"""
批量 Skill 分配与安装 API — 依赖预检 / 安装队列 / 报告
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.batch_install_service import BatchInstallService

router = APIRouter(prefix="/api/v1/batch-install", tags=["批量安装"])


def _item_to_dict(i):
    return {
        "id": i.id,
        "queue_id": i.queue_id,
        "skill_id": i.skill_id,
        "skill_name": i.skill_name,
        "agent_id": i.agent_id,
        "agent_name": i.agent_name,
        "dep_check_status": i.dep_check_status,
        "status": i.status,
        "error_message": i.error_message,
        "started_at": i.started_at.isoformat() if i.started_at else None,
        "completed_at": i.completed_at.isoformat() if i.completed_at else None,
    }


def _queue_to_dict(q):
    return {
        "id": q.id,
        "operation": q.operation,
        "status": q.status,
        "total_items": q.total_items,
        "success_count": q.success_count or 0,
        "fail_count": q.fail_count or 0,
        "warn_count": q.warn_count or 0,
        "precheck_status": q.precheck_status,
        "precheck_summary": q.precheck_summary,
        "created_by": q.created_by,
        "created_at": q.created_at.isoformat() if q.created_at else None,
        "completed_at": q.completed_at.isoformat() if q.completed_at else None,
    }


# ----------------------------------------------------------
# 依赖预检
# ----------------------------------------------------------

@router.post("/precheck", summary="批量安装预检")
async def batch_precheck(data: dict, db: AsyncSession = Depends(get_db)):
    """对批量安装进行依赖预检，返回通过/警告/阻塞状态"""
    svc = BatchInstallService(db)
    result = await svc.batch_precheck(
        skill_ids=data.get("skill_ids", []),
        agent_ids=data.get("agent_ids", []),
    )
    return {"success": True, "data": result}


# ----------------------------------------------------------
# 批量安装
# ----------------------------------------------------------

@router.post("", summary="创建批量安装任务")
async def create_batch_install(data: dict, db: AsyncSession = Depends(get_db)):
    """创建批量安装任务（自动执行预检）"""
    svc = BatchInstallService(db)
    queue = await svc.create_batch_install(
        skill_ids=data["skill_ids"],
        agent_ids=data["agent_ids"],
        operation=data.get("operation", "install"),
        created_by=data.get("created_by", ""),
    )
    return {"success": True, "data": _queue_to_dict(queue)}


@router.post("/{queue_id}/execute", summary="执行批量安装")
async def execute_batch(queue_id: str, db: AsyncSession = Depends(get_db)):
    """执行指定队列的批量安装"""
    svc = BatchInstallService(db)
    try:
        queue = await svc.execute_batch(queue_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": _queue_to_dict(queue)}


@router.get("", summary="查询批量安装队列列表")
async def list_queues(
    status: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    svc = BatchInstallService(db)
    items, total = await svc.list_queues(status, offset, limit)
    return {
        "success": True,
        "data": [_queue_to_dict(q) for q in items],
        "total": total,
    }


@router.get("/{queue_id}", summary="获取队列详情")
async def get_queue(queue_id: str, db: AsyncSession = Depends(get_db)):
    svc = BatchInstallService(db)
    queue = await svc.get_queue(queue_id)
    if not queue:
        raise HTTPException(404, "队列不存在")
    return {"success": True, "data": _queue_to_dict(queue)}


@router.get("/{queue_id}/items", summary="获取队列安装项列表")
async def get_queue_items(
    queue_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    svc = BatchInstallService(db)
    items, total = await svc.get_queue_items(queue_id, offset, limit)
    return {
        "success": True,
        "data": [_item_to_dict(i) for i in items],
        "total": total,
    }


@router.get("/{queue_id}/report", summary="生成安装报告")
async def generate_report(queue_id: str, db: AsyncSession = Depends(get_db)):
    svc = BatchInstallService(db)
    report = await svc.generate_report(queue_id)
    if "error" in report:
        raise HTTPException(404, report["error"])
    return {"success": True, "data": report}
