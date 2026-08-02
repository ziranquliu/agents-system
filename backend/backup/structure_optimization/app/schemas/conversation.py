"""对话历史 Pydantic Schema - 请求/响应数据模型"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    """创建对话请求"""
    title: str = Field(..., min_length=1, max_length=200, description="对话标题")
    agent_id: str = Field(..., description="关联的 Agent ID")


class ConversationUpdate(BaseModel):
    """更新对话请求（所有字段可选）"""
    title: Optional[str] = Field(None, min_length=1, max_length=200, description="新标题")


class ConversationResponse(BaseModel):
    """对话信息响应"""
    id: str
    title: Optional[str] = None
    agent_id: str
    agent_name: Optional[str] = None
    status: str = "active"
    message_count: int = 0
    total_tokens: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ConversationListResponse(BaseModel):
    """对话列表响应（分页）"""
    items: list[ConversationResponse]
    total: int
    page: int
    page_size: int


class MessageCreate(BaseModel):
    """创建消息请求"""
    model_config = {"protected_namespaces": ()}

    role: str = Field(
        ...,
        pattern=r"^(user|assistant|system|tool)$",
        description="消息角色",
    )
    content: str = Field(..., min_length=1, description="消息内容")
    tokens: Optional[int] = 0
    model_name: Optional[str] = None
    metadata: Optional[dict] = None


class MessageResponse(BaseModel):
    """消息响应"""
    model_config = {"from_attributes": True, "protected_namespaces": ()}
    id: str
    conversation_id: str
    role: str
    content: str
    tokens: int = 0
    model_name: Optional[str] = None
    created_at: datetime


class MessageListResponse(BaseModel):
    """消息列表响应（分页）"""
    items: list[MessageResponse]
    total: int
    page: int
    page_size: int


class ConversationStatsResponse(BaseModel):
    """对话统计响应"""
    total_conversations: int
    total_tokens: int
