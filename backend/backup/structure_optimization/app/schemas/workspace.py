"""工作区 Pydantic Schema - 请求/响应数据模型"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class WorkspaceCreate(BaseModel):
    """创建工作区请求"""
    name: str = Field(..., min_length=1, max_length=100, description="工作区名称")
    description: Optional[str] = Field(None, max_length=500, description="工作区描述")


class WorkspaceUpdate(BaseModel):
    """更新工作区请求（所有字段可选）"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="新名称")
    description: Optional[str] = Field(None, max_length=500, description="新描述")
    is_active: Optional[bool] = None


class WorkspaceResponse(BaseModel):
    """工作区信息响应"""
    id: str
    name: str
    description: Optional[str] = None
    owner_id: str
    owner_name: Optional[str] = None
    is_active: bool = True
    agent_count: int = 0
    member_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WorkspaceListResponse(BaseModel):
    """工作区列表响应（分页）"""
    items: list[WorkspaceResponse]
    total: int
    page: int
    page_size: int


class WorkspaceMemberResponse(BaseModel):
    """工作区成员响应"""
    id: str
    workspace_id: str
    user_id: str
    username: Optional[str] = None
    role: str = "member"
    joined_at: datetime

    model_config = {"from_attributes": True}


class MemberListResponse(BaseModel):
    """成员列表响应"""
    items: list[WorkspaceMemberResponse]
    total: int


class AddMemberRequest(BaseModel):
    """添加成员请求"""
    user_id: str = Field(..., description="用户 ID")
    role: str = Field("member", pattern=r"^(admin|member|viewer)$", description="角色")


class UpdateMemberRoleRequest(BaseModel):
    """更新成员角色请求"""
    role: str = Field(..., pattern=r"^(admin|member|viewer)$", description="新角色")
