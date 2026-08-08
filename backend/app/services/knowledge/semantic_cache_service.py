"""
Semantic Cache 服务 — 三级缓存架构 + 语义匹配

L1: 本地 LRU 内存缓存（最快,进程内）
L2: Redis 缓存（快速,跨进程共享）
L3: Qdrant/PostgreSQL 向量缓存（语义匹配,最慢但最准）

查询流程: L1 → L2 → L3 → miss
写入流程: 同时写入 L1 + L2 + L3
"""
import collections
import hashlib
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.semantic_cache import SemanticCacheEntry
from app.services.embedding_service import (
    cosine_similarity,
    get_embeddings,
    json_loads_vector,
    serialize_vector,
)

logger = logging.getLogger("semantic_cache")


# ==================================================================
# L1: 本地 LRU 内存缓存
# ==================================================================

class L1LRUCache:
    """进程内 LRU 缓存 — 最快,但不跨进程"""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, dict] = {}  # key → {value, timestamp, access_count}
        self._access_order: collections.OrderedDict = collections.OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                # TTL 检查
                if time.time() - entry["timestamp"] > self.ttl_seconds:
                    self._evict(key)
                    self._misses += 1
                    return None
                # 命中: 移到最后(最近使用)
                self._access_order.move_to_end(key)
                entry["access_count"] = entry.get("access_count", 0) + 1
                self._hits += 1
                return entry["value"]
            self._misses += 1
            return None

    def set(self, key: str, value: str):
        with self._lock:
            if key in self._cache:
                self._cache[key]["value"] = value
                self._cache[key]["timestamp"] = time.time()
                self._access_order.move_to_end(key)
            else:
                if len(self._cache) >= self.max_size:
                    # 淘汰最久未使用
                    oldest_key, _ = self._access_order.popitem(last=False)
                    del self._cache[oldest_key]
                self._cache[key] = {
                    "value": value,
                    "timestamp": time.time(),
                    "access_count": 0,
                }
                self._access_order[key] = True

    def delete(self, key: str):
        with self._lock:
            self._evict(key)

    def clear(self):
        with self._lock:
            self._cache.clear()
            self._access_order.clear()

    def _evict(self, key: str):
        self._cache.pop(key, None)
        self._access_order.pop(key, None)

    def cleanup_expired(self) -> int:
        """清理过期条目"""
        now = time.time()
        expired = []
        with self._lock:
            for key, entry in self._cache.items():
                if now - entry["timestamp"] > self.ttl_seconds:
                    expired.append(key)
        for key in expired:
            self._evict(key)
        return len(expired)

    def get_stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "level": "L1",
            "type": "LRU",
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total * 100, 1) if total else 0,
        }


# ==================================================================
# L2: Redis 缓存
# ==================================================================

class L2RedisCache:
    """Redis 缓存 — 跨进程共享,毫秒级延迟"""

    def __init__(self, default_ttl: int = 3600):
        self.default_ttl = default_ttl
        self._redis = None
        self._hits = 0
        self._misses = 0

    async def _get_redis(self):
        if self._redis is None:
            try:
                from app.core.config import settings
                import redis.asyncio as aioredis
                self._redis = await aioredis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                )
            except Exception as e:
                logger.warning("Redis 连接失败, L2 缓存不可用: %s", str(e))
                return None
        return self._redis

    async def get(self, key: str) -> Optional[str]:
        redis = await self._get_redis()
        if not redis:
            self._misses += 1
            return None
        try:
            value = await redis.get(f"semcache:{key}")
            if value:
                self._hits += 1
                return value
            self._misses += 1
            return None
        except Exception as e:
            logger.warning("L2 缓存读取失败: %s", str(e))
            self._misses += 1
            return None

    async def set(self, key: str, value: str, ttl: Optional[int] = None):
        redis = await self._get_redis()
        if not redis:
            return
        try:
            await redis.set(
                f"semcache:{key}",
                value,
                ex=ttl or self.default_ttl,
            )
        except Exception as e:
            logger.warning("L2 缓存写入失败: %s", str(e))

    async def delete(self, key: str):
        redis = await self._get_redis()
        if not redis:
            return
        try:
            await redis.delete(f"semcache:{key}")
        except Exception as e:
            logger.warning("L2 缓存删除失败: %s", str(e))

    async def cleanup_expired(self) -> int:
        """Redis 自动处理过期"""
        return 0

    def get_stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "level": "L2",
            "type": "Redis",
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total * 100, 1) if total else 0,
        }


# ==================================================================
# 三级缓存管理器
# ==================================================================

class ThreeLevelCache:
    """
    三级缓存管理器
    查询: L1 → L2 → L3(PG向量)
    写入: 同时写入三级
    """

    @staticmethod
    def _make_key(query: str, model: Optional[str] = None) -> str:
        """生成缓存键"""
        raw = f"{query}:{model or ''}"
        return hashlib.md5(raw.encode()).hexdigest()

    @staticmethod
    async def query(
        query: str,
        model: Optional[str] = None,
        threshold: float = 0.92,
        l1: Optional[L1LRUCache] = None,
        l2: Optional[L2RedisCache] = None,
        db: Optional[AsyncSession] = None,
    ) -> Optional[str]:
        """
        三级查询:
        L1 → L2 → L3(PG向量语义匹配)
        """
        key = ThreeLevelCache._make_key(query, model)

        # L1 查询
        if l1:
            result = l1.get(key)
            if result:
                logger.debug("L1 缓存命中: %s", key)
                return result

        # L2 查询
        if l2:
            result = await l2.get(key)
            if result:
                # 回填 L1
                if l1:
                    l1.set(key, result)
                logger.debug("L2 缓存命中: %s", key)
                return result

        # L3: 向量语义匹配(PG)
        if db:
            result = await ThreeLevelCache._query_l3(
                query, model, threshold, db
            )
            if result:
                # 回填 L1 + L2
                if l1:
                    l1.set(key, result)
                if l2:
                    await l2.set(key, result)
                logger.debug("L3 缓存命中: %s", key)
                return result

        return None

    @staticmethod
    async def _query_l3(
        query: str,
        model: Optional[str],
        threshold: float,
        db: AsyncSession,
    ) -> Optional[str]:
        """L3: PG 向量语义匹配"""
        try:
            query_vec = (await get_embeddings([query]))[0]
        except Exception as e:
            logger.warning("L3 embedding 计算失败: %s", str(e))
            return None

        if not query_vec:
            return None

        result = await db.execute(
            select(SemanticCacheEntry).order_by(
                SemanticCacheEntry.created_at.desc()
            )
        )
        entries = result.scalars().all()

        now = datetime.now(timezone.utc)
        best_score = 0.0
        best_entry = None
        for entry in entries:
            if entry.is_expired:
                await db.delete(entry)
                continue
            if model and entry.model and entry.model != model:
                continue
            entry_vec = json_loads_vector(entry.query_embedding)
            if not entry_vec:
                continue
            score = cosine_similarity(query_vec, entry_vec)
            if score > best_score:
                best_score = score
                best_entry = entry

        if best_entry and best_score >= threshold:
            best_entry.hit_count = (best_entry.hit_count or 0) + 1
            return best_entry.answer

        return None

    @staticmethod
    async def store(
        query: str,
        answer: str,
        model: Optional[str] = None,
        threshold: float = 0.92,
        ttl_seconds: int = 3600,
        l1: Optional[L1LRUCache] = None,
        l2: Optional[L2RedisCache] = None,
        db: Optional[AsyncSession] = None,
    ) -> bool:
        """三级写入"""
        if not query or not answer:
            return False

        key = ThreeLevelCache._make_key(query, model)

        # L1
        if l1:
            l1.set(key, answer)

        # L2
        if l2:
            await l2.set(key, answer, ttl=ttl_seconds)

        # L3 (PG)
        if db:
            try:
                query_vec = (await get_embeddings([query]))[0]
                entry = SemanticCacheEntry(
                    id=str(uuid.uuid4()),
                    query_text=query[:500],
                    query_embedding=serialize_vector(query_vec),
                    answer=answer,
                    model=model,
                    threshold=threshold,
                    ttl_seconds=ttl_seconds,
                    hit_count=0,
                    created_at=datetime.now(timezone.utc),
                    expires_at=SemanticCacheEntry.make_expires_at(ttl_seconds),
                )
                db.add(entry)
                await db.flush()
            except Exception as e:
                logger.warning("L3 缓存写入失败: %s", str(e))

        return True

    @staticmethod
    async def invalidate(
        query: str,
        model: Optional[str] = None,
        l1: Optional[L1LRUCache] = None,
        l2: Optional[L2RedisCache] = None,
        db: Optional[AsyncSession] = None,
    ):
        """三级失效"""
        key = ThreeLevelCache._make_key(query, model)
        if l1:
            l1.delete(key)
        if l2:
            await l2.delete(key)
        if db:
            result = await db.execute(
                select(SemanticCacheEntry).where(
                    SemanticCacheEntry.query_text == query[:500]
                )
            )
            for entry in result.scalars().all():
                await db.delete(entry)

    @staticmethod
    def get_all_stats(
        l1: Optional[L1LRUCache] = None,
        l2: Optional[L2RedisCache] = None,
    ) -> dict:
        stats = {"l1": l1.get_stats() if l1 else None, "l2": l2.get_stats() if l2 else None}
        return stats


# ==================================================================
# 向后兼容层 — 供 chat.py 等已有调用方使用
# ==================================================================

class SemanticCacheService:
    """兼容旧接口的包装类，内部委托 ThreeLevelCache"""

    @staticmethod
    async def get_cached_answer(
        session: AsyncSession,
        query: str,
        model: Optional[str] = None,
        threshold: float = 0.92,
        ttl_seconds: Optional[int] = None,
        query_embedding: Optional[list] = None,
    ) -> Optional[str]:
        return await ThreeLevelCache.query(
            query=query,
            model=model,
            threshold=threshold,
            db=session,
        )

    @staticmethod
    async def store_answer(
        session: AsyncSession,
        query: str,
        answer: str,
        model: Optional[str] = None,
        threshold: float = 0.92,
        ttl_seconds: Optional[int] = 3600,
        query_embedding: Optional[list] = None,
    ):
        await ThreeLevelCache.store(
            query=query,
            answer=answer,
            model=model,
            threshold=threshold,
            ttl_seconds=ttl_seconds or 3600,
            db=session,
        )

    @staticmethod
    async def clean_expired(session: AsyncSession) -> int:
        result = await session.execute(
            select(SemanticCacheEntry).where(
                SemanticCacheEntry.expires_at.isnot(None)
            )
        )
        entries = result.scalars().all()
        removed = 0
        for entry in entries:
            if entry.is_expired:
                await session.delete(entry)
                removed += 1
        if removed:
            await session.flush()
        return removed

    @staticmethod
    async def count(session: AsyncSession) -> int:
        result = await session.execute(select(SemanticCacheEntry))
        return len(result.scalars().all())


# 便捷引用（供 API 使用）
semantic_cache_service = SemanticCacheService()
