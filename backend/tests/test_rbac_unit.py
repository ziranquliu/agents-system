"""
单元测试 - RBAC权限系统
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

try:
    from fastapi import HTTPException
except ImportError:
    HTTPException = None

try:
    from app.core.rbac import RoleChecker, WorkspacePermissionChecker, PermissionLevels
    from app.models.user import User
except ImportError:
    pytest.skip("缺少依赖", allow_module_level=True)


@pytest.fixture
def admin_user():
    """创建管理员用户"""
    return User(
        id="admin-001",
        username="admin",
        role="admin",
        is_active=True
    )


@pytest.fixture
def editor_user():
    """创建编辑用户"""
    return User(
        id="editor-001",
        username="editor",
        role="editor",
        is_active=True
    )


@pytest.fixture
def viewer_user():
    """创建查看用户"""
    return User(
        id="viewer-001",
        username="viewer",
        role="viewer",
        is_active=True
    )
def test_admin_role_checker(admin_user):
    """测试管理员角色检查"""
    checker = RoleChecker(["admin", "editor"])
    result = checker(admin_user)
    assert result.role == "admin"
def test_editor_role_checker(admin_user, editor_user):
    """测试编辑者角色检查"""
    checker = RoleChecker(["admin", "editor"])
    
    # admin可以通过
    result = checker(admin_user)
    assert result.role == "admin"
    
    # editor也可以通过
    result = checker(editor_user)
    assert result.role == "editor"
def test_viewer_rejected(viewer_user):
    """测试查看者被拒绝"""
    checker = RoleChecker(["admin", "editor"])
    
    with pytest.raises(HTTPException) as exc_info:
        checker(viewer_user)
    
    assert exc_info.value.status_code == 403
def test_workspace_permission_checker():
    """测试工作空间权限检查"""
    checker = WorkspacePermissionChecker(
        required_roles=["editor", "admin"],
        admin_override=True
    )
    
    # Mock request and user
    mock_request = MagicMock()
    mock_request.path_params = {"workspace_id": "ws-001"}
    mock_request.query_params = {}
    
    mock_user = User(id="admin-001", role="admin", is_active=True)
    
    # Mock database
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    # Admin should pass even without member
    result = checker.check(mock_request, mock_user, mock_db)
    assert result.role == "admin"
def test_permission_levels():
    """测试权限级别定义"""
    assert PermissionLevels.reader is not None
    assert PermissionLevels.editor is not None
    assert PermissionLevels.admin is not None
    assert PermissionLevels.owner is not None
def test_workspace_member_check():
    """测试工作空间成员检查"""
    checker = WorkspacePermissionChecker(
        required_roles=["viewer", "editor", "admin"]
    )
    
    mock_request = MagicMock()
    mock_request.path_params = {"workspace_id": "ws-001"}
    mock_request.query_params = {}
    
    mock_user = User(id="user-001", role="editor", is_active=True)
    mock_member = MagicMock()
    mock_member.role = "editor"
    
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_member
    mock_db.execute.return_value = mock_result
    
    result = checker.check(mock_request, mock_user, mock_db)
    assert result.id == "user-001"
def test_non_member_rejected():
    """测试非成员被拒绝"""
    checker = WorkspacePermissionChecker(
        required_roles=["viewer", "editor", "admin"]
    )
    
    mock_request = MagicMock()
    mock_request.path_params = {"workspace_id": "ws-001"}
    
    mock_user = User(id="user-001", role="editor", is_active=True)
    
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None  # 非成员
    mock_db.execute.return_value = mock_result
    
    with pytest.raises(HTTPException) as exc_info:
        checker.check(mock_request, mock_user, mock_db)
    
    assert exc_info.value.status_code == 403
