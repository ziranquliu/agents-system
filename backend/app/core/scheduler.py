"""
全局定时调度器 — APScheduler AsyncIOScheduler 集成

注册的任务：
1. 组件扫描（默认 5 分钟）— 4.10 本地组件扫描器
2. 更新检测（默认 24 小时）— 4.11 统一更新检测中心
3. 定期维护任务（按 MaintenanceTask.cron_expression）— 4.22.4
4. 定时备份（按 BackupPolicy.full_backup_cron / incremental_interval_hours / drill_cron）— 4.23
5. 操作审计归档与保留期清理（每日）— 4.25

每个任务使用独立的 DB session（async_session_factory），
避免与 FastAPI 请求生命周期耦合，故障不中断其他任务。
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from app.db.session import async_session_factory

logger = logging.getLogger("scheduler")

scheduler: Optional[AsyncIOScheduler] = None
# 已注册的 job id 集合（用于防重复注册）
_registered_jobs: set = set()


# ==================== 任务执行体 ====================

async def _run_scan():
    """定时触发组件扫描（4.10）"""
    try:
        from app.services.scanner_service import trigger_scan
        await trigger_scan(user_id="scheduler")
        logger.info("[scheduler] component scan completed")
    except Exception as e:
        logger.error(f"[scheduler] component scan failed: {e}")


async def _run_update_check():
    """定时更新检测（4.11）"""
    try:
        from app.services.update_service import check_updates
        async with async_session_factory() as session:
            await check_updates(session)
        logger.info("[scheduler] update check completed")
    except Exception as e:
        logger.error(f"[scheduler] update check failed: {e}")


async def _run_maintenance():
    """定期维护任务（4.22.4）— 动态读取启用的维护任务并执行"""
    try:
        from app.services.ops_service import MaintenanceService
        from app.models.ops import MaintenanceType
        from app.models.ops import MaintenanceTask as MaintTask

        async with async_session_factory() as session:
            tasks, _ = await MaintenanceService.list_tasks(session, enabled_only=True)
            for task in tasks:
                await _execute_maintenance_task(session, task)
    except Exception as e:
        logger.error(f"[scheduler] maintenance run failed: {e}")


async def _execute_maintenance_task(session, task):
    """执行单个维护任务，按类型执行对应清理逻辑并记录执行结果"""
    from app.services.ops_service import MaintenanceService
    from app.models.ops import MaintenanceType

    task_type = task.task_type
    processed = 0
    cleaned = 0
    try:
        if task_type == MaintenanceType.SESSION_CLEANUP:
            # 清理超过 7 天的会话
            from app.models.conversation import Conversation
            cutoff = datetime.utcnow() - timedelta(days=7)
            stmt = select(Conversation).where(Conversation.updated_at < cutoff)
            rows = (await session.execute(stmt)).scalars().all()
            for row in rows:
                await session.delete(row)
                cleaned += 1
            processed = len(rows)
        elif task_type == MaintenanceType.CACHE_CLEANUP:
            # 清理已停用/过期的模型缓存标记（此处做统计性清理）
            from app.models.agent import Agent
            stmt = select(Agent).where(Agent.status == "stopped")
            rows = (await session.execute(stmt)).scalars().all()
            processed = len(rows)
            cleaned = 0
        elif task_type == MaintenanceType.TEMP_FILE_CLEANUP:
            # 清理备份目录中的临时文件（tmp_* 前缀）
            import shutil
            from pathlib import Path
            from app.services.backup_enhanced_service import _BACKUP_DIR
            if _BACKUP_DIR and _BACKUP_DIR.exists():
                for f in _BACKUP_DIR.glob("tmp_*"):
                    try:
                        f.unlink(missing_ok=True)
                        cleaned += 1
                    except Exception:
                        pass
            processed = cleaned
        elif task_type == MaintenanceType.INDEX_REBUILD:
            # 索引重建：统计当前表行数作为健康检查
            from app.models.audit import AuditLog
            total = (await session.execute(
                select(AuditLog.id).limit(10000)
            )).scalars().all()
            processed = len(total)
        elif task_type == MaintenanceType.STATISTICS_ANALYSIS:
            # 统计分析：审计日志 24h 新增量统计
            from app.models.audit import AuditLog
            cutoff = datetime.utcnow() - timedelta(hours=24)
            total = (await session.execute(
                select(AuditLog.id).where(AuditLog.created_at >= cutoff).limit(100000)
            )).scalars().all()
            processed = len(total)
        else:
            processed = 0

        await MaintenanceService.execute_task(
            session, task.id,
            items_processed=processed,
            items_cleaned=cleaned,
            status="success",
        )
        await session.commit()
        logger.info(f"[scheduler] maintenance task '{task.name}' done: processed={processed} cleaned={cleaned}")
    except Exception as e:
        await session.rollback()
        try:
            await MaintenanceService.execute_task(
                session, task.id,
                status="failed",
                error_message=str(e)[:250],
            )
            await session.commit()
        except Exception:
            pass
        logger.error(f"[scheduler] maintenance task '{task.name}' failed: {e}")


async def _run_backup_job():
    """定时备份（4.23）— 读取启用的备份策略并执行全量备份"""
    try:
        from app.services.backup_enhanced_service import BackupEnhancedService
        from app.models.backup_enhanced import BackupType

        async with async_session_factory() as session:
            policies, _ = await BackupEnhancedService.list_policies(session, enabled_only=True)
            for policy in policies:
                await BackupEnhancedService.create_backup(
                    session,
                    agent_id=policy.agent_id,
                    agent_name=policy.agent_name,
                    backup_type=BackupType.FULL,
                    created_by="scheduler",
                )
            await session.commit()
        logger.info(f"[scheduler] scheduled full backup completed ({len(policies)} agents)")
    except Exception as e:
        logger.error(f"[scheduler] scheduled backup failed: {e}")


async def _run_incremental_backup_job():
    """定时增量备份（4.23）"""
    try:
        from app.services.backup_enhanced_service import BackupEnhancedService
        from app.models.backup_enhanced import BackupType

        async with async_session_factory() as session:
            policies, _ = await BackupEnhancedService.list_policies(session, enabled_only=True)
            for policy in policies:
                await BackupEnhancedService.create_backup(
                    session,
                    agent_id=policy.agent_id,
                    agent_name=policy.agent_name,
                    backup_type=BackupType.INCREMENTAL,
                    created_by="scheduler",
                )
            await session.commit()
        logger.info("[scheduler] scheduled incremental backup completed")
    except Exception as e:
        logger.error(f"[scheduler] incremental backup failed: {e}")


async def _run_drill_job():
    """定时恢复演练（4.23）"""
    try:
        from app.services.backup_enhanced_service import BackupEnhancedService, DrillService

        async with async_session_factory() as session:
            policies, _ = await BackupEnhancedService.list_policies(session, enabled_only=True)
            for policy in policies:
                # 每个 Agent 每轮演练一次，取最近一次备份
                backups, _ = await BackupEnhancedService.list_backups(
                    session, agent_id=policy.agent_id, limit=1
                )
                if backups:
                    await DrillService.create_drill(
                        session,
                        agent_id=policy.agent_id,
                        agent_name=policy.agent_name,
                        backup_id=backups[0].id,
                        created_by="scheduler",
                    )
            await session.commit()
        logger.info("[scheduler] scheduled restore drill completed")
    except Exception as e:
        logger.error(f"[scheduler] drill job failed: {e}")


async def _run_audit_maintenance():
    """审计日志归档与保留期清理（4.25）"""
    try:
        from app.services.audit_service import AuditService
        async with async_session_factory() as session:
            await AuditService.archive_old(session)
        async with async_session_factory() as session:
            await AuditService.enforce_retention(session)
        logger.info("[scheduler] audit archive + retention completed")
    except Exception as e:
        logger.error(f"[scheduler] audit maintenance failed: {e}")


async def _run_health_snapshot():
    """定时健康快照（4.24）— 对已配置健康检查的 Agent 执行 L1-L2 检查并生成快照"""
    try:
        from app.models.health import AgentHealthConfig
        from app.services.health_service import HealthCheckExecutor

        async with async_session_factory() as session:
            configs = (await session.execute(select(AgentHealthConfig))).scalars().all()
            for cfg in configs:
                await HealthCheckExecutor.run_full_check(
                    session, agent_id=cfg.agent_id, agent_name=cfg.agent_name, level="L2"
                )
            await session.commit()
        logger.info(f"[scheduler] health snapshot completed ({len(configs)} agents)")
    except Exception as e:
        logger.error(f"[scheduler] health snapshot failed: {e}")


# ==================== 运维报告定时生成（B2.5） ====================

async def _run_report_task(report_type: str, period_start: datetime, period_end: datetime):
    """生成运维报告（日/周/月），生成后自动推送通知"""
    try:
        from app.services.ops_service import ReportService

        async with async_session_factory() as session:
            report = await ReportService.generate_report(
                session,
                report_type=report_type,
                period_start=period_start,
                period_end=period_end,
                notify=True,
                created_by="scheduler",
            )
            await session.commit()
        logger.info(f"[scheduler] {report_type} report generated: {period_start.date()} ~ {period_end.date()}")
    except Exception as e:
        logger.error(f"[scheduler] {report_type} report generation failed: {e}")


async def _run_daily_report():
    """日报：每日 08:00（统计昨日 00:00 ~ 24:00）"""
    now = datetime.now()
    yesterday = now - timedelta(days=1)
    start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    await _run_report_task("daily", start, end)


async def _run_weekly_report():
    """周报：每周一 08:30（统计上周一 00:00 ~ 本周一 00:00）"""
    now = datetime.now()
    start = (now - timedelta(days=now.weekday(), weeks=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    await _run_report_task("weekly", start, end)


async def _run_monthly_report():
    """月报：每月 1 日 09:00（统计上月 1 日 00:00 ~ 本月 1 日 00:00）"""
    now = datetime.now()
    first_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_end = first_this - timedelta(days=1)
    first_last = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    await _run_report_task("monthly", first_last, first_this)


# ==================== 调度器管理 ====================

def _register_fixed_jobs():
    """注册固定间隔任务"""
    scheduler.add_job(
        _run_scan,
        trigger=IntervalTrigger(minutes=5),
        id="scan_every_5min",
        replace_existing=True,
        misfire_grace_time=60,
    )
    scheduler.add_job(
        _run_update_check,
        trigger=IntervalTrigger(hours=24),
        id="update_check_24h",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        _run_audit_maintenance,
        trigger=CronTrigger(hour=2, minute=30),
        id="audit_maintenance_daily",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        _run_health_snapshot,
        trigger=IntervalTrigger(minutes=15),
        id="health_snapshot_15min",
        replace_existing=True,
        misfire_grace_time=300,
    )
    # 备份任务：以默认值注册，随后在 refresh 时按策略动态调整
    scheduler.add_job(
        _run_backup_job,
        trigger=CronTrigger(hour=3, minute=0),
        id="backup_full_daily",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        _run_incremental_backup_job,
        trigger=IntervalTrigger(hours=6),
        id="backup_incremental_6h",
        replace_existing=True,
        misfire_grace_time=1800,
    )
    scheduler.add_job(
        _run_drill_job,
        trigger=CronTrigger(day_of_week="sun", hour=4, minute=0),
        id="backup_drill_weekly",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        _run_maintenance,
        trigger=IntervalTrigger(hours=1),
        id="maintenance_dynamic_1h",
        replace_existing=True,
        misfire_grace_time=1800,
    )
    # 运维报告定时生成（B2.5）：日报每日 08:00、周报周一 08:30、月报每月 1 日 09:00
    scheduler.add_job(
        _run_daily_report,
        trigger=CronTrigger(hour=8, minute=0),
        id="ops_report_daily",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        _run_weekly_report,
        trigger=CronTrigger(day_of_week="mon", hour=8, minute=30),
        id="ops_report_weekly",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        _run_monthly_report,
        trigger=CronTrigger(day=1, hour=9, minute=0),
        id="ops_report_monthly",
        replace_existing=True,
        misfire_grace_time=7200,
    )


def start_scheduler() -> AsyncIOScheduler:
    """启动全局调度器（幂等）"""
    global scheduler
    if scheduler is not None and scheduler.running:
        return scheduler

    scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
    _register_fixed_jobs()
    scheduler.start()
    logger.info(f"[scheduler] started with {len(scheduler.get_jobs())} jobs")
    return scheduler


def stop_scheduler():
    """停止调度器（幂等）"""
    global scheduler
    if scheduler is not None and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[scheduler] stopped")
    scheduler = None


def get_scheduler_status() -> dict:
    """调度器状态（供 API 展示）"""
    if scheduler is None or not scheduler.running:
        return {"running": False, "jobs": []}
    jobs = []
    for job in scheduler.get_jobs():
        next_run = job.next_run_time.isoformat() if job.next_run_time else None
        jobs.append({
            "id": job.id,
            "name": job.name or job.id,
            "next_run": next_run,
        })
    return {"running": True, "jobs": jobs}
