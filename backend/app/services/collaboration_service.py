"""
多智能体协作服务 - 创建/执行/跟踪协作
"""
import json
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import selectinload, joinedload
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

    elif collab.mode == "supervisor":
        # 监督模式：协调 Agent 收集所有子 Agent 输出后统一汇总
        shared_input = collab.context or tasks[0].input_text or ""
        for task in tasks:
            task.status = "running"
            task.started_at = datetime.utcnow()
            task.input_text = task.input_text or shared_input
            task.output_text = f"[模拟] Agent '{task.agent_name}' 执行完成，产出建议方案"
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            await db.flush()
        outputs = [{"agent": t.agent_name, "output": t.output_text} for t in tasks]
        collab.result = json.dumps({
            "mode": "supervisor",
            "summary": f"监督 Agent 汇总 {len(tasks)} 个子 Agent 的执行结果，形成最终方案",
            "member_outputs": outputs,
        })

    elif collab.mode == "debate":
        # 辩论模式：各 Agent 独立发表观点，最后汇总
        shared_input = collab.context or tasks[0].input_text or ""
        viewpoints = []
        for task in tasks:
            task.status = "running"
            task.started_at = datetime.utcnow()
            task.input_text = task.input_text or shared_input
            task.output_text = f"[模拟] Agent '{task.agent_name}' 观点: 基于输入 '{shared_input[:30]}' 分析，认为应优先考虑自身专业领域"
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            viewpoints.append({"agent": task.agent_name, "viewpoint": task.output_text})
            await db.flush()
        collab.result = json.dumps({
            "mode": "debate",
            "viewpoints": viewpoints,
            "summary": f"共收集 {len(viewpoints)} 个观点，存在分歧，建议投票表决",
        })

    elif collab.mode == "team":
        # Agent 团队模式：按角色分工并行执行，Leader 汇总
        shared_input = collab.context or tasks[0].input_text or ""
        member_results = []
        for task in tasks:
            task.status = "running"
            task.started_at = datetime.utcnow()
            task.input_text = task.input_text or shared_input
            role_tag = f"[{task.role}]" if task.role else ""
            task.output_text = f"[模拟] 团队成员{role_tag} '{task.agent_name}' 完成分工任务"
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            member_results.append({"agent": task.agent_name, "role": task.role, "output": task.output_text})
            await db.flush()
        collab.result = json.dumps({
            "mode": "team",
            "team_leader": "协调者",
            "member_results": member_results,
            "summary": f"团队 {len(member_results)} 名成员按角色分工完成协作",
        })

    elif collab.mode == "pipeline":
        # 管道链模式：严格按 order 流水线传递（与 sequential 类似但强调阶段化产物）
        prev_output = collab.context or ""
        stages = []
        for task in tasks:
            task.status = "running"
            task.started_at = datetime.utcnow()
            effective_input = prev_output if prev_output else task.input_text or ""
            task.input_text = effective_input
            task.output_text = f"[模拟] 流水线阶段[{task.order}] '{task.agent_name}' 产出中间产物"
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            stages.append({"stage": task.order, "agent": task.agent_name, "input_len": len(effective_input), "output": task.output_text})
            prev_output = task.output_text
            await db.flush()
        collab.result = json.dumps({
            "mode": "pipeline",
            "stages": stages,
            "final_output": prev_output,
            "summary": f"{len(stages)} 阶段流水线执行完毕",
        })

    elif collab.mode == "market":
        # 市场竞价模式：各 Agent 提交方案与报价，按评分选择最优
        shared_input = collab.context or tasks[0].input_text or ""
        bids = []
        for i, task in enumerate(tasks):
            task.status = "running"
            task.started_at = datetime.utcnow()
            task.input_text = task.input_text or shared_input
            # 模拟竞价：不同 Agent 给出不同报价与评分
            bid_price = 5 + (i * 3) % 20
            score = 70 + (i * 7) % 25
            task.output_text = f"[模拟] Agent '{task.agent_name}' 报价 ${bid_price}，方案评分 {score}/100"
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            bids.append({"agent": task.agent_name, "bid_price": bid_price, "score": score})
            await db.flush()
        best = max(bids, key=lambda b: b["score"] / max(b["bid_price"], 1))
        collab.result = json.dumps({
            "mode": "market",
            "bids": bids,
            "winner": best["agent"],
            "summary": f"{len(bids)} 个 Agent 参与竞价，'{best['agent']}' 以性价比最优中标",
        })

    elif collab.mode == "vote":
        # 投票/共识模式：各 Agent 投票表决，加权聚合达成共识
        shared_input = collab.context or tasks[0].input_text or ""
        votes = []
        options = ["方案A", "方案B", "方案C"]
        for i, task in enumerate(tasks):
            task.status = "running"
            task.started_at = datetime.utcnow()
            task.input_text = task.input_text or shared_input
            choice = options[i % len(options)]
            confidence = 60 + (i * 9) % 35  # 置信度 60-95
            task.output_text = f"[模拟] Agent '{task.agent_name}' 投票选择 {choice}（置信度 {confidence}%）"
            task.status = "completed"
            task.completed_at = datetime.utcnow()
            votes.append({"agent": task.agent_name, "choice": choice, "confidence": confidence})
            await db.flush()
        # 加权投票（置信度作权重）
        tally: dict = {}
        for v in votes:
            tally.setdefault(v["choice"], {"count": 0, "weighted": 0.0})
            tally[v["choice"]]["count"] += 1
            tally[v["choice"]]["weighted"] += v["confidence"]
        consensus = max(tally, key=lambda k: tally[k]["weighted"])
        collab.result = json.dumps({
            "mode": "vote",
            "votes": votes,
            "tally": tally,
            "consensus": consensus,
            "summary": f"{len(votes)} 个 Agent 投票表决，达成共识：{consensus}",
        })

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
        {"id": "supervisor", "name": "监督模式", "description": "一个监督 Agent 协调多个执行 Agent，汇总结果", "icon": "👑"},
        {"id": "team", "name": "Agent 团队模式", "description": "多 Agent 按角色分工协作，Leader 汇总团队成果", "icon": "👥"},
        {"id": "pipeline", "name": "管道链模式", "description": "任务按阶段流水线传递，前阶段产物作为后阶段输入", "icon": "🔗"},
        {"id": "debate", "name": "辩论模式", "description": "多个 Agent 对同一问题进行辩论，最后汇总观点", "icon": "🎯"},
        {"id": "vote", "name": "投票/共识模式", "description": "多 Agent 投票表决，按置信度加权聚合达成共识", "icon": "🗳️"},
        {"id": "market", "name": "市场竞价模式", "description": "多 Agent 提交方案与报价，按性价比竞价中标", "icon": "🏷️"},
        {"id": "sequential", "name": "顺序执行", "description": "多个 Agent 按顺序依次执行，前一个输出作为后一个输入", "icon": "➡️"},
        {"id": "parallel", "name": "并行执行", "description": "多个 Agent 同时处理不同子任务，互不干扰", "icon": "🔀"},
        {"id": "broadcast", "name": "广播模式", "description": "所有 Agent 收到相同输入，各自独立输出结果", "icon": "📡"},
    ]
