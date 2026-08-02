"""技能 Pydantic Schema - 请求/响应数据模型"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SkillCreate(BaseModel):
    """创建 Skill 请求"""
    name: str = Field(..., min_length=1, max_length=100)
    type: Optional[str] = "tool"  # tool | skill | plugin
    version: str = "1.0.0"
    category: Optional[str] = None  # analysis | search | code | etc.
    description: Optional[str] = None
    enabled: bool = True
    config: Optional[dict] = None  # 技能配置参数，存储为 parameters JSON


class SkillUpdate(BaseModel):
    """更新 Skill 请求（所有字段可选）"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    type: Optional[str] = None
    version: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None
    config: Optional[dict] = None


class SkillResponse(BaseModel):
    """Skill 信息响应"""
    id: str
    name: str
    type: Optional[str] = None
    version: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    status: str  # "active" | "inactive"，由 enabled 字段派生
    agents_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class SkillListResponse(BaseModel):
    """Skill 列表响应（分页）"""
    items: list[SkillResponse]
    total: int
    page: int
    page_size: int


class SkillBindRequest(BaseModel):
    """绑定 Agent 请求"""
    agent_id: str = Field(..., description="目标 Agent ID")
    config: Optional[dict] = None  # 技能特定配置
