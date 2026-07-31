"""
统一更新检测 API - 检查更新/执行更新
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services import update_service

router = APIRouter(tags=["更新检测"])


class UpdateItem(BaseModel):
    component_type: str
    component_id: str
    component_name: str
    current_version: str
    latest_version: str
    description: str | None = None
    icon: str | None = None


class UpdateResponse(BaseModel):
    total: int
    updates: list[UpdateItem]


@router.get("/updates/available")
async def get_available_updates(
    db: AsyncSession = Depends(get_db),
):
    """获取所有可更新的组件"""
    updates = await update_service.check_updates(db)
    return UpdateResponse(
        total=len(updates),
        updates=[UpdateItem(**u) for u in updates],
    )


@router.get("/updates/count")
async def get_update_count(
    db: AsyncSession = Depends(get_db),
):
    """获取可更新的组件数量"""
    count = await update_service.get_update_count(db)
    return {"count": count}


@router.post("/updates/refresh")
async def refresh_updates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """刷新检查更新"""
    updates = await update_service.check_updates(db)
    return {"message": "检查完成", "updates_count": len(updates)}


@router.post("/updates/apply/{component_type}/{component_id}")
async def apply_update(
    component_type: str,
    component_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """执行单个组件更新（自动保留快照）"""
    if component_type not in ("skill", "mcp", "agent", "model"):
        raise HTTPException(status_code=400, detail=f"不支持的组件类型: {component_type}")
    result = await update_service.update_component(
        db, component_type, component_id,
        created_by=current_user.username if current_user else "manual",
    )
    return result


@router.post("/updates/batch")
async def batch_apply_updates(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量更新：多组件排队执行，返回汇总报告"""
    component_type = body.get("component_type")
    ids = body.get("component_ids", [])
    if component_type not in ("skill", "mcp", "agent", "model"):
        raise HTTPException(status_code=400, detail=f"不支持的组件类型: {component_type}")
    if not ids:
        raise HTTPException(status_code=400, detail="component_ids 不能为空")
    return await update_service.batch_update_components(
        db, component_type, ids,
        created_by=current_user.username if current_user else "manual",
    )


@router.get("/updates/snapshots")
async def list_snapshots(
    component_type: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """更新快照列表（用于回滚）"""
    return await update_service.list_snapshots(db, component_type=component_type, limit=limit)


@router.post("/updates/rollback/{snapshot_id}")
async def rollback_update(
    snapshot_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """回滚组件到快照状态"""
    return await update_service.rollback_component(
        db, snapshot_id,
        created_by=current_user.username if current_user else "manual",
    )


@router.get("/updates/logs")
async def list_update_logs(
    component_type: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """更新操作日志（时间/变更/兼容性/回滚状态）"""
    return await update_service.list_update_logs(db, component_type=component_type, limit=limit)
