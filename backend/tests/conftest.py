"""
测试配置 - conftest.py

测试套件使用同步 TestClient + mock DB。需要覆盖三个关键依赖：
1. get_db → mock AsyncSession（execute 返回 mock Result）
2. get_current_user → 返回 mock User（避免 JWT + DB 查询链）
3. security HTTPBearer → 接受任何 token
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.db.session import get_db
from app.services.auth_service import get_current_user


def _make_mock_result(scalar_result=None, scalars_result=None):
    """构造 mock Result，模拟 SQLAlchemy execute 返回值

    同时支持 scalar()（count 查询用）和 scalar_one_or_none()（单行查询用）
    以及 scalars().all()（列表查询用）。
    """
    mock_result = MagicMock()
    mock_result.scalar.return_value = scalar_result
    mock_result.scalar_one_or_none.return_value = scalar_result
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = scalars_result or []
    mock_result.scalars.return_value = mock_scalars
    return mock_result


@pytest.fixture
def db_session():
    """创建 mock AsyncSession（execute 返回 mock Result）"""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.execute = AsyncMock(return_value=_make_mock_result())
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.close = AsyncMock()
    return mock_db


@pytest.fixture
def mock_user():
    """构造 mock User 对象"""
    user = MagicMock()
    user.id = "test-user-001"
    user.username = "tester"
    user.email = "tester@test.com"
    user.role = "admin"
    user.is_active = True
    user.workspace_id = "ws-test-001"
    return user


@pytest.fixture
def auth_dependency(mock_user):
    """覆盖 get_current_user 依赖，返回 mock User"""
    async def _get_current_user():
        return mock_user
    return _get_current_user


@pytest.fixture
def client(db_session, auth_dependency):
    """创建测试客户端（覆盖 DB + 鉴权依赖）"""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = auth_dependency
    c = TestClient(app, raise_server_exceptions=False)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def admin_client(db_session, auth_dependency):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = auth_dependency
    c = TestClient(app, raise_server_exceptions=False)
    c.headers["Authorization"] = "Bearer admin_token"
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def editor_client(db_session, auth_dependency):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = auth_dependency
    c = TestClient(app, raise_server_exceptions=False)
    c.headers["Authorization"] = "Bearer editor_token"
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def viewer_client(db_session, auth_dependency):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = auth_dependency
    c = TestClient(app, raise_server_exceptions=False)
    c.headers["Authorization"] = "Bearer viewer_token"
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    """默认认证头"""
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def encryption_service():
    from app.core.encryption import EncryptionHelper
    return EncryptionHelper()


@pytest.fixture
def cache_manager():
    from app.core.cache import CacheManager
    return CacheManager()


@pytest.fixture
def sample_agent():
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
    return {
        "title": "测试对话",
        "agent_id": "agent-001",
        "user_id": "user-001",
        "workspace_id": "ws-test-001"
    }
