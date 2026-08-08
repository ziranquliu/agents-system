"""
智能体自动化运维服务
覆盖：自动部署、Auto Scaling、日志管理、定期维护、异常自愈、运维报告
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select, func, and_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ops import (
    AgentDeployment, AgentDeploymentStatus,
    ScalingPolicy, ScalingEvent, ScalingDirection, ScalingMetricType,
    LogEntry, LogCollectionConfig, LogLevel, LogSourceType,
    MaintenanceTask, MaintenanceExecution, MaintenanceType,
    SelfHealRecord, HealRule, HealLevel, HealStatus,
    OpsReport, ReportType,
)

logger = logging.getLogger(__name__)


# ==================== 4.22.1 自动部署 ====================

class DeploymentService:

    @staticmethod
    async def create_deployment(
        session: AsyncSession,
        agent_name: str,
        template_yaml: str,
        version: str = "1.0.0",
        parameters: Optional[Dict[str, Any]] = None,
        created_by: str = "system",
    ) -> AgentDeployment:
        dep = AgentDeployment(
            agent_name=agent_name,
            version=version,
            template_yaml=template_yaml,
            parameters=json.dumps(parameters) if parameters else None,
            status=AgentDeploymentStatus.PENDING,
            created_by=created_by,
        )
        session.add(dep)
        await session.flush()
        return dep

    @staticmethod
    async def get_deployment(session: AsyncSession, dep_id: str) -> Optional[AgentDeployment]:
        stmt = select(AgentDeployment).where(AgentDeployment.id == dep_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_deployments(
        session: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        status: Optional[AgentDeploymentStatus] = None,
        agent_name: Optional[str] = None,
    ) -> Tuple[List[AgentDeployment], int]:
        conditions = [AgentDeployment.is_active == True]
        if status:
            conditions.append(AgentDeployment.status == status)
        if agent_name:
            conditions.append(AgentDeployment.agent_name.ilike(f"%{agent_name}%"))
        stmt = select(AgentDeployment).where(and_(*conditions)).order_by(desc(AgentDeployment.created_at)).offset(skip).limit(limit)
        count_stmt = select(func.count(AgentDeployment.id)).where(and_(*conditions))
        result = await session.execute(stmt)
        count_result = await session.execute(count_stmt)
        return list(result.scalars().all()), count_result.scalar() or 0

    @staticmethod
    async def update_status(
        session: AsyncSession,
        dep_id: str,
        status: AgentDeploymentStatus,
        error_message: Optional[str] = None,
        health_score: Optional[float] = None,
    ) -> Optional[AgentDeployment]:
        dep = await DeploymentService.get_deployment(session, dep_id)
        if not dep:
            return None
        dep.status = status
        dep.updated_at = datetime.utcnow()
        if error_message:
            dep.error_message = error_message
        if health_score is not None:
            dep.health_score = health_score
        if status == AgentDeploymentStatus.HEALTHY:
            dep.deployed_at = datetime.utcnow()
        elif status == AgentDeploymentStatus.ROLLED_BACK:
            dep.rolled_back_at = datetime.utcnow()
        await session.flush()
        return dep

    @staticmethod
    async def rollback_deployment(session: AsyncSession, dep_id: str) -> Optional[AgentDeployment]:
        dep = await DeploymentService.get_deployment(session, dep_id)
        if not dep:
            return None
        dep.status = AgentDeploymentStatus.ROLLED_BACK
        dep.rolled_back_at = datetime.utcnow()
        dep.updated_at = datetime.utcnow()
        await session.flush()
        return dep

    @staticmethod
    async def delete_deployment(session: AsyncSession, dep_id: str) -> bool:
        dep = await DeploymentService.get_deployment(session, dep_id)
        if not dep:
            return False
        dep.is_active = False
        await session.flush()
        return True

    @staticmethod
    async def get_stats(session: AsyncSession) -> Dict[str, Any]:
        """部署统计"""
        total = select(func.count(AgentDeployment.id)).where(AgentDeployment.is_active == True)
        successful = select(func.count(AgentDeployment.id)).where(
            and_(AgentDeployment.is_active == True, AgentDeployment.status == AgentDeploymentStatus.HEALTHY)
        )
        failed = select(func.count(AgentDeployment.id)).where(
            and_(AgentDeployment.is_active == True, AgentDeployment.status == AgentDeploymentStatus.FAILED)
        )
        t, s, f = await asyncio.gather(
            session.execute(total), session.execute(successful), session.execute(failed)
        )
        return {
            "total": t.scalar() or 0,
            "successful": s.scalar() or 0,
            "failed": f.scalar() or 0,
            "success_rate": round((s.scalar() or 0) / max(t.scalar() or 1, 1) * 100, 2),
        }


# ==================== 4.22.2 Auto Scaling ====================

class AutoScalingService:

    @staticmethod
    async def get_policy(session: AsyncSession, policy_id: str) -> Optional[ScalingPolicy]:
        stmt = select(ScalingPolicy).where(ScalingPolicy.id == policy_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_policy_by_agent(session: AsyncSession, agent_id: str) -> Optional[ScalingPolicy]:
        stmt = select(ScalingPolicy).where(ScalingPolicy.agent_id == agent_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert_policy(
        session: AsyncSession,
        agent_id: str,
        agent_name: str,
        **kwargs,
    ) -> ScalingPolicy:
        existing = await AutoScalingService.get_policy_by_agent(session, agent_id)
        if existing:
            for k, v in kwargs.items():
                if hasattr(existing, k) and v is not None:
                    setattr(existing, k, v)
            existing.updated_at = datetime.utcnow()
            await session.flush()
            return existing
        policy = ScalingPolicy(agent_id=agent_id, agent_name=agent_name, **kwargs)
        session.add(policy)
        await session.flush()
        return policy

    @staticmethod
    async def list_policies(
        session: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        enabled_only: bool = False,
    ) -> Tuple[List[ScalingPolicy], int]:
        conditions = []
        if enabled_only:
            conditions.append(ScalingPolicy.enabled == True)
        stmt = select(ScalingPolicy).where(and_(*conditions)).order_by(desc(ScalingPolicy.created_at)).offset(skip).limit(limit)
        count_stmt = select(func.count(ScalingPolicy.id)).where(and_(*conditions))
        result = await session.execute(stmt)
        count_result = await session.execute(count_stmt)
        return list(result.scalars().all()), count_result.scalar() or 0

    @staticmethod
    async def evaluate_scaling(
        session: AsyncSession,
        agent_id: str,
        current_instances: int,
        metric_type: ScalingMetricType,
        metric_value: float,
    ) -> Optional[ScalingEvent]:
        """评估是否需要扩缩容"""
        policy = await AutoScalingService.get_policy_by_agent(session, agent_id)
        if not policy or not policy.enabled:
            return None

        # 检查冷却期
        last_event_stmt = select(ScalingEvent).where(
            ScalingEvent.agent_id == agent_id
        ).order_by(desc(ScalingEvent.created_at)).limit(1)
        last_event_result = await session.execute(last_event_stmt)
        last_event = last_event_result.scalar_one_or_none()

        now = datetime.utcnow()
        direction = None
        new_instances = current_instances
        reason = ""

        if metric_value >= policy.scale_out_threshold and current_instances < policy.max_instances:
            if last_event:
                cooldown_sec = (now - last_event.created_at).total_seconds()
                if cooldown_sec < policy.scale_out_cooldown:
                    return None  # 冷却中
            direction = ScalingDirection.SCALE_OUT
            new_instances = min(current_instances + policy.scale_out_step, policy.max_instances)
            reason = f"{metric_type}={metric_value:.1f} >= threshold={policy.scale_out_threshold}"

        elif metric_value <= policy.scale_in_threshold and current_instances > policy.min_instances:
            if last_event:
                cooldown_sec = (now - last_event.created_at).total_seconds()
                if cooldown_sec < policy.scale_in_cooldown:
                    return None
            direction = ScalingDirection.SCALE_IN
            new_instances = max(current_instances - policy.scale_in_step, policy.min_instances)
            reason = f"{metric_type}={metric_value:.1f} <= threshold={policy.scale_in_threshold}"

        if direction is None or new_instances == current_instances:
            return None

        event = ScalingEvent(
            agent_id=agent_id,
            agent_name=policy.agent_name,
            direction=direction,
            previous_instances=current_instances,
            new_instances=new_instances,
            trigger_reason=reason,
            metric_value=metric_value,
            success=True,
        )
        session.add(event)
        await session.flush()
        return event

    @staticmethod
    async def list_events(
        session: AsyncSession,
        agent_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
        days: int = 7,
    ) -> Tuple[List[ScalingEvent], int]:
        conditions = [ScalingEvent.created_at >= datetime.utcnow() - timedelta(days=days)]
        if agent_id:
            conditions.append(ScalingEvent.agent_id == agent_id)
        stmt = select(ScalingEvent).where(and_(*conditions)).order_by(desc(ScalingEvent.created_at)).offset(skip).limit(limit)
        count_stmt = select(func.count(ScalingEvent.id)).where(and_(*conditions))
        result = await session.execute(stmt)
        count_result = await session.execute(count_stmt)
        return list(result.scalars().all()), count_result.scalar() or 0

    @staticmethod
    async def get_scaling_stats(session: AsyncSession, days: int = 30) -> Dict[str, Any]:
        """扩缩容统计"""
        since = datetime.utcnow() - timedelta(days=days)
        total = select(func.count(ScalingEvent.id)).where(ScalingEvent.created_at >= since)
        scale_out = select(func.count(ScalingEvent.id)).where(
            and_(ScalingEvent.created_at >= since, ScalingEvent.direction == ScalingDirection.SCALE_OUT)
        )
        scale_in = select(func.count(ScalingEvent.id)).where(
            and_(ScalingEvent.created_at >= since, ScalingEvent.direction == ScalingDirection.SCALE_IN)
        )
        t, o, i = await asyncio.gather(
            session.execute(total), session.execute(scale_out), session.execute(scale_in)
        )
        return {
            "total": t.scalar() or 0,
            "scale_out": o.scalar() or 0,
            "scale_in": i.scalar() or 0,
            "period_days": days,
        }


# ==================== 4.22.3 日志管理 ====================

class LogService:

    @staticmethod
    async def ingest_log(
        session: AsyncSession,
        level: LogLevel,
        logger_name: str,
        message: str,
        source_type: LogSourceType = LogSourceType.SYSTEM,
        source_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> LogEntry:
        entry = LogEntry(
            level=level,
            logger=logger_name,
            message=message,
            source_type=source_type,
            source_id=source_id,
            agent_id=agent_id,
            trace_id=trace_id,
            log_metadata=json.dumps(metadata) if metadata else None,
        )
        session.add(entry)
        await session.flush()
        return entry

    @staticmethod
    async def search_logs(
        session: AsyncSession,
        level: Optional[LogLevel] = None,
        logger_name: Optional[str] = None,
        source_type: Optional[LogSourceType] = None,
        agent_id: Optional[str] = None,
        keyword: Optional[str] = None,
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[LogEntry], int]:
        conditions = []
        if level:
            conditions.append(LogEntry.level == level)
        if logger_name:
            conditions.append(LogEntry.logger == logger_name)
        if source_type:
            conditions.append(LogEntry.source_type == source_type)
        if agent_id:
            conditions.append(LogEntry.agent_id == agent_id)
        if keyword:
            conditions.append(LogEntry.message.ilike(f"%{keyword}%"))
        if from_time:
            conditions.append(LogEntry.timestamp >= from_time)
        if to_time:
            conditions.append(LogEntry.timestamp <= to_time)

        stmt = select(LogEntry).where(and_(*conditions)).order_by(desc(LogEntry.timestamp)).offset(skip).limit(limit)
        count_stmt = select(func.count(LogEntry.id)).where(and_(*conditions))
        result = await session.execute(stmt)
        count_result = await session.execute(count_stmt)
        return list(result.scalars().all()), count_result.scalar() or 0

    @staticmethod
    async def get_log_stats(
        session: AsyncSession,
        days: int = 7,
    ) -> Dict[str, Any]:
        """日志统计"""
        since = datetime.utcnow() - timedelta(days=days)
        total = select(func.count(LogEntry.id)).where(LogEntry.timestamp >= since)
        by_level = {}
        for lvl in ["DEBUG", "INFO", "WARN", "ERROR", "FATAL"]:
            by_level[lvl.lower()] = select(func.count(LogEntry.id)).where(
                and_(LogEntry.timestamp >= since, LogEntry.level == lvl)
            )
        by_source = {}
        for src in ["agent", "skill", "mcp", "system"]:
            by_source[src] = select(func.count(LogEntry.id)).where(
                and_(LogEntry.timestamp >= since, LogEntry.source_type == src)
            )

        t = await session.execute(total)
        result = {"total": t.scalar() or 0, "period_days": days, "by_level": {}, "by_source": {}}
        for k, st in by_level.items():
            r = await session.execute(st)
            result["by_level"][k] = r.scalar() or 0
        for k, st in by_source.items():
            r = await session.execute(st)
            result["by_source"][k] = r.scalar() or 0
        return result

    @staticmethod
    async def get_collection_config(session: AsyncSession, agent_id: str) -> Optional[LogCollectionConfig]:
        stmt = select(LogCollectionConfig).where(LogCollectionConfig.agent_id == agent_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert_collection_config(
        session: AsyncSession,
        agent_id: str,
        **kwargs,
    ) -> LogCollectionConfig:
        existing = await LogService.get_collection_config(session, agent_id)
        if existing:
            for k, v in kwargs.items():
                if hasattr(existing, k) and v is not None:
                    setattr(existing, k, v)
            existing.updated_at = datetime.utcnow()
            await session.flush()
            return existing
        config = LogCollectionConfig(agent_id=agent_id, **kwargs)
        session.add(config)
        await session.flush()
        return config

    @staticmethod
    async def list_collection_configs(session: AsyncSession, skip: int = 0, limit: int = 50) -> Tuple[List[LogCollectionConfig], int]:
        stmt = select(LogCollectionConfig).offset(skip).limit(limit)
        count_stmt = select(func.count(LogCollectionConfig.id))
        result = await session.execute(stmt)
        count_result = await session.execute(count_stmt)
        return list(result.scalars().all()), count_result.scalar() or 0


# ==================== 4.22.4 定期维护 ====================

class MaintenanceService:

    @staticmethod
    async def create_task(
        session: AsyncSession,
        task_type: MaintenanceType,
        name: str,
        cron_expression: str,
        description: Optional[str] = None,
        maintenance_window_start: Optional[str] = None,
        maintenance_window_end: Optional[str] = None,
        timeout_seconds: int = 3600,
    ) -> MaintenanceTask:
        task = MaintenanceTask(
            task_type=task_type,
            name=name,
            description=description,
            cron_expression=cron_expression,
            maintenance_window_start=maintenance_window_start,
            maintenance_window_end=maintenance_window_end,
            timeout_seconds=timeout_seconds,
        )
        session.add(task)
        await session.flush()
        return task

    @staticmethod
    async def get_task(session: AsyncSession, task_id: str) -> Optional[MaintenanceTask]:
        stmt = select(MaintenanceTask).where(MaintenanceTask.id == task_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_tasks(
        session: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        task_type: Optional[MaintenanceType] = None,
        enabled_only: bool = False,
    ) -> Tuple[List[MaintenanceTask], int]:
        conditions = []
        if task_type:
            conditions.append(MaintenanceTask.task_type == task_type)
        if enabled_only:
            conditions.append(MaintenanceTask.enabled == True)
        stmt = select(MaintenanceTask).where(and_(*conditions)).order_by(asc(MaintenanceTask.task_type)).offset(skip).limit(limit)
        count_stmt = select(func.count(MaintenanceTask.id)).where(and_(*conditions))
        result = await session.execute(stmt)
        count_result = await session.execute(count_stmt)
        return list(result.scalars().all()), count_result.scalar() or 0

    @staticmethod
    async def update_task(session: AsyncSession, task_id: str, **kwargs) -> Optional[MaintenanceTask]:
        task = await MaintenanceService.get_task(session, task_id)
        if not task:
            return None
        for k, v in kwargs.items():
            if hasattr(task, k) and v is not None:
                setattr(task, k, v)
        task.updated_at = datetime.utcnow()
        await session.flush()
        return task

    @staticmethod
    async def delete_task(session: AsyncSession, task_id: str) -> bool:
        task = await MaintenanceService.get_task(session, task_id)
        if not task:
            return False
        task.enabled = False
        await session.flush()
        return True

    @staticmethod
    async def execute_task(
        session: AsyncSession,
        task_id: str,
        items_processed: int = 0,
        items_cleaned: int = 0,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> Optional[MaintenanceExecution]:
        """记录维护执行结果"""
        task = await MaintenanceService.get_task(session, task_id)
        if not task:
            return None

        now = datetime.utcnow()
        exec_record = MaintenanceExecution(
            task_id=task_id,
            task_type=task.task_type,
            completed_at=now,
            status=status,
            items_processed=items_processed,
            items_cleaned=items_cleaned,
            error_message=error_message,
            duration_seconds=0,
        )

        if task.last_run_at:
            exec_record.duration_seconds = (now - task.last_run_at).total_seconds()

        task.last_run_at = now
        task.last_run_result = status
        task.updated_at = now

        session.add(exec_record)
        await session.flush()
        return exec_record

    @staticmethod
    async def list_executions(
        session: AsyncSession,
        task_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
        days: int = 7,
    ) -> Tuple[List[MaintenanceExecution], int]:
        conditions = [MaintenanceExecution.started_at >= datetime.utcnow() - timedelta(days=days)]
        if task_id:
            conditions.append(MaintenanceExecution.task_id == task_id)
        stmt = select(MaintenanceExecution).where(and_(*conditions)).order_by(desc(MaintenanceExecution.started_at)).offset(skip).limit(limit)
        count_stmt = select(func.count(MaintenanceExecution.id)).where(and_(*conditions))
        result = await session.execute(stmt)
        count_result = await session.execute(count_stmt)
        return list(result.scalars().all()), count_result.scalar() or 0


# ==================== 4.22.5 异常自愈 ====================

class SelfHealService:

    @staticmethod
    async def create_rule(
        session: AsyncSession,
        agent_id: str,
        anomaly_type: str,
        heal_level: HealLevel = HealLevel.LEVEL_1_RESTART,
        consecutive_threshold: int = 3,
        error_rate_threshold: Optional[float] = None,
        p99_latency_threshold_ms: Optional[float] = None,
        health_drop_threshold: Optional[float] = None,
        auto_heal: bool = True,
        cooldown_seconds: int = 300,
    ) -> HealRule:
        rule = HealRule(
            agent_id=agent_id,
            anomaly_type=anomaly_type,
            heal_level=heal_level,
            consecutive_threshold=consecutive_threshold,
            error_rate_threshold=error_rate_threshold,
            p99_latency_threshold_ms=p99_latency_threshold_ms,
            health_drop_threshold=health_drop_threshold,
            auto_heal=auto_heal,
            cooldown_seconds=cooldown_seconds,
        )
        session.add(rule)
        await session.flush()
        return rule

    @staticmethod
    async def get_rule(session: AsyncSession, rule_id: str) -> Optional[HealRule]:
        stmt = select(HealRule).where(HealRule.id == rule_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_rules(
        session: AsyncSession,
        agent_id: Optional[str] = None,
        enabled_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[HealRule], int]:
        conditions = []
        if agent_id:
            conditions.append(HealRule.agent_id == agent_id)
        if enabled_only:
            conditions.append(HealRule.enabled == True)
        stmt = select(HealRule).where(and_(*conditions)).order_by(desc(HealRule.created_at)).offset(skip).limit(limit)
        count_stmt = select(func.count(HealRule.id)).where(and_(*conditions))
        result = await session.execute(stmt)
        count_result = await session.execute(count_stmt)
        return list(result.scalars().all()), count_result.scalar() or 0

    @staticmethod
    async def update_rule(session: AsyncSession, rule_id: str, **kwargs) -> Optional[HealRule]:
        rule = await SelfHealService.get_rule(session, rule_id)
        if not rule:
            return None
        for k, v in kwargs.items():
            if hasattr(rule, k) and v is not None:
                setattr(rule, k, v)
        rule.updated_at = datetime.utcnow()
        await session.flush()
        return rule

    @staticmethod
    async def delete_rule(session: AsyncSession, rule_id: str) -> bool:
        rule = await SelfHealService.get_rule(session, rule_id)
        if not rule:
            return False
        rule.enabled = False
        await session.flush()
        return True

    @staticmethod
    async def trigger_heal(
        session: AsyncSession,
        agent_id: str,
        agent_name: str,
        anomaly_type: str,
        anomaly_value: float,
        threshold_value: float,
        heal_level: HealLevel = HealLevel.LEVEL_1_RESTART,
        auto_heal: bool = True,
    ) -> SelfHealRecord:
        record = SelfHealRecord(
            agent_id=agent_id,
            agent_name=agent_name,
            anomaly_type=anomaly_type,
            anomaly_value=anomaly_value,
            threshold_value=threshold_value,
            heal_level=heal_level,
            status=HealStatus.HEALING if auto_heal else HealStatus.DETECTED,
            action_taken=f"Auto-{heal_level} triggered for {anomaly_type}" if auto_heal else "Pending manual intervention",
        )
        session.add(record)
        await session.flush()

        # ---- 自愈通知通道：Webhook / 邮件 ----
        try:
            from app.services.notification_service import (
                get_notification_config, notify,
            )
            from app.models.notification import NotifyMethod
            from app.models.agent import Agent

            cfg = await get_notification_config(session)
            agent_webhook = None
            if cfg.notify_method and cfg.notify_method != NotifyMethod.OFF:
                # 读取 Agent 级 webhook_url（优先于全局）
                agent_stmt = select(Agent.webhook_url).where(Agent.id == agent_id)
                agent_webhook = (await session.execute(agent_stmt)).scalar_one_or_none()

                action_desc = f"自动执行自愈 {heal_level}：{anomaly_type}" if auto_heal \
                    else f"检测到异常（{anomaly_type}），等待人工处理"
                title = f"【自愈通知】Agent {agent_name} {anomaly_type}"
                content = (
                    f"Agent: {agent_name} ({agent_id})\n"
                    f"异常类型: {anomaly_type}\n"
                    f"异常值: {anomaly_value} / 阈值: {threshold_value}\n"
                    f"自愈等级: {heal_level}\n"
                    f"处理动作: {action_desc}\n"
                    f"触发时间: {datetime.utcnow().isoformat()}\n"
                )
                recipients = cfg.default_recipients or None
                await notify(
                    method=cfg.notify_method,
                    target=recipients,
                    title=title,
                    content=content,
                    webhook_url=agent_webhook,
                    cfg=cfg,
                )
        except Exception as exc:  # noqa: BLE001 - 通知失败不影响自愈主流程
            logger.warning("trigger_heal: 发送自愈通知失败: %s", exc)

        return record

    @staticmethod
    async def complete_heal(
        session: AsyncSession,
        record_id: str,
        status: HealStatus,
        health_score_after: Optional[float] = None,
        verified: bool = False,
        error_message: Optional[str] = None,
    ) -> Optional[SelfHealRecord]:
        stmt = select(SelfHealRecord).where(SelfHealRecord.id == record_id)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        if not record:
            return None
        record.status = status
        record.healed_at = datetime.utcnow()
        record.duration_seconds = (record.healed_at - record.detected_at).total_seconds()
        record.verified = verified
        if health_score_after is not None:
            record.health_score_after = health_score_after
        if error_message:
            record.error_message = error_message
        await session.flush()
        return record

    @staticmethod
    async def list_heal_records(
        session: AsyncSession,
        agent_id: Optional[str] = None,
        status: Optional[HealStatus] = None,
        skip: int = 0,
        limit: int = 50,
        days: int = 30,
    ) -> Tuple[List[SelfHealRecord], int]:
        conditions = [SelfHealRecord.detected_at >= datetime.utcnow() - timedelta(days=days)]
        if agent_id:
            conditions.append(SelfHealRecord.agent_id == agent_id)
        if status:
            conditions.append(SelfHealRecord.status == status)
        stmt = select(SelfHealRecord).where(and_(*conditions)).order_by(desc(SelfHealRecord.detected_at)).offset(skip).limit(limit)
        count_stmt = select(func.count(SelfHealRecord.id)).where(and_(*conditions))
        result = await session.execute(stmt)
        count_result = await session.execute(count_stmt)
        return list(result.scalars().all()), count_result.scalar() or 0

    @staticmethod
    async def get_heal_stats(session: AsyncSession, days: int = 30) -> Dict[str, Any]:
        """自愈统计"""
        since = datetime.utcnow() - timedelta(days=days)
        total = select(func.count(SelfHealRecord.id)).where(SelfHealRecord.detected_at >= since)
        success = select(func.count(SelfHealRecord.id)).where(
            and_(SelfHealRecord.detected_at >= since, SelfHealRecord.status == HealStatus.SUCCESS)
        )
        failed = select(func.count(SelfHealRecord.id)).where(
            and_(SelfHealRecord.detected_at >= since, SelfHealRecord.status == HealStatus.FAILED)
        )
        by_level = {}
        for lvl in ["restart", "rollback", "degrade"]:
            by_level[lvl] = select(func.count(SelfHealRecord.id)).where(
                and_(SelfHealRecord.detected_at >= since, SelfHealRecord.heal_level == lvl)
            )

        t, s, f = await asyncio.gather(
            session.execute(total), session.execute(success), session.execute(failed),
        )
        result = {
            "total": t.scalar() or 0,
            "success": s.scalar() or 0,
            "failed": f.scalar() or 0,
            "success_rate": round((s.scalar() or 0) / max(t.scalar() or 1, 1) * 100, 2),
            "by_level": {},
            "period_days": days,
        }
        for k, st in by_level.items():
            r = await session.execute(st)
            result["by_level"][k] = r.scalar() or 0
        return result


# ==================== 4.22.6 运维报告 ====================

class ReportService:

    @staticmethod
    async def generate_report(
        session: AsyncSession,
        report_type: ReportType,
        period_start: datetime,
        period_end: datetime,
        notify: bool = True,
        created_by: str = "system",
    ) -> OpsReport:
        """生成运维报告（汇总各维度数据），生成后可通过通知通道推送

        notify=True 时，生成后通过 notification_service（webhook/邮件）推送摘要。
        """
        from app.services.monitoring_service import MonitoringService
        from app.services.token_service import TokenService
        from app.services.notification_service import get_notification_config, notify

        days = max((period_end - period_start).days, 1)
        # 采集数据
        deploy_stats = await DeploymentService.get_stats(session)
        scaling_stats = await AutoScalingService.get_scaling_stats(session, days=days)
        log_stats = await LogService.get_log_stats(session, days=days)
        heal_stats = await SelfHealService.get_heal_stats(session, days=days)

        # 维护执行数
        maint_stmt = select(func.count(MaintenanceExecution.id)).where(
            and_(
                MaintenanceExecution.started_at >= period_start,
                MaintenanceExecution.started_at <= period_end,
            )
        )
        maint_result = await session.execute(maint_stmt)
        maint_count = maint_result.scalar() or 0

        # Top 异常 Agent（按自愈记录数）
        top_agents_stmt = (
            select(SelfHealRecord.agent_name, func.count(SelfHealRecord.id).label("count"))
            .where(
                and_(
                    SelfHealRecord.detected_at >= period_start,
                    SelfHealRecord.detected_at <= period_end,
                )
            )
            .group_by(SelfHealRecord.agent_name)
            .order_by(desc("count"))
            .limit(5)
        )
        top_result = await session.execute(top_agents_stmt)
        top_agents = [{"name": r.agent_name, "count": r.count} for r in top_result.all()]

        # 资源趋势（真实数据：监控服务最新指标聚合）
        resource_trends = {"avg_cpu": None, "avg_memory": None, "avg_response_time": None, "avg_health_score": None, "agent_count": 0}
        try:
            monitor = MonitoringService(session)
            latest = await monitor.get_latest_metrics()
            if latest:
                cpus = [m.get("cpu_percent") for m in latest.values() if m.get("cpu_percent") is not None]
                mems = [m.get("memory_mb") for m in latest.values() if m.get("memory_mb") is not None]
                p95s = [m.get("latency_p95") for m in latest.values() if m.get("latency_p95") is not None]
                healths = [m.get("health_score") for m in latest.values() if m.get("health_score") is not None]
                qps = sum(m.get("qps") or 0 for m in latest.values())
                resource_trends = {
                    "avg_cpu": round(sum(cpus) / len(cpus), 2) if cpus else None,
                    "avg_memory": round(sum(mems) / len(mems), 2) if mems else None,
                    "avg_response_time": round(sum(p95s) / len(p95s), 2) if p95s else None,
                    "avg_health_score": round(sum(healths) / len(healths), 2) if healths else None,
                    "total_qps": round(qps, 2),
                    "agent_count": len(latest),
                }
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"生成报告：获取资源趋势失败: {exc}")

        # Token 消耗（真实数据）
        token_stats = {}
        try:
            token_stats = await TokenService.get_stats(session, days=days)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"生成报告：获取 Token 统计失败: {exc}")

        availability = deploy_stats.get("success_rate", 100)
        total_requests = log_stats.get("total", 0) * 2  # 估算
        error_count = log_stats.get("by_level", {}).get("error", 0) + log_stats.get("by_level", {}).get("fatal", 0)

        suggestions = []
        if heal_stats.get("total", 0) > 10:
            suggestions.append(f"自愈事件数较高（{heal_stats['total']}次），建议检查异常根因")
        if deploy_stats.get("failed", 0) > 0:
            suggestions.append(f"有 {deploy_stats['failed']} 次部署失败，请检查部署模板")
        if error_count > total_requests * 0.05:
            suggestions.append("错误率超过 5%，建议优先处理")
        if token_stats.get("total_cost"):
            suggestions.append(
                f"周期内 Token 消耗 {token_stats.get('total_tokens', 0)} 个，成本 ${token_stats.get('total_cost', 0):.4f}"
            )
        if resource_trends.get("avg_cpu") and resource_trends["avg_cpu"] > 80:
            suggestions.append("平均 CPU 使用率超过 80%，建议扩容或优化")
        if resource_trends.get("avg_health_score") is not None and resource_trends["avg_health_score"] < 70:
            suggestions.append("平均健康评分低于 70，建议排查异常 Agent")

        raw_data = {
            "deployment": deploy_stats,
            "scaling": scaling_stats,
            "logs": log_stats,
            "healing": heal_stats,
            "maintenance_count": maint_count,
            "top_agents": top_agents,
            "resource_trends": resource_trends,
            "token_usage": token_stats,
        }

        report = OpsReport(
            report_type=report_type,
            title=f"{report_type.capitalize()} Operations Report - {period_start.date()} to {period_end.date()}",
            period_start=period_start,
            period_end=period_end,
            availability_rate=availability,
            total_requests=total_requests,
            error_count=error_count,
            anomaly_count=heal_stats.get("total", 0),
            heal_count=heal_stats.get("success", 0),
            scaling_events=scaling_stats.get("total", 0),
            maintenance_executions=maint_count,
            top_agents=json.dumps(top_agents),
            resource_trends=json.dumps(resource_trends),
            suggestions="\n".join(suggestions) if suggestions else "系统运行状态良好，无需特别关注。",
            raw_data=json.dumps(raw_data, ensure_ascii=False, default=str),
            created_by=created_by,
        )
        session.add(report)
        await session.flush()

        # 生成后推送通知（webhook / 邮件，复用 notification_service）
        if notify:
            try:
                cfg = await get_notification_config(session)
                content = "\n".join(
                    [
                        f"报告类型: {report_type.value if hasattr(report_type, 'value') else report_type}",
                        f"统计周期: {period_start.date()} ~ {period_end.date()}",
                        f"可用率: {availability}%",
                        f"总请求: {total_requests}，错误: {error_count}",
                        f"自愈次数: {heal_stats.get('total', 0)}（成功 {heal_stats.get('success', 0)}）",
                        f"扩缩容事件: {scaling_stats.get('total', 0)}",
                        f"维护执行: {maint_count}",
                        f"Token 消耗: {token_stats.get('total_tokens', 0)}（成本 ${token_stats.get('total_cost', 0):.4f}）",
                        f"平均健康评分: {resource_trends.get('avg_health_score', '-')}",
                        "",
                        "建议:",
                        "\n".join(suggestions) if suggestions else "系统运行状态良好，无需特别关注。",
                    ]
                )
                await notify(
                    method=cfg.notify_method,
                    target=cfg.default_recipients,
                    title=f"[运维报告] {report.title}",
                    content=content,
                    webhook_url=cfg.webhook_url,
                    cfg=cfg,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"生成报告：推送通知失败: {exc}")
        return report

    @staticmethod
    async def get_report(session: AsyncSession, report_id: str) -> Optional[OpsReport]:
        stmt = select(OpsReport).where(OpsReport.id == report_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_reports(
        session: AsyncSession,
        report_type: Optional[ReportType] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[OpsReport], int]:
        conditions = []
        if report_type:
            conditions.append(OpsReport.report_type == report_type)
        stmt = select(OpsReport).where(and_(*conditions)).order_by(desc(OpsReport.generated_at)).offset(skip).limit(limit)
        count_stmt = select(func.count(OpsReport.id)).where(and_(*conditions))
        result = await session.execute(stmt)
        count_result = await session.execute(count_stmt)
        return list(result.scalars().all()), count_result.scalar() or 0

    @staticmethod
    async def delete_report(session: AsyncSession, report_id: str) -> bool:
        stmt = select(OpsReport).where(OpsReport.id == report_id)
        result = await session.execute(stmt)
        report = result.scalar_one_or_none()
        if not report:
            return False
        await session.delete(report)
        await session.flush()
        return True


# Helper to parse JSON fields
def _safe_json_loads(value: Optional[str], default=None):
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


import asyncio  # noqa: E402 - imported here for async gather usage throughout
