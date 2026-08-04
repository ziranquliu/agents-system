"""
测试配置 - conftest.py
"""
import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.db.session import get_db


@pytest.fixture
def db_session():
    """创建测试数据库会话（mock）"""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.close = AsyncMock()
    return mock_db


@pytest.fixture
def client(db_session):
    """创建测试客户端（不触发 lifespan，避免连接真实 DB）"""
    app.dependency_overrides[get_db] = lambda: db_session
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def admin_client(db_session):
    """创建管理员测试客户端"""
    app.dependency_overrides[get_db] = lambda: db_session
    c = TestClient(app, raise_server_exceptions=False)
    c.headers["Authorization"] = "Bearer admin_token"
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def editor_client(db_session):
    """创建编辑者测试客户端"""
    app.dependency_overrides[get_db] = lambda: db_session
    c = TestClient(app, raise_server_exceptions=False)
    c.headers["Authorization"] = "Bearer editor_token"
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def viewer_client(db_session):
    """创建查看者测试客户端"""
    app.dependency_overrides[get_db] = lambda: db_session
    c = TestClient(app, raise_server_exceptions=False)
    c.headers["Authorization"] = "Bearer viewer_token"
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    """默认认证头（admin 角色）"""
    from app.services.auth_service import create_access_token
    token, _ = create_access_token(user_id="test-user-001", username="tester", role="admin")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def encryption_service():
    """创建加密服务实例"""
    from app.core.encryption import EncryptionHelper
    return EncryptionHelper()


@pytest.fixture
def cache_manager():
    """创建缓存管理器"""
    from app.core.cache import CacheManager
    return CacheManager()


@pytest.fixture
def sample_agent():
    """样本Agent数据"""
    return {
        "name": "测试Agent",
        "description": "这是一个测试用的Agent",
        "system_prompt": "你是一个助手",
        "model_provider": "openai",
        "model_name": "gpt-4",
        "workspace_id": "ws-test-001"
    }


@pytest.fixture
def sample_template():
    """样本模型模板数据"""
    return {
        "name": "GPT-4 模板",
        "provider": "openai",
        "model_name": "gpt-4",
        "temperature": 0.7,
        "max_tokens": 2048,
        "is_default": False
    }


@pytest.fixture
def sample_conversation():
    """样本对话数据"""
    return {
        "title": "测试对话",
        "agent_id": "agent-001",
        "user_id": "user-001",
        "workspace_id": "ws-test-001"
    }
