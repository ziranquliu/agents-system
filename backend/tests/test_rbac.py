"""
API集成测试 - RBAC权限控制
"""
import pytest
from fastapi.testclient import TestClient

from app.models.user import User


@pytest.fixture
async def admin_user(db):
    """创建管理员用户"""
    user = User(
        id="admin-001",
        username="admin",
        email="admin@test.com",
        hashed_password="hashed_password",
        role="admin",
        is_active=True
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
async def editor_user(db):
    """创建编辑用户"""
    user = User(
        id="editor-001",
        username="editor",
        email="editor@test.com",
        hashed_password="hashed_password",
        role="editor",
        is_active=True
    )
    db.add(user)
    db.commit()
    return user
def test_admin_can_access_all(admin_client: TestClient):
    """测试管理员可以访问所有接口"""
    # Agent管理
    response = admin_client.get("/api/v1/agents")
    assert response.status_code == 200
    
    # 创建工作空间
    response = admin_client.post(
        "/api/v1/workspaces",
        json={"name": "Test Workspace"},
        headers={"Authorization": "Bearer admin_token"}
    )
    assert response.status_code in [200, 201]
def test_editor_can_create_agent(editor_client: TestClient):
    """测试编辑用户可以创建Agent"""
    response = editor_client.post(
        "/api/v1/agents",
        json={
            "name": "Test Agent",
            "description": "测试Agent"
        },
        headers={"Authorization": "Bearer editor_token"}
    )
    assert response.status_code in [200, 201]
def test_viewer_cannot_modify(viewer_client: TestClient):
    """测试查看者不能修改数据"""
    # 尝试创建Agent
    response = viewer_client.post(
        "/api/v1/agents",
        json={"name": "Test Agent"},
        headers={"Authorization": "Bearer viewer_token"}
    )
    assert response.status_code == 403
def test_workspace_isolation(client: TestClient, admin_user: User):
    """测试工作空间隔离"""
    # 作为管理员，可以访问所有工作空间
    response = client.get("/api/v1/workspaces")
    assert response.status_code == 200
