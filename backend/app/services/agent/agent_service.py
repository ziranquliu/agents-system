"""
Agent 服务 - CRUD 操作与状态管理
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.schemas.agent import AgentCreate, AgentUpdate


_VALID_STATUS_TRANSITIONS = {
    "draft": ["running", "stopped"],
    "running": ["stopped", "error"],
    "stopped": ["running", "archived"],
    "error": ["stopped", "draft"],
    "archived": [],
}


def validate_status_transition(current: str, target: str) -> bool:
    """校验状态转换是否合法"""
    allowed = _VALID_STATUS_TRANSITIONS.get(current, [])
    return target in allowed


async def list_agents(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    search: Optional[str] = None,
    workspace_id: Optional[str] = None,
    created_by: Optional[str] = None,
) -> tuple[list[Agent], int]:
    """获取 Agent 列表（分页 + 筛选）"""
    query = select(Agent)

    # 筛选条件
    if status:
        query = query.where(Agent.status == status)
    if search:
        query = query.where(
            or_(
                Agent.name.ilike(f"%{search}%"),
                Agent.description.ilike(f"%{search}%"),
            )
        )
    if workspace_id:
        query = query.where(Agent.workspace_id == workspace_id)
    if created_by:
        query = query.where(Agent.created_by == created_by)

    # 总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页
    query = query.order_by(Agent.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    agents = list(result.scalars().all())

    return agents, total


async def get_agent(db: AsyncSession, agent_id: str) -> Optional[Agent]:
    """根据 ID 获取 Agent"""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    return result.scalar_one_or_none()


async def create_agent(db: AsyncSession, data: AgentCreate, user_id: str) -> Agent:
    """创建 Agent"""
    now = datetime.now(timezone.utc)
    agent = Agent(
        id=str(uuid.uuid4()),
        name=data.name,
        description=data.description,
        avatar=data.avatar,
        system_prompt=data.system_prompt,
        welcome_message=data.welcome_message,
        status=data.status or "draft",
        model_provider=data.model_provider,
        model_name=data.model_name,
        model_config_template_id=data.model_config_template_id,
        temperature=data.temperature,
        max_tokens=data.max_tokens,
        context_window=data.context_window,
        enabled_skills=json.dumps(data.enabled_skills) if data.enabled_skills else None,
        enabled_mcp_servers=json.dumps(data.enabled_mcp_servers) if data.enabled_mcp_servers else None,
        workspace_id=data.workspace_id,
        created_by=user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(agent)
    await db.flush()
    return agent


async def update_agent(db: AsyncSession, agent_id: str, data: AgentUpdate) -> Optional[Agent]:
    """更新 Agent"""
    agent = await get_agent(db, agent_id)
    if not agent:
        return None

    update_data = data.model_dump(exclude_unset=True)

    # JSON 字段特殊处理
    if "enabled_skills" in update_data:
        update_data["enabled_skills"] = json.dumps(update_data["enabled_skills"]) if update_data["enabled_skills"] else None
    if "enabled_mcp_servers" in update_data:
        update_data["enabled_mcp_servers"] = json.dumps(update_data["enabled_mcp_servers"]) if update_data["enabled_mcp_servers"] else None

    for field, value in update_data.items():
        setattr(agent, field, value)

    agent.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return agent


async def delete_agent(db: AsyncSession, agent_id: str) -> bool:
    """删除 Agent（硬删除）"""
    agent = await get_agent(db, agent_id)
    if not agent:
        return False
    await db.delete(agent)
    await db.flush()
    return True


async def update_agent_status(db: AsyncSession, agent_id: str, new_status: str) -> Optional[Agent]:
    """更新 Agent 状态（含状态机校验）"""
    agent = await get_agent(db, agent_id)
    if not agent:
        return None

    if not validate_status_transition(agent.status, new_status):
        raise ValueError(
            f"Invalid status transition: {agent.status} -> {new_status}. "
            f"Allowed transitions: {_VALID_STATUS_TRANSITIONS.get(agent.status, [])}"
        )

    agent.status = new_status
    agent.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return agent
