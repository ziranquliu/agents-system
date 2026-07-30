"""
多智能体协作 API - 协作 CRUD / 启动 / 任务管理
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.collaboration import Collaboration, CollaborationTask
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services import collaboration_service

router = APIRouter(tags=["多智能体协作"])


class TaskCreate(BaseModel):
    agent_id: str
    agent_name: str | None = None
    order: int = 0
    role: str | None = None
    input_text: str | None = None


class CollaborationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    mode: str = "sequential"
    context: dict | None = None
    tasks: list[TaskCreate] = []


@router.get("/collaborations/modes")
async def get_modes():
    """获取所有协作模式"""
    modes = await collaboration_service.list_modes()
    return {"modes": modes}


@router.post("/collaborations")
async def create_collaboration(
    data: CollaborationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建协作会话"""
    collab = await collaboration_service.create_collaboration(
        db=db,
        name=data.name,
        mode=data.mode,
        description=data.description,
        context=data.context,
        created_by=current_user.id,
    )

    # 批量添加任务
    for task_data in data.tasks:
        await collaboration_service.add_task(
            db=db,
            collaboration_id=collab.id,
            agent_id=task_data.agent_id,
            agent_name=task_data.agent_name,
            order=task_data.order,
            role=task_data.role,
            input_text=task_data.input_text,
        )

    return {"id": collab.id, "name": collab.name, "mode": collab.mode, "status": collab.status}


@router.get("/collaborations")
async def list_collaborations(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    mode: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """获取协作列表"""
    items, total = await collaboration_service.list_collaborations(
        db=db, page=page, page_size=page_size, mode=mode, status=status,
    )
    return {
        "items": [_format_collab(c) for c in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/collaborations/{collab_id}")
async def get_collaboration(
    collab_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取协作详情"""
    collab = await db.get(Collaboration, collab_id)
    if not collab:
        raise HTTPException(status_code=404, detail="Collaboration not found")
    return _format_collab(collab)


@router.post("/collaborations/{collab_id}/tasks")
async def add_collaboration_task(
    collab_id: str,
    data: TaskCreate,
    db: AsyncSession = Depends(get_db),
):
    """添加协作任务"""
    task = await collaboration_service.add_task(
        db=db,
        collaboration_id=collab_id,
        agent_id=data.agent_id,
        agent_name=data.agent_name,
        order=data.order,
        role=data.role,
        input_text=data.input_text,
    )
    return _format_task(task)


@router.get("/collaborations/{collab_id}/tasks")
async def get_collaboration_tasks(
    collab_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取协作的所有任务"""
    collab = await db.get(collaboration_service.Collaboration, collab_id)
    if not collab:
        raise HTTPException(status_code=404, detail="Collaboration not found")

    tasks_result = await db.execute(
        select(CollaborationTask)
        .where(CollaborationTask.collaboration_id == collab_id)
        .order_by(CollaborationTask.order)
    )
    tasks = tasks_result.scalars().all()
    return {"tasks": [_format_task(t) for t in tasks]}


@router.post("/collaborations/{collab_id}/start")
async def start_collaboration(
    collab_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """启动协作执行"""
    try:
        collab = await collaboration_service.start_collaboration(db, collab_id)
        return {"message": "协作已启动并完成", "collaboration": _format_collab(collab)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


def _format_collab(c) -> dict:
    import json
    context = None
    result = None
    if c.context:
        try:
            context = json.loads(c.context)
        except (json.JSONDecodeError, TypeError):
            context = {"raw": c.context}
    if c.result:
        try:
            result = json.loads(c.result)
        except (json.JSONDecodeError, TypeError):
            result = {"raw": c.result}
    return {
        "id": c.id,
        "name": c.name,
        "description": c.description,
        "mode": c.mode,
        "status": c.status,
        "context": context,
        "result": result,
        "created_by": c.created_by,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _format_task(t) -> dict:
    return {
        "id": t.id,
        "collaboration_id": t.collaboration_id,
        "agent_id": t.agent_id,
        "agent_name": t.agent_name,
        "order": t.order,
        "role": t.role,
        "input_text": t.input_text,
        "output_text": t.output_text,
        "status": t.status,
        "error_message": t.error_message,
        "started_at": t.started_at.isoformat() if t.started_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
    }
