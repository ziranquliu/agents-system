"""
RBAC权限中间件
基于角色的访问控制，支持工作空间级别权限隔离
"""
from functools import wraps
from typing import List, Optional, Callable
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User, Role
from app.models.workspace import WorkspaceMember
from app.api.v1.auth import get_current_user


class RoleChecker:
    """角色检查器"""
    
    def __init__(self, required_roles: List[str]):
        self.required_roles = required_roles
    
    async def __call__(self, user: User = Depends(get_current_user)) -> User:
        """检查用户角色"""
        if user.role in self.required_roles:
            return user
        
        raise HTTPException(
            status_code=403,
            detail=f"需要以下角色之一: {', '.join(self.required_roles)}"
        )


class WorkspacePermissionChecker:
    """工作空间权限检查器"""
    
    def __init__(
        self, 
        required_roles: List[str],
        resource_owner: bool = False,
        admin_override: bool = True
    ):
        """
        Args:
            required_roles: 允许的角色列表
            resource_owner: 资源所有者是否可访问
            admin_override: admin角色是否有权访问所有资源
        """
        self.required_roles = required_roles
        self.resource_owner = resource_owner
        self.admin_override = admin_override
    
    async def check(
        self,
        request: Request,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        """检查工作空间权限"""
        
        # Admin权限检查
        if self.admin_override and current_user.role == "admin":
            return current_user
        
        # 获取工作空间ID
        workspace_id = request.path_params.get("workspace_id") or \
                      request.query_params.get("workspace_id")
        
        if not workspace_id:
            # 无工作空间ID的资源（如全局配置），只需角色检查
            if current_user.role in self.required_roles:
                return current_user
            raise HTTPException(status_code=403, detail="权限不足")
        
        # 检查工作空间成员关系
        member_result = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == current_user.id
            )
        )
        member = member_result.scalar_one_or_none()
        
        if not member:
            raise HTTPException(
                status_code=403,
                detail="您不是该工作空间的成员"
            )
        
        # 检查成员角色
        allowed_member_roles = ["owner", "admin", "editor", "viewer"]
        if member.role not in allowed_member_roles:
            raise HTTPException(status_code=403, detail="角色权限不足")
        
        return current_user


# 快捷创建函数
def require_role(*roles: str):
    """装饰器：要求特定角色"""
    checker = RoleChecker(list(roles))
    return checker


def require_workspace_permission(
    roles: List[str] = None,
    resource_owner: bool = False,
    admin_override: bool = True
):
    """装饰器：检查工作空间权限"""
    if roles is None:
        roles = ["admin", "editor"]
    
    checker = WorkspacePermissionChecker(roles, resource_owner, admin_override)
    return checker.check


# 常用权限组合
class PermissionLevels:
    """预定义的权限级别"""
    
    @staticmethod
    def reader():
        """只读权限"""
        return require_workspace_permission(roles=["viewer", "editor", "admin"])
    
    @staticmethod
    def editor():
        """编辑权限"""
        return require_workspace_permission(roles=["editor", "admin"])
    
    @staticmethod
    def admin():
        """管理员权限"""
        return require_workspace_permission(roles=["admin"])
    
    @staticmethod
    def owner():
        """拥有者权限"""
        return require_workspace_permission(roles=["owner", "admin"])
    
    @staticmethod
    def global_admin():
        """全局管理员（无需工作空间）"""
        return require_role("admin")


# 使用示例
"""
from app.core.rbac import PermissionLevels

@router.get("/agents")
@PermissionLevels.reader()
async def list_agents(...):
    ...

@router.post("/agents")
@PermissionLevels.editor()
async def create_agent(...):
    ...

@router.delete("/agents/{id}")
@PermissionLevels.owner()
async def delete_agent(...):
    ...
"""
