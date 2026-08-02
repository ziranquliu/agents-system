"""
任务管理 API
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services import task_service

router = APIRouter(tags=["任务管理"])


@router.get("/tasks")
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    priority: str | None = None,
    assigned_to: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    items, total = await task_service.list_tasks(db, page=page, page_size=page_size, status=status, priority=priority, assigned_to=assigned_to, search=search)
    return {"items": [_format_task(t) for t in items], "total": total, "page": page, "page_size": page_size}


@router.post("/tasks")
async def create_task(
    title: str = Body(...),
    description: str | None = None,
    priority: str = "medium",
    assigned_to: str | None = None,
    due_date: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dd = datetime.fromisoformat(due_date) if due_date else None
    task = await task_service.create_task(db, title=title, description=description, priority=priority, assigned_to=assigned_to, due_date=dd, created_by=current_user.id)
    return _format_task(task)


@router.patch("/tasks/{task_id}/status")
async def update_task_status(
    task_id: str,
    status: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    task = await task_service.update_task_status(db, task_id, status)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _format_task(task)


@router.get("/tasks/stats")
async def get_task_stats(
    db: AsyncSession = Depends(get_db),
):
    return await task_service.get_task_stats(db)


def _format_task(t):
    return {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "priority": t.priority,
        "assigned_to": t.assigned_to,
        "created_by": t.created_by,
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }
