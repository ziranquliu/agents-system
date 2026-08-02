# Redis缓存服务 - 完整实现
"""
提供热点数据缓存、缓存失效策略等
"""
import json
from typing import Optional, Any, Callable
from functools import wraps
from redis.asyncio import Redis, from_url

from app.core.config import settings
from app.core.exceptions import APIError


class CacheManager:
    # TODO: Consider splitting large methods into smaller units
    """Redis缓存管理器"""
    
    def __init__(self):
        self._redis: Optional[Redis] = None
    
    async def connect(self):
        """连接Redis"""
        self._redis = from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=20
        )
        await self._redis.ping()
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if not self._redis:
            return None
        try:
            value = await self._redis.get(key)
            return json.loads(value) if value else None
        except Exception:
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 300):
        """设置缓存"""
        if not self._redis:
            return
        try:
            serialized = json.dumps(value, ensure_ascii=False, default=str)
            await self._redis.setex(key, ttl, serialized)
        except Exception:
            pass
    
    async def delete(self, key: str):
        """删除缓存"""
        if not self._redis:
            return
        try:
            await self._redis.delete(key)
        except Exception:
            pass
    
    async def delete_pattern(self, pattern: str):
        """批量删除匹配模式的缓存"""
        if not self._redis:
            return
        try:
            keys = await self._redis.keys(pattern)
            if keys:
                await self._redis.delete(*keys)
        except Exception:
            pass
    
    async def incr(self, key: str, amount: int = 1) -> int:
        """递增计数"""
        if not self._redis:
            return 0
        try:
            return await self._redis.incr(key, amount)
        except Exception:
            return 0
    
    async def decr(self, key: str, amount: int = 1) -> int:
        """递减计数"""
        if not self._redis:
            return 0
        try:
            return await self._redis.decr(key, amount)
        except Exception:
            return 0


# 全局缓存实例
cache_manager = CacheManager()


def cached(ttl: int = 300, key_prefix: str = ""):
    """缓存装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            base_key = f"{key_prefix}{func.__name__}"
            cache_key = f"{base_key}:{args}:{kwargs}"
            
            value = await cache_manager.get(cache_key)
            if value is not None:
                return value
            
            result = await func(*args, **kwargs)
            
            if result is not None:
                await cache_manager.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator


def invalidate_pattern(pattern: str):
    """缓存失效装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            await cache_manager.delete_pattern(pattern)
            return result
        return wrapper
    return decorator


# 便捷函数
async def get_cache(key: str) -> Optional[Any]:
    """获取缓存"""
    return await cache_manager.get(key)


async def set_cache(key: str, value: Any, ttl: int = 300):
    """设置缓存"""
    await cache_manager.set(key, value, ttl)


async def delete_cache(key: str):
    """删除缓存"""
    await cache_manager.delete(key)


async def invalidate_cache_pattern(pattern: str):
    """批量失效缓存"""
    await cache_manager.delete_pattern(pattern)


# ============================================================================
# REFACTORED METHODS - Split from main RedisCacheManager class
# ============================================================================

class RedisCacheManagerEnhanced:
    """Enhanced cache manager with split methods for better maintainability."""
    
    async def get_cached_value(self, key: str) -> Optional[Any]:
        """
        Get a cached value by key.
        
        Args:
            key: Cache key
        
        Returns:
            Cached value or None if not found
        """
        try:
            if not self.client:
                return None
            
            value = await self.client.get(key)
            if value is None:
                return None
            
            return json.loads(value)
        except Exception as e:
            logger.error(f"Failed to get cache value for key {key}: {e}")
            return None
    
    async def set_cached_value(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None
    ) -> bool:
        """
        Set a cached value.
        
        Args:
            key: Cache key
            value: Value to cache
            expire: Expiration time in seconds
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.client:
                return False
            
            serialized = json.dumps(value)
            if expire:
                await self.client.set(key, serialized, ex=expire)
            else:
                await self.client.set(key, serialized)
            
            return True
        except Exception as e:
            logger.error(f"Failed to set cache value for key {key}: {e}")
            return False
    
    async def delete_cached_value(self, key: str) -> bool:
        """
        Delete a cached value.
        
        Args:
            key: Cache key
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.client:
                return False
            
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Failed to delete cache value for key {key}: {e}")
            return False
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching a pattern.
        
        Args:
            pattern: Key pattern to match
        
        Returns:
            Number of keys invalidated
        """
        try:
            if not self.client:
                return 0
            
            count = 0
            async for key in self.client.scan_iter(match=pattern):
                await self.client.delete(key)
                count += 1
            
            return count
        except Exception as e:
            logger.error(f"Failed to invalidate pattern {pattern}: {e}")
            return 0
