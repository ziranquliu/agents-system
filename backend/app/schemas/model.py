"""
模型配置模板 Schema
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ModelConfigCreate(BaseModel):
    """创建模型配置模板"""
    name: str = Field(..., min_length=1, max_length=100)
    provider: str = Field(..., description="Provider: openai, ollama, deepseek, glm, qwen")
    model_name: str = Field(..., min_length=1)
    endpoint: Optional[str] = None
    api_key: Optional[str] = Field(None, description="敏感字段，响应中自动隐藏")
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    context_window: Optional[int] = None
    embedding_model: Optional[str] = None
    is_default: bool = False
    description: Optional[str] = None


class ModelConfigUpdate(BaseModel):
    """更新模型配置模板"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    provider: Optional[str] = None
    model_name: Optional[str] = None
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    context_window: Optional[int] = None
    embedding_model: Optional[str] = None
    is_default: Optional[bool] = None
    description: Optional[str] = None


class ModelConfigResponse(BaseModel):
    """模型配置模板响应（API Key 脱敏）"""
    id: str
    name: str
    provider: str
    model_name: str
    endpoint: Optional[str] = None
    api_key_masked: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    context_window: Optional[int] = None
    embedding_model: Optional[str] = None
    is_default: bool = False
    description: Optional[str] = None
    created_by: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ModelTestRequest(BaseModel):
    """模型测试请求"""
    messages: Optional[list[dict]] = Field(
        None,
        description="测试消息，默认使用 'Say hello'"
    )


class ModelTestResponse(BaseModel):
    """模型测试响应"""
    success: bool
    response: Optional[str] = None
    model: Optional[str] = None
    latency_ms: Optional[int] = None
    error: Optional[str] = None
