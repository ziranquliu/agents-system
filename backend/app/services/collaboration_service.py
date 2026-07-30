"""
多智能体协作服务 - 创建/执行/跟踪协作
"""
import json
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collaboration import Collaboration, CollaborationTask
from app.models.agent import Agent


async def create_collaboration(
    db: AsyncSession,
    name: str,
    mode: str,
    description: Optional[str] = None,
    context: Optional[dict] = None,
    created_by: str = "",
) -> Collaboration:
    """创建协作会话"""
    collab = Collaboration(
        id=str(uuid.uuid4()),
        name=name,
        description=description,
        mode=mode,
        status="draft",
        context=json.dumps(context) if context else None,
        created_by=created_by,
    )
    db.add(collab)
    await db.flush()
    return collab


async def add_task(
    db: AsyncSession,
    collaboration_id: str,
    agent_id: str,
    agent_name: Optional[str] = None,
    order: int = 0,
    role: Optional[str] = None,
    input_text: Optional[str] = None,
) -> CollaborationTask:
    """添加协作任务"""
    # 获取 Agent 名称
    if not agent_name:
        result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()
        agent_name = agent.name if agent else "Unknown"

    task = CollaborationTask(
        id=str(uuid.uuid4()),
        collaboration_id=collaboration_id,
        agent_id=agent_id,
        agent_name=agent_name,
        order=order,
        role=role,
        input_text=input_text,
        status="pending",
    )
    db.add(task)
    await db.flush()
    return task


async def start_collaboration(db: AsyncSession, collaboration_id: str) -> Collaboration:
    """启动协作执行

    根据模式执行所有任务：
    - sequential: 按 order 顺序执行，每个任务输出作为下一个任务的输入
    - parallel: 所有任务同时执行（使用独立上下文）
    - broadcast: 所有任务都收到相同的输入
    """
    collab = await db.get(Collaboration, collaboration_id)
    if not collab:
        raise ValueError(f"Collaboration not found: {collaboration_id}")

    collab.status = "running"
    await db.flush()

    tasks_result = await db.execute(
        select(CollaborationTask)
        .where(CollaborationTask.collaboration_id == collaboration_id)
        .order_by(CollaborationTask.order)
    )
    tasks = list(tasks_result.scalars().all())

    if not tasks:
        collab.status = "completed"
        await db.flush()
        return collab

    if collab.mode == "sequential":
        prev_output = collab.context or ""
        for task in tasks:
            task.status = "running"
            task.started_at = datetime.utcnow()
            # 把前一个任务的输出作为输入（如果是第一个，使用初始上下文）
            effective_input = prev_output if prev_output else task.input_text or ""
            task.input_text = effective_input
            task.output_text = f"[模拟] Agent '{task.agent_name}' 处理完成: 收到输入 {len(effective_input)} 字符"
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            prev_output = task.output_text
            await db.flush()

        collab.result = json.dumps({"final_output": prev_output, "tasks_count": len(tasks)})

    elif collab.mode in ("parallel", "broadcast"):
        shared_input = collab.context or tasks[0].input_text or ""
        for task in tasks:
            task.status = "running"
            task.started_at = datetime.utcnow()
            task.input_text = task.input_text or shared_input
            task.output_text = f"[模拟] Agent '{task.agent_name}' 并行处理完成"
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            await db.flush()

        outputs = [t.output_text for t in tasks]
        collab.result = json.dumps({"outputs": outputs, "tasks_count": len(tasks)})

    collab.status = "completed"
    await db.flush()
    return collab


async def list_collaborations(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 10,
    mode: Optional[str] = None,
    status: Optional[str] = None,
) -> tuple[list[Collaboration], int]:
    """获取协作列表"""
    query = select(Collaboration)
    if mode:
        query = query.where(Collaboration.mode == mode)
    if status:
        query = query.where(Collaboration.status == status)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(desc(Collaboration.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    return list(result.scalars().all()), total


async def list_modes() -> list[dict]:
    """获取所有协作模式"""
    return [
        {"id": "sequential", "name": "顺序执行", "description": "多个 Agent 按顺序依次执行，前一个输出作为后一个输入", "icon": "➡️"},
        {"id": "parallel", "name": "并行执行", "description": "多个 Agent 同时处理不同子任务，互不干扰", "icon": "🔀"},
        {"id": "broadcast", "name": "广播模式", "description": "所有 Agent 收到相同输入，各自独立输出结果", "icon": "📡"},
        {"id": "supervisor", "name": "监督模式", "description": "一个监督 Agent 协调多个执行 Agent，汇总结果", "icon": "👑"},
        {"id": "debate", "name": "辩论模式", "description": "多个 Agent 对同一问题进行辩论，最后汇总观点", "icon": "🎯"},
    ]
