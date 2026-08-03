"""
Semantic Cache 服务（A8）— 语义缓存

- 查询 → 计算向量 → 与缓存条目余弦相似度 > 阈值（默认 0.92）→ 命中返回缓存答案
- 缓存键: query_embedding；存 answer + 时间戳；可配置阈值和 TTL
- 未命中走 LLM 并写入缓存（由调用方在聊天主流程中处理）
"""
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

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


class SemanticCacheService:
    """语义缓存服务"""

    @staticmethod
    async def get_cached_answer(
        session: AsyncSession,
        query: str,
        model: Optional[str] = None,
        threshold: float = 0.92,
        ttl_seconds: Optional[int] = None,
        query_embedding: Optional[list[float]] = None,
    ) -> Optional[str]:
        """查询语义缓存：返回命中的缓存答案，未命中返回 None。

        参数:
            query: 查询文本
            model: 模型名（可选，用于区分缓存）
            threshold: 余弦相似度阈值（默认 0.92）
            ttl_seconds: 只考虑未过期条目
            query_embedding: 预计算的查询向量（避免重复计算）
        """
        if not query or not query.strip():
            return None
        try:
            query_vec = query_embedding or (await get_embeddings([query]))[0]
        except Exception as e:
            logger.warning("[semantic_cache] query embedding failed: %s", e)
            return None
        if not query_vec:
            return None

        result = await session.execute(
            select(SemanticCacheEntry).order_by(SemanticCacheEntry.created_at.desc())
        )
        entries = result.scalars().all()

        now = datetime.utcnow()
        best_score = 0.0
        best_entry = None
        for entry in entries:
            # TTL 过期清理（懒清理：读到过期条目即删除）
            if entry.is_expired:
                await session.delete(entry)
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

        if best_entry is not None and best_score >= threshold:
            best_entry.hit_count = (best_entry.hit_count or 0) + 1
            await session.commit()
            return best_entry.answer
        return None

    @staticmethod
    async def store_answer(
        session: AsyncSession,
        query: str,
        answer: str,
        model: Optional[str] = None,
        threshold: float = 0.92,
        ttl_seconds: Optional[int] = 3600,
        query_embedding: Optional[list[float]] = None,
    ) -> Optional[SemanticCacheEntry]:
        """写入语义缓存条目。向量生成失败时跳过（不阻塞主流程）。"""
        if not query or not query.strip() or not answer:
            return None
        try:
            query_vec = query_embedding or (await get_embeddings([query]))[0]
        except Exception as e:
            logger.warning("[semantic_cache] store embedding failed: %s", e)
            return None
        if not query_vec:
            return None

        entry = SemanticCacheEntry(
            id=str(uuid.uuid4()),
            query_text=query[:500],
            query_embedding=serialize_vector(query_vec),
            answer=answer,
            model=model,
            threshold=threshold,
            ttl_seconds=ttl_seconds,
            hit_count=0,
            created_at=datetime.utcnow(),
            expires_at=SemanticCacheEntry.make_expires_at(ttl_seconds),
        )
        session.add(entry)
        await session.commit()
        return entry

    @staticmethod
    async def clean_expired(session: AsyncSession) -> int:
        """清理全部过期条目，返回删除数量"""
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
            await session.commit()
        return removed

    @staticmethod
    async def count(session: AsyncSession) -> int:
        """当前缓存条目数（统计用）"""
        result = await session.execute(select(SemanticCacheEntry))
        return len(result.scalars().all())


# 便捷引用（供 API 使用）
semantic_cache_service = SemanticCacheService()
