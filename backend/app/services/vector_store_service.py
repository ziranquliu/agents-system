"""
向量存储服务 — Qdrant 真实集成

功能:
- 向量集合 CRUD (创建/删除/列表)
- 向量插入/更新/删除
- 语义搜索 (向量相似度)
- 混合搜索 (向量 + 关键词过滤)
- 批量操作
- 优雅降级 (Qdrant 不可用时回退到 numpy 内存搜索)
- 支持集合级别的 payload 过滤
- 多租户 (按 tenant_id 隔离)

设计:
  本服务是 Qdrant 向量数据库的真实客户端封装。
  当 Qdrant 不可用时，自动降级为内存中的 numpy 向量搜索。
"""

import json
import logging
import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# 尝试导入 Qdrant 客户端
_qdrant_available = False
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance,
        FieldCondition,
        Filter,
        MatchValue,
        PointStruct,
        VectorParams,
        ScrollRequest,
    )
    _qdrant_available = True
    logger.info("Qdrant client available")
except ImportError:
    logger.info("Qdrant client not installed, using numpy fallback")


@dataclass
class VectorPoint:
    """向量数据点"""
    id: str = ""
    vector: list[float] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0


@dataclass
class SearchResult:
    """搜索结果"""
    points: list[VectorPoint] = field(default_factory=list)
    total: int = 0
    search_time_ms: float = 0
    backend: str = "qdrant"  # qdrant / numpy_fallback


class VectorStoreService:
    """
    向量存储服务

    - 主存储: Qdrant (真实向量数据库)
    - 降级: numpy 内存搜索
    - 多租户隔离
    - 支持 payload 过滤
    """

    DEFAULT_COLLECTION = "agent_vectors"
    DEFAULT_VECTOR_SIZE = 1536  # text-embedding-3-small 维度

    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        qdrant_api_key: str = "",
        default_vector_size: int = 0,
    ):
        self._qdrant_url = qdrant_url
        self._qdrant_api_key = qdrant_api_key
        self._default_vector_size = default_vector_size or self.DEFAULT_VECTOR_SIZE
        self._client: Optional["QdrantClient"] = None
        self._numpy_store: dict[str, list[dict]] = {}  # collection -> [{id, vector, payload}]
        self._using_qdrant = False

    # ----------------------------------------------------------
    # 初始化
    # ----------------------------------------------------------

    def connect(self) -> bool:
        """连接到 Qdrant"""
        if not _qdrant_available:
            logger.warning("Qdrant 不可用, 使用 numpy 内存搜索")
            return False

        try:
            kwargs: dict[str, Any] = {"url": self._qdrant_url}
            if self._qdrant_api_key:
                kwargs["api_key"] = self._qdrant_api_key
            self._client = QdrantClient(**kwargs)
            # 验证连接
            self._client.get_collections()
            self._using_qdrant = True
            logger.info("已连接到 Qdrant: %s", self._qdrant_url)
            return True
        except Exception as e:
            logger.warning("Qdrant 连接失败: %s, 回退到 numpy", e)
            self._using_qdrant = False
            return False

    @property
    def backend(self) -> str:
        return "qdrant" if self._using_qdrant else "numpy_fallback"

    # ----------------------------------------------------------
    # 集合管理
    # ----------------------------------------------------------

    def ensure_collection(
        self, collection_name: str = "", vector_size: int = 0
    ) -> dict:
        """确保集合存在"""
        name = collection_name or self.DEFAULT_COLLECTION
        size = vector_size or self._default_vector_size

        if self._using_qdrant:
            try:
                collections = self._client.get_collections()
                existing = [c.name for c in collections.collections]
                if name not in existing:
                    self._client.create_collection(
                        collection_name=name,
                        vectors_config=VectorParams(
                            size=size,
                            distance=Distance.COSINE,
                        ),
                    )
                    logger.info("创建 Qdrant 集合: %s (维度=%d)", name, size)
                return {"collection": name, "vector_size": size, "backend": "qdrant"}
            except Exception as e:
                logger.warning("Qdrant 创建集合失败: %s", e)

        # numpy 降级
        if name not in self._numpy_store:
            self._numpy_store[name] = []
        return {"collection": name, "vector_size": size, "backend": "numpy_fallback"}

    def delete_collection(self, collection_name: str = "") -> dict:
        """删除集合"""
        name = collection_name or self.DEFAULT_COLLECTION

        if self._using_qdrant:
            try:
                self._client.delete_collection(collection_name=name)
                return {"deleted": True, "collection": name, "backend": "qdrant"}
            except Exception as e:
                logger.warning("Qdrant 删除集合失败: %s", e)

        self._numpy_store.pop(name, None)
        return {"deleted": True, "collection": name, "backend": "numpy_fallback"}

    def list_collections(self) -> list[dict]:
        """列出集合"""
        if self._using_qdrant:
            try:
                collections = self._client.get_collections()
                return [{"name": c.name} for c in collections.collections]
            except Exception as e:
                logger.warning("Qdrant 列举集合失败: %s", e)

        return [{"name": name, "count": len(pts)} for name, pts in self._numpy_store.items()]

    # ----------------------------------------------------------
    # 写入操作
    # ----------------------------------------------------------

    def upsert(
        self,
        collection_name: str,
        point_id: str,
        vector: list[float],
        payload: Optional[dict] = None,
    ) -> dict:
        """插入或更新单条向量"""
        if not point_id:
            point_id = uuid.uuid4().hex

        if self._using_qdrant:
            try:
                point = PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload or {},
                )
                self._client.upsert(
                    collection_name=collection_name,
                    points=[point],
                )
                return {"upserted": True, "id": point_id, "backend": "qdrant"}
            except Exception as e:
                logger.warning("Qdrant upsert 失败: %s", e)

        # numpy 降级
        store = self._numpy_store.setdefault(collection_name, [])
        # 更新或插入
        for i, p in enumerate(store):
            if p["id"] == point_id:
                store[i] = {"id": point_id, "vector": vector, "payload": payload or {}}
                return {"upserted": True, "id": point_id, "backend": "numpy_fallback"}
        store.append({"id": point_id, "vector": vector, "payload": payload or {}})
        return {"upserted": True, "id": point_id, "backend": "numpy_fallback"}

    def upsert_batch(
        self,
        collection_name: str,
        points: list[dict],
    ) -> dict:
        """批量插入向量"""
        if not points:
            return {"upserted": 0}

        if self._using_qdrant:
            try:
                qd_points = [
                    PointStruct(
                        id=p.get("id", uuid.uuid4().hex),
                        vector=p["vector"],
                        payload=p.get("payload", {}),
                    )
                    for p in points
                ]
                self._client.upsert(
                    collection_name=collection_name,
                    points=qd_points,
                )
                return {"upserted": len(points), "backend": "qdrant"}
            except Exception as e:
                logger.warning("Qdrant batch upsert 失败: %s", e)

        # numpy 降级
        store = self._numpy_store.setdefault(collection_name, [])
        for p in points:
            pid = p.get("id", uuid.uuid4().hex)
            updated = False
            for i, existing in enumerate(store):
                if existing["id"] == pid:
                    store[i] = {"id": pid, "vector": p["vector"], "payload": p.get("payload", {})}
                    updated = True
                    break
            if not updated:
                store.append({"id": pid, "vector": p["vector"], "payload": p.get("payload", {})})
        return {"upserted": len(points), "backend": "numpy_fallback"}

    def delete(
        self, collection_name: str, point_ids: list[str]
    ) -> dict:
        """删除向量"""
        if self._using_qdrant:
            try:
                self._client.delete(
                    collection_name=collection_name,
                    points_selector=point_ids,
                )
                return {"deleted": len(point_ids), "backend": "qdrant"}
            except Exception as e:
                logger.warning("Qdrant delete 失败: %s", e)

        # numpy 降级
        store = self._numpy_store.get(collection_name, [])
        id_set = set(point_ids)
        before = len(store)
        self._numpy_store[collection_name] = [
            p for p in store if p["id"] not in id_set
        ]
        return {"deleted": before - len(self._numpy_store[collection_name]), "backend": "numpy_fallback"}

    # ----------------------------------------------------------
    # 搜索
    # ----------------------------------------------------------

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        top_k: int = 10,
        score_threshold: float = 0.0,
        filter_payload: Optional[dict] = None,
        tenant_id: str = "",
    ) -> SearchResult:
        """语义搜索"""
        start = time.time()

        if self._using_qdrant:
            try:
                query_filter = None
                conditions = []
                if tenant_id:
                    conditions.append(
                        FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))
                    )
                if filter_payload:
                    for key, value in filter_payload.items():
                        conditions.append(
                            FieldCondition(key=key, match=MatchValue(value=value))
                        )
                if conditions:
                    query_filter = Filter(must=conditions)

                results = self._client.search(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    limit=top_k,
                    score_threshold=score_threshold if score_threshold > 0 else None,
                    query_filter=query_filter,
                )

                points = [
                    VectorPoint(
                        id=str(r.id),
                        vector=[],
                        payload=r.payload or {},
                        score=r.score,
                    )
                    for r in results
                ]
                elapsed = (time.time() - start) * 1000
                return SearchResult(
                    points=points, total=len(points),
                    search_time_ms=round(elapsed, 2), backend="qdrant",
                )
            except Exception as e:
                logger.warning("Qdrant 搜索失败: %s, 回退到 numpy", e)

        # numpy 降级
        store = self._numpy_store.get(collection_name, [])
        scored: list[tuple[float, dict]] = []

        for p in store:
            # payload 过滤
            if tenant_id and p.get("payload", {}).get("tenant_id") != tenant_id:
                continue
            if filter_payload:
                match = True
                for key, value in filter_payload.items():
                    if p.get("payload", {}).get(key) != value:
                        match = False
                        break
                if not match:
                    continue

            sim = self._cosine_similarity(query_vector, p.get("vector", []))
            if sim >= score_threshold:
                scored.append((sim, p))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]

        points = [
            VectorPoint(
                id=p["id"], vector=[],
                payload=p.get("payload", {}),
                score=round(s, 4),
            )
            for s, p in top
        ]

        elapsed = (time.time() - start) * 1000
        return SearchResult(
            points=points, total=len(points),
            search_time_ms=round(elapsed, 2), backend="numpy_fallback",
        )

    # ----------------------------------------------------------
    # 信息查询
    # ----------------------------------------------------------

    def get_collection_info(self, collection_name: str = "") -> dict:
        """获取集合信息"""
        name = collection_name or self.DEFAULT_COLLECTION

        if self._using_qdrant:
            try:
                info = self._client.get_collection(collection_name=name)
                return {
                    "name": name,
                    "vectors_count": info.vectors_count,
                    "points_count": info.points_count,
                    "config": {
                        "vector_size": info.config.params.vectors.size
                            if hasattr(info.config.params, 'vectors') else 0,
                        "distance": str(info.config.params.vectors.distance)
                            if hasattr(info.config.params, 'vectors') else "unknown",
                    },
                    "backend": "qdrant",
                }
            except Exception as e:
                logger.warning("Qdrant 获取集合信息失败: %s", e)

        store = self._numpy_store.get(name, [])
        return {
            "name": name,
            "vectors_count": len(store),
            "points_count": len(store),
            "backend": "numpy_fallback",
        }

    def count(self, collection_name: str = "") -> int:
        """获取向量数量"""
        name = collection_name or self.DEFAULT_COLLECTION
        if self._using_qdrant:
            try:
                info = self._client.get_collection(collection_name=name)
                return info.points_count or 0
            except Exception:
                pass
        return len(self._numpy_store.get(name, []))

    def health_check(self) -> dict:
        """健康检查"""
        if self._using_qdrant:
            try:
                self._client.get_collections()
                return {"status": "healthy", "backend": "qdrant", "url": self._qdrant_url}
            except Exception as e:
                return {"status": "unhealthy", "backend": "qdrant", "error": str(e)}
        return {"status": "degraded", "backend": "numpy_fallback", "message": "使用内存搜索"}

    # ----------------------------------------------------------
    # 工具方法
    # ----------------------------------------------------------

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """余弦相似度"""
        if not a or not b or len(a) != len(b):
            return 0.0
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        return dot / (norm_a * norm_b)


# 全局实例
_vector_store_service: Optional[VectorStoreService] = None


def get_vector_store_service() -> VectorStoreService:
    global _vector_store_service
    if _vector_store_service is None:
        import os
        _vector_store_service = VectorStoreService(
            qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            qdrant_api_key=os.getenv("QDRANT_API_KEY", ""),
        )
        _vector_store_service.connect()
    return _vector_store_service
