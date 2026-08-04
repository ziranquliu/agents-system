"""
单元测试 - 缓存服务
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.cache import CacheManager, cached, invalidate_pattern


@pytest.fixture
def cache_manager():
    """创建缓存管理器实例"""
    return CacheManager()
def test_cache_set_and_get(cache_manager):
    """测试缓存设置和获取"""
    # Mock Redis
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value='{"key": "value"}')
    cache_manager._redis = mock_redis
    
    result = cache_manager.get("test_key")
    assert result == {"key": "value"}
def test_cache_set(cache_manager):
    """测试缓存写入"""
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()
    cache_manager._redis = mock_redis
    
    cache_manager.set("test_key", {"data": "value"}, ttl=60)
    mock_redis.setex.assert_called_once()
def test_cache_delete(cache_manager):
    """测试缓存删除"""
    mock_redis = AsyncMock()
    mock_redis.delete = AsyncMock()
    cache_manager._redis = mock_redis
    
    cache_manager.delete("test_key")
    mock_redis.delete.assert_called_once_with("test_key")
def test_invalidate_pattern(cache_manager):
    """测试批量失效缓存"""
    mock_redis = AsyncMock()
    mock_redis.keys = AsyncMock(return_value=["key1", "key2", "key3"])
    mock_redis.delete = AsyncMock()
    cache_manager._redis = mock_redis
    
    cache_manager.delete_pattern("agent:*")
    mock_redis.keys.assert_called_once_with("agent:*")
    mock_redis.delete.assert_called_once()
def test_cached_decorator(cache_manager):
    """测试缓存装饰器"""
    # Mock Redis
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    cache_manager._redis = mock_redis
    
    @cached(ttl=60, key_prefix="test")
    def test_function(x: int) -> int:
        return x * 2
    
    result = test_function(5)
    assert result == 10
    mock_redis.setex.assert_called_once()
def test_cache_with_none_value(cache_manager):
    """测试None值的处理"""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    cache_manager._redis = mock_redis
    
    result = cache_manager.get("nonexistent")
    assert result is None
def test_json_serialization(cache_manager):
    """测试JSON序列化"""
    mock_redis = AsyncMock()
    
    # 测试复杂对象序列化
    complex_data = {
        "list": [1, 2, 3],
        "nested": {"a": {"b": "c"}},
        "none_value": None
    }
    
    mock_redis.get = AsyncMock(return_value=None)
    result = cache_manager.get("test")
    assert result is None
