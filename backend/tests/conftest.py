"""
测试配置 - conftest.py 增强版
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from app.main import app
from app.db.session import get_db
from app.models.user import User


# 测试数据库引擎
TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost/test_db"


@pytest_asyncio.fixture
async def db_session():
    """创建测试数据库会话"""
    # 在实际测试中，这里应该使用内存数据库或测试专用数据库
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.close = AsyncMock()
    return mock_db


@pytest_asyncio.fixture
async def client(db_session):
    """创建测试客户端"""
    # 覆盖数据库依赖
    app.dependency_overrides[get_db] = lambda: db_session
    
    test_client = TestClient(app)
    return test_client


@pytest_asyncio.fixture
async def admin_client(db_session):
    """创建管理员测试客户端"""
    app.dependency_overrides[get_db] = lambda: db_session
    
    test_client = TestClient(app)
    # 添加管理员认证头
    test_client.headers["Authorization"] = "Bearer admin_token"
    return test_client


@pytest_asyncio.fixture
async def editor_client(db_session):
    """创建编辑者测试客户端"""
    app.dependency_overrides[get_db] = lambda: db_session
    
    test_client = TestClient(app)
    test_client.headers["Authorization"] = "Bearer editor_token"
    return test_client


@pytest_asyncio.fixture
async def viewer_client(db_session):
    """创建查看者测试客户端"""
    app.dependency_overrides[get_db] = lambda: db_session
    
    test_client = TestClient(app)
    test_client.headers["Authorization"] = "Bearer viewer_token"
    return test_client


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


# 通用测试数据
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
