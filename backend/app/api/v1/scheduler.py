"""
全局定时调度器 API — 查看调度状态 / 手动触发定时任务
"""
from fastapi import APIRouter, HTTPException

from app.core.scheduler import get_scheduler_status, start_scheduler, stop_scheduler

router = APIRouter(prefix="/api/v1/scheduler", tags=["全局定时调度器"])


@router.get("/status", summary="调度器运行状态与任务列表")
async def status():
    return get_scheduler_status()


@router.post("/start", summary="启动调度器")
async def start():
    try:
        sched = start_scheduler()
        return {"running": True, "jobs": len(sched.get_jobs())}
    except Exception as e:
        raise HTTPException(500, f"启动调度器失败: {e}")


@router.post("/stop", summary="停止调度器")
async def stop():
    stop_scheduler()
    return {"running": False}


@router.post("/trigger", summary="立即触发指定任务（手动执行）")
async def trigger(task: str):
    """task: scan / update_check / maintenance / backup / backup_incremental / drill / audit / health"""
    import asyncio
    from app.core import scheduler as sched_mod

    tasks_map = {
        "scan": sched_mod._run_scan,
        "update_check": sched_mod._run_update_check,
        "maintenance": sched_mod._run_maintenance,
        "backup": sched_mod._run_backup_job,
        "backup_incremental": sched_mod._run_incremental_backup_job,
        "drill": sched_mod._run_drill_job,
        "audit": sched_mod._run_audit_maintenance,
        "health": sched_mod._run_health_snapshot,
    }
    fn = tasks_map.get(task)
    if not fn:
        raise HTTPException(400, f"未知任务: {task}，可选: {list(tasks_map.keys())}")
    try:
        await asyncio.wait_for(fn(), timeout=600)
        return {"task": task, "triggered": True}
    except Exception as e:
        raise HTTPException(500, f"任务 {task} 执行失败: {e}")
