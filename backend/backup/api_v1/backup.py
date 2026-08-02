"""
备份与恢复 API
"""
from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services import backup_service

router = APIRouter(tags=["备份与恢复"])


@router.post("/backup/create")
async def create_backup(
    notes: str | None = Body(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建备份"""
    return await backup_service.create_backup(db, created_by=current_user.id, notes=notes)


@router.get("/backup/list")
async def list_backups():
    """列出所有备份"""
    backups = await backup_service.list_backups()
    return {"backups": backups, "count": len(backups)}


@router.delete("/backup/{backup_id}")
async def delete_backup(backup_id: str):
    """删除备份"""
    success = await backup_service.delete_backup(backup_id)
    if not success:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="备份不存在")
    return {"message": "备份已删除", "backup_id": backup_id}
