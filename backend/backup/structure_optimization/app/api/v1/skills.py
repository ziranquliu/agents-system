"""Skill 管理 API - 完整的 CRUD + 绑定管理"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.schemas.skill import (
    SkillCreate,
    SkillUpdate,
    SkillResponse,
    SkillListResponse,
    SkillBindRequest,
)
from app.services.auth_service import get_current_user
from app.services import skill_service

router = APIRouter()


@router.get("/", response_model=SkillListResponse)
async def list_skills(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    type: str = Query(None, alias="type", description="按类型筛选"),
    search: str = Query(None, description="搜索关键词"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 Skill 列表（分页 + 类型筛选 + 搜索）"""
    skills, total = await skill_service.list_skills(
        db=db,
        page=page,
        page_size=page_size,
        type_filter=type,
        search=search,
    )

    # 为每个 Skill 计算绑定的 Agent 数量
    items = []
    for skill in skills:
        agents_count = await skill_service.get_skill_agents_count(db, skill.id)
        items.append(skill_service.skill_to_response(skill, agents_count))

    return SkillListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=SkillResponse, status_code=201)
async def create_skill(
    data: SkillCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建新的 Skill"""
    skill = await skill_service.create_skill(db, data)
    return skill_service.skill_to_response(skill, agents_count=0)


@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 Skill 详情"""
    skill = await skill_service.get_skill(db, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    agents_count = await skill_service.get_skill_agents_count(db, skill_id)
    return skill_service.skill_to_response(skill, agents_count)


@router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: str,
    data: SkillUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新 Skill 配置"""
    skill = await skill_service.update_skill(db, skill_id, data)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    agents_count = await skill_service.get_skill_agents_count(db, skill_id)
    return skill_service.skill_to_response(skill, agents_count)


@router.delete("/{skill_id}", status_code=204)
async def delete_skill(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除 Skill（同时清理关联绑定）"""
    success = await skill_service.delete_skill(db, skill_id)
    if not success:
        raise HTTPException(status_code=404, detail="Skill not found")
    return None


@router.patch("/{skill_id}/toggle", response_model=SkillResponse)
async def toggle_skill(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """启用/停用 Skill"""
    skill = await skill_service.toggle_skill(db, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    agents_count = await skill_service.get_skill_agents_count(db, skill_id)
    return skill_service.skill_to_response(skill, agents_count)


@router.post("/{skill_id}/bind", response_model=dict, status_code=201)
async def bind_skill(
    skill_id: str,
    data: SkillBindRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """将 Skill 绑定到 Agent"""
    binding = await skill_service.bind_skill_to_agent(
        db, skill_id, data.agent_id, config=data.config
    )
    if not binding:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {
        "id": binding.id,
        "skill_id": binding.skill_id,
        "agent_id": binding.agent_id,
        "message": "Skill bound to agent successfully",
    }


@router.delete("/{skill_id}/bind/{agent_id}", status_code=204)
async def unbind_skill(
    skill_id: str,
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """解绑 Skill 与 Agent"""
    success = await skill_service.unbind_skill_from_agent(db, skill_id, agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="Binding not found")
    return None
