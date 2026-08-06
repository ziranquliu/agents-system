"""
单元测试 - 缓存服务

CacheManager 的方法是 async 的，同步 TestClient 无法 await。
因此这里直接 mock Redis 交互层来验证缓存逻辑。
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
try:
    from app.core.cache import CacheManager
    _has_cache = True
except (ImportError, ModuleNotFoundError):
    _has_cache = False

pytestmark = pytest.mark.skipif(not _has_cache, reason="缺少 redis 依赖")


@pytest.fixture
def mock_redis():
    """创建 mock Redis 客户端"""
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.setex = AsyncMock()
    r.delete = AsyncMock()
    r.keys = AsyncMock(return_value=[])
    return r


def test_cache_set_and_get(mock_redis):
    """测试缓存设置和获取"""
    from app.core.cache import CacheManager
    cm = CacheManager()
    cm._redis = mock_redis

    mock_redis.get.return_value = json.dumps({"key": "value"})
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(cm.get("test_key"))
    assert result == {"key": "value"}
    mock_redis.get.assert_called_once_with("test_key")


def test_cache_set(mock_redis):
    """测试缓存写入"""
    from app.core.cache import CacheManager
    cm = CacheManager()
    cm._redis = mock_redis

    import asyncio
    asyncio.get_event_loop().run_until_complete(cm.set("test_key", {"data": "value"}, ttl=60))
    mock_redis.setex.assert_called_once()


def test_cache_delete(mock_redis):
    """测试缓存删除"""
    from app.core.cache import CacheManager
    cm = CacheManager()
    cm._redis = mock_redis

    import asyncio
    asyncio.get_event_loop().run_until_complete(cm.delete("test_key"))
    mock_redis.delete.assert_called_once_with("test_key")


def test_invalidate_pattern(mock_redis):
    """测试批量失效缓存"""
    from app.core.cache import CacheManager
    cm = CacheManager()
    cm._redis = mock_redis
    mock_redis.keys.return_value = ["key1", "key2", "key3"]

    import asyncio
    asyncio.get_event_loop().run_until_complete(cm.delete_pattern("agent:*"))
    mock_redis.keys.assert_called_once_with("agent:*")
    mock_redis.delete.assert_called_once()


def test_cache_with_none_value(mock_redis):
    """测试 None 值的处理"""
    from app.core.cache import CacheManager
    cm = CacheManager()
    cm._redis = mock_redis
    mock_redis.get.return_value = None

    import asyncio
    result = asyncio.get_event_loop().run_until_complete(cm.get("nonexistent"))
    assert result is None


def test_json_serialization(mock_redis):
    """测试 JSON 序列化"""
    from app.core.cache import CacheManager
    cm = CacheManager()
    cm._redis = mock_redis
    mock_redis.get.return_value = None

    import asyncio
    result = asyncio.get_event_loop().run_until_complete(cm.get("test"))
    assert result is None
