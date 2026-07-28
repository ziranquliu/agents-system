"""工作区管理 API — 完整的 CRUD + 成员管理"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceResponse,
    WorkspaceListResponse,
    WorkspaceMemberResponse,
    MemberListResponse,
    AddMemberRequest,
    UpdateMemberRoleRequest,
)
from app.services.auth_service import get_current_user
from app.services import workspace_service

router = APIRouter()


# ──────────────────────────────────────────
# 工作区 CRUD
# ──────────────────────────────────────────


@router.get("/", response_model=WorkspaceListResponse)
async def list_workspaces(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    search: str = Query(None, description="搜索工作区名称"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取工作区列表（分页 + 搜索），仅返回用户有权限的工作区"""
    workspaces, total = await workspace_service.list_workspaces(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        user_id=current_user.id,
    )
    return WorkspaceListResponse(
        items=[WorkspaceResponse.model_validate(ws) for ws in workspaces],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    data: WorkspaceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建工作区（自动将创建者添加为 owner 成员）"""
    workspace = await workspace_service.create_workspace(
        db=db,
        data=data,
        user_id=current_user.id,
    )
    return WorkspaceResponse.model_validate(workspace)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取工作区详情"""
    workspace = await workspace_service.get_workspace(db, workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceResponse.model_validate(workspace)


@router.put("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    data: WorkspaceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新工作区信息"""
    workspace = await workspace_service.update_workspace(db, workspace_id, data)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceResponse.model_validate(workspace)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除工作区（硬删除 + 关联成员）"""
    success = await workspace_service.delete_workspace(db, workspace_id)
    if not success:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return None


# ──────────────────────────────────────────
# 成员管理
# ──────────────────────────────────────────


@router.get("/{workspace_id}/members", response_model=MemberListResponse)
async def list_members(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取工作区成员列表"""
    members, total = await workspace_service.list_members(db, workspace_id)
    return MemberListResponse(
        items=[WorkspaceMemberResponse.model_validate(m) for m in members],
        total=total,
    )


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    workspace_id: str,
    data: AddMemberRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """添加成员到工作区"""
    member = await workspace_service.add_member(
        db=db,
        workspace_id=workspace_id,
        user_id=data.user_id,
        role=data.role,
    )
    if not member:
        raise HTTPException(
            status_code=409,
            detail="Member already exists or workspace not found",
        )
    return WorkspaceMemberResponse.model_validate(member)


@router.put(
    "/{workspace_id}/members/{target_user_id}",
    response_model=WorkspaceMemberResponse,
)
async def update_member_role(
    workspace_id: str,
    target_user_id: str,
    data: UpdateMemberRoleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """修改成员角色"""
    member = await workspace_service.update_member_role(
        db=db,
        workspace_id=workspace_id,
        user_id=target_user_id,
        new_role=data.role,
    )
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return WorkspaceMemberResponse.model_validate(member)


@router.delete(
    "/{workspace_id}/members/{target_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    workspace_id: str,
    target_user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从工作区移除成员（不能移除 owner）"""
    success = await workspace_service.remove_member(
        db=db,
        workspace_id=workspace_id,
        user_id=target_user_id,
    )
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Cannot remove owner or member not found",
        )
    return None
