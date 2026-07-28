"""
Agent Pydantic Schema - 请求/响应数据模型
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    """创建 Agent 请求"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    avatar: Optional[str] = None
    system_prompt: Optional[str] = None
    welcome_message: Optional[str] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    model_config_template_id: Optional[str] = None
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 4096
    context_window: Optional[int] = 8192
    enabled_skills: Optional[list[str]] = None
    enabled_mcp_servers: Optional[list[str]] = None
    workspace_id: Optional[str] = None
    status: str = "draft"


class AgentUpdate(BaseModel):
    """更新 Agent 请求（所有字段可选）"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    avatar: Optional[str] = None
    system_prompt: Optional[str] = None
    welcome_message: Optional[str] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    model_config_template_id: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    context_window: Optional[int] = None
    enabled_skills: Optional[list[str]] = None
    enabled_mcp_servers: Optional[list[str]] = None


class AgentResponse(BaseModel):
    """Agent 信息响应"""
    id: str
    name: str
    description: Optional[str] = None
    avatar: Optional[str] = None
    status: str
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    model_config_template_id: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    context_window: Optional[int] = None
    system_prompt: Optional[str] = None
    welcome_message: Optional[str] = None
    enabled_skills: Optional[str] = None
    enabled_mcp_servers: Optional[str] = None
    workspace_id: Optional[str] = None
    created_by: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AgentListResponse(BaseModel):
    """Agent 列表响应（分页）"""
    items: list[AgentResponse]
    total: int
    page: int
    page_size: int


class AgentStatusUpdate(BaseModel):
    """状态变更请求"""
    status: str = Field(..., pattern=r"^(draft|running|stopped|error|archived)$")
