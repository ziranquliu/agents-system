from typing import Optional
from datetime import datetime, date
from fastapi import APIRouter, Depends, Query

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User, OperationLog
from app.api.v1.auth import get_current_user

router = APIRouter(tags=["操作日志"])


@router.get("/operation-logs")
async def list_operation_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    user_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询操作日志（分页 + 多维度筛选）"""
    conditions = []

    if action:
        conditions.append(OperationLog.action == action)
    if resource_type:
        conditions.append(OperationLog.resource_type == resource_type)
    if user_id:
        conditions.append(OperationLog.user_id == user_id)
    if date_from:
        conditions.append(OperationLog.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        conditions.append(OperationLog.created_at <= datetime.combine(date_to, datetime.max.time()))

    # 总条数
    count_q = select(func.count(OperationLog.id)).where(and_(*conditions))
    total = (await db.execute(count_q)).scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    q = (
        select(OperationLog)
        .where(and_(*conditions))
        .order_by(OperationLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = (await db.execute(q)).scalars().all()

    items = []
    for log in rows:
        items.append({
            "id": log.id,
            "user_id": log.user_id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "detail": log.detail,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


@router.get("/operation-logs/actions")
async def list_operation_actions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取所有操作类型列表（用于下拉筛选）"""
    q = select(OperationLog.action).distinct().order_by(OperationLog.action)
    rows = (await db.execute(q)).scalars().all()
    return {"actions": rows}


@router.get("/operation-logs/resource-types")
async def list_operation_resource_types(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取所有资源类型列表（用于下拉筛选）"""
    q = select(OperationLog.resource_type).distinct().order_by(OperationLog.resource_type)
    rows = (await db.execute(q)).scalars().all()
    return {"resource_types": rows}
