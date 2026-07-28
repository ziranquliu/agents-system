"""Skill 服务 - CRUD 操作、状态管理、Agent-Skill 绑定"""
import json
import uuid
from typing import Optional

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill, SkillBinding
from app.schemas.skill import SkillCreate, SkillUpdate, SkillResponse


def skill_to_response(skill: Skill, agents_count: int = 0) -> SkillResponse:
    """将 Skill ORM 转换为响应对象"""
    return SkillResponse(
        id=skill.id,
        name=skill.name,
        type=skill.type,
        version=skill.version,
        category=skill.category,
        description=skill.description,
        status="active" if skill.enabled else "inactive",
        agents_count=agents_count,
        created_at=skill.created_at,
    )


async def list_skills(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    type_filter: Optional[str] = None,
    search: Optional[str] = None,
) -> tuple[list[Skill], int]:
    """获取 Skill 列表（分页 + 类型筛选 + 搜索）"""
    query = select(Skill)

    # 筛选条件
    if type_filter:
        query = query.where(Skill.type == type_filter)
    if search:
        query = query.where(
            or_(
                Skill.name.ilike(f"%{search}%"),
                Skill.description.ilike(f"%{search}%"),
            )
        )

    # 总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页
    query = query.order_by(Skill.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    skills = list(result.scalars().all())

    return skills, total


async def get_skill(db: AsyncSession, skill_id: str) -> Optional[Skill]:
    """根据 ID 获取 Skill"""
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    return result.scalar_one_or_none()


async def get_skill_agents_count(db: AsyncSession, skill_id: str) -> int:
    """获取绑定到指定 Skill 的 Agent 数量"""
    result = await db.execute(
        select(func.count()).where(SkillBinding.skill_id == skill_id)
    )
    return result.scalar() or 0


async def create_skill(db: AsyncSession, data: SkillCreate) -> Skill:
    """创建 Skill"""
    skill = Skill(
        id=str(uuid.uuid4()),
        name=data.name,
        type=data.type or "tool",
        version=data.version or "1.0.0",
        category=data.category,
        description=data.description,
        enabled=data.enabled,
        parameters=json.dumps(data.config) if data.config else None,
    )
    db.add(skill)
    await db.flush()
    return skill


async def update_skill(db: AsyncSession, skill_id: str, data: SkillUpdate) -> Optional[Skill]:
    """更新 Skill"""
    skill = await get_skill(db, skill_id)
    if not skill:
        return None

    update_data = data.model_dump(exclude_unset=True)

    # config 字段映射到 model 的 parameters 字段
    if "config" in update_data:
        config_val = update_data.pop("config")
        update_data["parameters"] = json.dumps(config_val) if config_val else None

    for field, value in update_data.items():
        setattr(skill, field, value)

    await db.flush()
    return skill


async def delete_skill(db: AsyncSession, skill_id: str) -> bool:
    """删除 Skill（硬删除，同时清理关联绑定）"""
    skill = await get_skill(db, skill_id)
    if not skill:
        return False

    # 删除关联的绑定记录
    bindings_result = await db.execute(
        select(SkillBinding).where(SkillBinding.skill_id == skill_id)
    )
    for binding in bindings_result.scalars().all():
        await db.delete(binding)

    await db.delete(skill)
    await db.flush()
    return True


async def toggle_skill(db: AsyncSession, skill_id: str) -> Optional[Skill]:
    """切换 Skill 启用/停用状态"""
    skill = await get_skill(db, skill_id)
    if not skill:
        return None
    skill.enabled = not skill.enabled
    await db.flush()
    return skill


async def bind_skill_to_agent(
    db: AsyncSession,
    skill_id: str,
    agent_id: str,
    config: Optional[dict] = None,
) -> Optional[SkillBinding]:
    """将 Skill 绑定到 Agent"""
    # 检查 Skill 是否存在
    skill = await get_skill(db, skill_id)
    if not skill:
        return None

    # 检查是否已存在绑定（幂等）
    result = await db.execute(
        select(SkillBinding).where(
            SkillBinding.skill_id == skill_id,
            SkillBinding.agent_id == agent_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        # 如果已存在，更新配置
        if config is not None:
            existing.config = json.dumps(config)
            await db.flush()
        return existing

    binding = SkillBinding(
        id=str(uuid.uuid4()),
        skill_id=skill_id,
        agent_id=agent_id,
        config=json.dumps(config) if config else None,
    )
    db.add(binding)
    await db.flush()
    return binding


async def unbind_skill_from_agent(
    db: AsyncSession, skill_id: str, agent_id: str
) -> bool:
    """解绑 Skill 与 Agent"""
    result = await db.execute(
        select(SkillBinding).where(
            SkillBinding.skill_id == skill_id,
            SkillBinding.agent_id == agent_id,
        )
    )
    binding = result.scalar_one_or_none()
    if not binding:
        return False
    await db.delete(binding)
    await db.flush()
    return True
