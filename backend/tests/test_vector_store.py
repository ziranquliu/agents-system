"""
测试 - 向量存储服务 (Qdrant + numpy 降级)
"""

import pytest
import math


class TestVectorStoreNumpyFallback:
    """测试 numpy 降级模式"""

    def _make_service(self):
        from app.services.vector_store_service import VectorStoreService
        svc = VectorStoreService(qdrant_url="http://localhost:9999")
        # 不连接 Qdrant, 直接使用 numpy 降级
        return svc

    def test_cosine_similarity(self):
        """余弦相似度计算"""
        from app.services.vector_store_service import VectorStoreService
        a = [1.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0]
        assert VectorStoreService._cosine_similarity(a, b) == pytest.approx(1.0)

        c = [0.0, 1.0, 0.0]
        assert VectorStoreService._cosine_similarity(a, c) == pytest.approx(0.0)

        d = [0.0, 0.0, 0.0]
        assert VectorStoreService._cosine_similarity(a, d) == 0.0

    def test_cosine_similarity_empty(self):
        from app.services.vector_store_service import VectorStoreService
        assert VectorStoreService._cosine_similarity([], []) == 0.0
        assert VectorStoreService._cosine_similarity([1.0], []) == 0.0

    def test_ensure_collection_numpy(self):
        svc = self._make_service()
        result = svc.ensure_collection("test_col", 128)
        assert result["collection"] == "test_col"
        assert result["vector_size"] == 128
        assert result["backend"] == "numpy_fallback"

    def test_upsert_and_search(self):
        svc = self._make_service()
        svc.ensure_collection("search_test", 3)

        # 插入向量
        svc.upsert("search_test", "v1", [1.0, 0.0, 0.0], {"label": "a"})
        svc.upsert("search_test", "v2", [0.0, 1.0, 0.0], {"label": "b"})
        svc.upsert("search_test", "v3", [0.9, 0.1, 0.0], {"label": "c"})

        # 搜索
        result = svc.search("search_test", [1.0, 0.0, 0.0], top_k=2)
        assert result.total == 2
        assert result.points[0].id == "v1"
        assert result.points[0].score > 0.99
        assert result.backend == "numpy_fallback"

    def test_upsert_update(self):
        svc = self._make_service()
        svc.ensure_collection("update_test", 2)

        svc.upsert("update_test", "p1", [1.0, 0.0], {"v": 1})
        svc.upsert("update_test", "p1", [0.0, 1.0], {"v": 2})

        info = svc.get_collection_info("update_test")
        assert info["points_count"] == 1

        result = svc.search("update_test", [0.0, 1.0], top_k=1)
        assert result.points[0].payload["v"] == 2

    def test_delete(self):
        svc = self._make_service()
        svc.ensure_collection("del_test", 2)
        svc.upsert("del_test", "p1", [1.0, 0.0])
        svc.upsert("del_test", "p2", [0.0, 1.0])

        deleted = svc.delete("del_test", ["p1"])
        assert deleted["deleted"] == 1

        info = svc.get_collection_info("del_test")
        assert info["points_count"] == 1

    def test_delete_collection(self):
        svc = self._make_service()
        svc.ensure_collection("to_delete", 2)
        result = svc.delete_collection("to_delete")
        assert result["deleted"] is True

    def test_list_collections(self):
        svc = self._make_service()
        svc.ensure_collection("col_a", 2)
        svc.ensure_collection("col_b", 2)
        cols = svc.list_collections()
        names = [c["name"] for c in cols]
        assert "col_a" in names
        assert "col_b" in names

    def test_batch_upsert(self):
        svc = self._make_service()
        svc.ensure_collection("batch_test", 2)

        points = [
            {"id": f"p{i}", "vector": [float(i), float(10 - i)], "payload": {"idx": i}}
            for i in range(5)
        ]
        result = svc.upsert_batch("batch_test", points)
        assert result["upserted"] == 5

        info = svc.get_collection_info("batch_test")
        assert info["points_count"] == 5

    def test_tenant_filter(self):
        svc = self._make_service()
        svc.ensure_collection("tenant_test", 2)
        svc.upsert("tenant_test", "p1", [1.0, 0.0], {"tenant_id": "t1"})
        svc.upsert("tenant_test", "p2", [1.0, 0.0], {"tenant_id": "t2"})

        result = svc.search("tenant_test", [1.0, 0.0], top_k=10, tenant_id="t1")
        assert result.total == 1
        assert result.points[0].payload["tenant_id"] == "t1"

    def test_health_check(self):
        svc = self._make_service()
        health = svc.health_check()
        assert health["backend"] == "numpy_fallback"
        assert health["status"] == "degraded"

    def test_count(self):
        svc = self._make_service()
        svc.ensure_collection("count_test", 2)
        assert svc.count("count_test") == 0
        svc.upsert("count_test", "p1", [1.0, 0.0])
        assert svc.count("count_test") == 1
