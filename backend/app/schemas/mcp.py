"""MCP Server Pydantic Schema - 请求/响应数据模型"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class MCPServerCreate(BaseModel):
    """创建 MCP Server 请求"""
    name: str = Field(..., min_length=1, max_length=100, description="服务名称")
    endpoint: str = Field(..., max_length=500, description="服务端点 URL")
    protocol: str = Field("sse", pattern=r"^(sse|stdio|streamable-http)$", description="通信协议")
    api_key: Optional[str] = Field(None, description="API 密钥")
    description: Optional[str] = None
    config: Optional[dict] = None  # JSON: 完整配置


class MCPServerUpdate(BaseModel):
    """更新 MCP Server 请求（所有字段可选）"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    endpoint: Optional[str] = Field(None, max_length=500)
    protocol: Optional[str] = Field(None, pattern=r"^(sse|stdio|streamable-http)$")
    api_key: Optional[str] = None
    description: Optional[str] = None
    config: Optional[dict] = None


class MCPServerResponse(BaseModel):
    """MCP Server 信息响应"""
    id: str
    name: str
    endpoint: str
    protocol: str
    status: str  # online | offline | error
    health_status: str  # healthy | unhealthy | unknown
    version: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MCPServerListResponse(BaseModel):
    """MCP Server 列表响应（分页）"""
    items: list[MCPServerResponse]
    total: int
    page: int
    page_size: int


class MCPServerStatusUpdate(BaseModel):
    """状态变更请求"""
    status: str = Field(..., pattern=r"^(online|offline|error)$")
