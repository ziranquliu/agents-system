import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.task import Task

"""
任务管理服务 - CRUD/筛选/统计
"""




async def list_tasks(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_to: Optional[str] = None,
    search: Optional[str] = None,
) -> tuple[list[Task], int]:
    query = select(Task)
    if status:
        query = query.where(Task.status == status)
    if priority:
        query = query.where(Task.priority == priority)
    if assigned_to:
        query = query.where(Task.assigned_to == assigned_to)
    if search:
        query = query.where(or_(Task.title.ilike(f"%{search}%"), Task.description.ilike(f"%{search}%")))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(desc(Task.priority), desc(Task.created_at)).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all()), total


async def create_task(
    db: AsyncSession,
    title: str,
    description: Optional[str] = None,
    priority: str = "medium",
    assigned_to: Optional[str] = None,
    due_date: Optional[datetime] = None,
    created_by: str = "",
) -> Task:
    task = Task(
        id=str(uuid.uuid4()),
        title=title,
        description=description,
        priority=priority,
        assigned_to=assigned_to,
        due_date=due_date,
        created_by=created_by,
    )
    db.add(task)
    await db.flush()
    return task


async def update_task_status(db: AsyncSession, task_id: str, status: str) -> Optional[Task]:
    task = await db.get(Task, task_id)
    if not task:
        return None
    task.status = status
    task.updated_at = datetime.utcnow()
    await db.flush()
    return task


async def get_task_stats(db: AsyncSession) -> dict:
    results = await db.execute(select(Task.status, func.count(Task.id)).group_by(Task.status))
    stats = {"total": 0, "todo": 0, "in_progress": 0, "done": 0, "cancelled": 0}
    for status, count in results:
        stats[status] = count
        stats["total"] += count
    # 优先级统计
    priority_results = await db.execute(select(Task.priority, func.count(Task.id)).group_by(Task.priority))
    priorities = {}
    for p, c in priority_results:
        priorities[p] = c
    stats["by_priority"] = priorities
    return stats
