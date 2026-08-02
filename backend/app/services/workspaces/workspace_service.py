import uuid
from typing import Optional
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.workspace import Workspace, WorkspaceMember
from app.models.user import User
from app.models.agent import Agent
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate

"""工作区服务 - CRUD 操作与成员管理"""




# ── 瞬态属性填充 ──────────────────────────────────────────


async def _attach_owner_names(db: AsyncSession, workspaces: list[Workspace]) -> None:
    """批量填充 owner_name 和 agent_count 到工作区对象（瞬态属性）"""
    if not workspaces:
        return

    # owner_name
    owner_ids = list(set(w.owner_id for w in workspaces if w.owner_id))
    if owner_ids:
        result = await db.execute(
            select(User.id, User.display_name).where(User.id.in_(owner_ids))
        )
        owner_map = dict(result.all())
        for ws in workspaces:
            ws.owner_name = owner_map.get(ws.owner_id)

    # agent_count
    ws_ids = [w.id for w in workspaces]
    if ws_ids:
        count_result = await db.execute(
            select(Agent.workspace_id, func.count(Agent.id))
            .where(Agent.workspace_id.in_(ws_ids))
            .group_by(Agent.workspace_id)
        )
        agent_counts = dict(count_result.all())
        for ws in workspaces:
            ws.agent_count = agent_counts.get(ws.id, 0)

    # member_count — use stored column value
    for ws in workspaces:
        ws.member_count = ws.member_count or 0


async def _attach_usernames(db: AsyncSession, members: list[WorkspaceMember]) -> None:
    """批量填充 username 到成员对象（瞬态属性）"""
    if not members:
        return
    user_ids = list(set(m.user_id for m in members if m.user_id))
    if not user_ids:
        return
    result = await db.execute(
        select(User.id, User.username).where(User.id.in_(user_ids))
    )
    user_map = dict(result.all())
    for m in members:
        m.username = user_map.get(m.user_id)


# ── 工作区 CRUD ────────────────────────────────────────────


async def list_workspaces(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    user_id: Optional[str] = None,
) -> tuple[list[Workspace], int]:
    """获取工作区列表（分页 + 搜索），用户作为所有者或成员可见"""
    # 用户可访问的工作区 ID（至少是所有者或成员）
    accessible_ids = set()
    if user_id:
        # 作为所有者
        owner_q = select(Workspace.id).where(Workspace.owner_id == user_id)
        owner_result = await db.execute(owner_q)
        accessible_ids.update(row[0] for row in owner_result.all())

        # 作为成员
        member_q = select(WorkspaceMember.workspace_id).where(
            WorkspaceMember.user_id == user_id
        )
        member_result = await db.execute(member_q)
        accessible_ids.update(row[0] for row in member_result.all())

    query = select(Workspace)

    if accessible_ids is not None:
        query = query.where(Workspace.id.in_(accessible_ids))

    if search:
        query = query.where(Workspace.name.ilike(f"%{search}%"))

    # 总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页
    query = query.order_by(Workspace.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    workspaces = list(result.scalars().all())

    await _attach_owner_names(db, workspaces)

    return workspaces, total


async def get_workspace(db: AsyncSession, workspace_id: str) -> Optional[Workspace]:
    """根据 ID 获取工作区详情"""
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()
    if workspace:
        await _attach_owner_names(db, [workspace])
    return workspace


async def create_workspace(
    db: AsyncSession,
    data: WorkspaceCreate,
    user_id: str,
) -> Workspace:
    """创建工作区，自动将创建者添加为 owner 成员"""
    workspace = Workspace(
        id=str(uuid.uuid4()),
        name=data.name,
        description=data.description,
        owner_id=user_id,
        member_count=1,
        is_active=True,
    )
    db.add(workspace)
    await db.flush()

    # 自动添加创建者为 owner 成员
    member = WorkspaceMember(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        user_id=user_id,
        role="owner",
    )
    db.add(member)
    await db.flush()

    await _attach_owner_names(db, [workspace])
    return workspace


async def update_workspace(
    db: AsyncSession,
    workspace_id: str,
    data: WorkspaceUpdate,
) -> Optional[Workspace]:
    """更新工作区信息"""
    workspace = await get_workspace(db, workspace_id)
    if not workspace:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(workspace, field, value)

    await db.flush()
    return workspace


async def delete_workspace(db: AsyncSession, workspace_id: str) -> bool:
    """删除工作区（硬删除 + 关联成员）"""
    workspace = await get_workspace(db, workspace_id)
    if not workspace:
        return False

    # 删除所有关联成员
    await db.execute(
        delete(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id)
    )
    await db.delete(workspace)
    await db.flush()
    return True


# ── 成员管理 ────────────────────────────────────────────────


async def list_members(
    db: AsyncSession,
    workspace_id: str,
) -> tuple[list[WorkspaceMember], int]:
    """获取工作区成员列表"""
    query = (
        select(WorkspaceMember)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.joined_at.asc())
    )

    result = await db.execute(query)
    members = list(result.scalars().all())

    total = len(members)
    await _attach_usernames(db, members)

    return members, total


async def add_member(
    db: AsyncSession,
    workspace_id: str,
    user_id: str,
    role: str,
) -> Optional[WorkspaceMember]:
    """添加成员到工作区"""
    # 验证工作区存在
    workspace = await get_workspace(db, workspace_id)
    if not workspace:
        return None

    # 检查是否已经是成员
    existing = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    if existing.scalar_one_or_none():
        return None  # 已经是成员

    member = WorkspaceMember(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        user_id=user_id,
        role=role,
    )
    db.add(member)

    # 更新 member_count
    workspace.member_count = (workspace.member_count or 0) + 1

    await db.flush()
    await _attach_usernames(db, [member])
    return member


async def update_member_role(
    db: AsyncSession,
    workspace_id: str,
    user_id: str,
    new_role: str,
) -> Optional[WorkspaceMember]:
    """更新成员角色"""
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        return None

    member.role = new_role
    await db.flush()
    await _attach_usernames(db, [member])
    return member


async def remove_member(
    db: AsyncSession,
    workspace_id: str,
    user_id: str,
) -> bool:
    """从工作区移除成员"""
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        return False

    # 不能移除所有者
    if member.role == "owner":
        return False

    await db.delete(member)

    # 更新 member_count
    workspace = await get_workspace(db, workspace_id)
    if workspace:
        workspace.member_count = max(0, (workspace.member_count or 1) - 1)

    await db.flush()
    return True
