"""
API集成测试 - 模型版本管理
"""
import pytest
try:
    from fastapi.testclient import TestClient
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.main import app
    from app.db.session import get_db
    from app.models.agent import ModelConfigTemplate
    from app.models.user import User
except (ImportError, ModuleNotFoundError):
    pytest.skip("缺少依赖", allow_module_level=True)


@pytest.fixture
def test_user(db: AsyncSession):
    """创建测试用户"""
    user = User(
        id="test-user-001",
        username="testuser",
        email="test@example.com",
        hashed_password="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36PQm3iV8jEGH3Nm1 eOyHqG",
        role="admin",
        is_active=True
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def test_template(db: AsyncSession, test_user: User):
    """创建测试模板"""
    template = ModelConfigTemplate(
        id="test-template-001",
        name="Test GPT-4",
        provider="openai",
        model="gpt-4",
        config='{"temperature": 0.7, "max_tokens": 2048}',
        description="测试模板",
        created_by=test_user.id,
        workspace_id="ws-test-001"
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template
def test_list_versions(client: TestClient, test_template: ModelConfigTemplate):
    """测试版本列表查询"""
    response = client.get(
        f"/api/v1/model-templates/{test_template.id}/versions",
        headers={"Authorization": "Bearer dummy_token"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
def test_rollback_to_version(client: TestClient, test_template: ModelConfigTemplate):
    """测试版本回滚"""
    # 先创建一个新版本
    version_response = client.post(
        f"/api/v1/model-templates/{test_template.id}/versions",
        json={
            "version": 2,
            "config": '{"temperature": 0.5}'
        },
        headers={"Authorization": "Bearer dummy_token"}
    )
    
    # 执行回滚
    rollback_response = client.post(
        f"/api/v1/model-templates/{test_template.id}/rollback",
        json={"target_version": 1},
        headers={"Authorization": "Bearer dummy_token"}
    )
    
    assert rollback_response.status_code == 200
    data = rollback_response.json()
    assert data["success"] is True
def test_list_bound_agents(client: TestClient, test_template: ModelConfigTemplate):
    """测试绑定Agent列表查询"""
    response = client.get(
        f"/api/v1/model-templates/{test_template.id}/bound-agents",
        headers={"Authorization": "Bearer dummy_token"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
def test_trigger_sync(client: TestClient, test_template: ModelConfigTemplate):
    """测试触发同步"""
    response = client.post(
        f"/api/v1/model-templates/{test_template.id}/sync",
        headers={"Authorization": "Bearer dummy_token"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "synced" in data
    assert "failed" in data
