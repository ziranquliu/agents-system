"""
测试 - 记忆增强服务 (自动遗忘/合并去重/追溯/词云/分布)
"""

import pytest
import time


class TestImportanceScoring:
    """重要性评分"""

    def test_recent_memory_high_importance(self):
        from app.services.memory_enhancement_service import MemoryEnhancementService
        svc = MemoryEnhancementService()
        now = time.time()
        score = svc.compute_importance(
            created_at=now - 3600,
            last_accessed=now - 100,
            access_count=10,
            relevance_score=0.8,
        )
        assert score > 0.5

    def test_old_memory_low_importance(self):
        from app.services.memory_enhancement_service import MemoryEnhancementService
        svc = MemoryEnhancementService()
        now = time.time()
        score = svc.compute_importance(
            created_at=now - 90 * 86400,
            last_accessed=now - 60 * 86400,
            access_count=0,
            relevance_score=0.1,
        )
        assert score < 0.2

    def test_frequent_access_boosts(self):
        from app.services.memory_enhancement_service import MemoryEnhancementService
        svc = MemoryEnhancementService()
        now = time.time()
        score_low = svc.compute_importance(now - 86400, now - 86400, 0)
        score_high = svc.compute_importance(now - 86400, now - 86400, 20)
        assert score_high > score_low


class TestAutoForget:
    """自动遗忘"""

    @pytest.mark.asyncio
    async def test_forget_low_importance(self):
        from app.services.memory_enhancement_service import MemoryEnhancementService
        svc = MemoryEnhancementService()
        now = time.time()
        memories = [
            {"id": "m1", "content": "重要记忆", "importance_score": 0.9,
             "created_at": now - 86400, "last_accessed": now - 100, "access_count": 15, "agent_id": "a1"},
            {"id": "m2", "content": "不重要记忆", "importance_score": 0.05,
             "created_at": now - 90 * 86400, "last_accessed": now - 60 * 86400, "access_count": 0, "agent_id": "a1"},
        ]
        result = await svc.auto_forget(memories, threshold=0.2)
        assert result["forgotten"] == 1
        assert result["kept"] == 1
        assert "m2" in result["forgotten_ids"]
        assert "m1" in result["kept_ids"]

    @pytest.mark.asyncio
    async def test_forget_lru_expired(self):
        from app.services.memory_enhancement_service import MemoryEnhancementService
        svc = MemoryEnhancementService()
        now = time.time()
        memories = [
            {"id": "m1", "content": "老记忆", "importance_score": 0.5,
             "created_at": now - 60 * 86400, "last_accessed": now - 40 * 86400, "access_count": 5},
        ]
        result = await svc.auto_forget(memories, threshold=0.01)
        assert result["forgotten"] == 1
        assert result["reasons"]["lru_expired"] == 1

    @pytest.mark.asyncio
    async def test_no_forget(self):
        from app.services.memory_enhancement_service import MemoryEnhancementService
        svc = MemoryEnhancementService()
        now = time.time()
        memories = [
            {"id": "m1", "content": "新记忆", "importance_score": 0.8,
             "created_at": now - 100, "last_accessed": now, "access_count": 10},
        ]
        result = await svc.auto_forget(memories, threshold=0.2)
        assert result["forgotten"] == 0
        assert result["kept"] == 1


class TestMergeDuplicates:
    """合并去重"""

    @pytest.mark.asyncio
    async def test_merge_identical_vectors(self):
        from app.services.memory_enhancement_service import MemoryEnhancementService
        svc = MemoryEnhancementService()
        memories = [
            {"id": "m1", "content": "内容A", "embedding_vector": [1.0, 0.0, 0.0], "importance_score": 0.8},
            {"id": "m2", "content": "内容B", "embedding_vector": [1.0, 0.0, 0.0], "importance_score": 0.5},
            {"id": "m3", "content": "内容C", "embedding_vector": [0.0, 0.0, 1.0], "importance_score": 0.7},
        ]
        result = await svc.merge_duplicates(memories, similarity_threshold=0.95)
        assert result["merge_candidates"] >= 1

    @pytest.mark.asyncio
    async def test_no_merge_different(self):
        from app.services.memory_enhancement_service import MemoryEnhancementService
        svc = MemoryEnhancementService()
        memories = [
            {"id": "m1", "content": "A", "embedding_vector": [1.0, 0.0, 0.0]},
            {"id": "m2", "content": "B", "embedding_vector": [0.0, 0.0, 1.0]},
        ]
        result = await svc.merge_duplicates(memories, similarity_threshold=0.95)
        assert result["merge_candidates"] == 0


class TestForgottenRecords:
    """遗忘记录追溯"""

    def test_record_and_retrieve(self):
        from app.services.memory_enhancement_service import MemoryEnhancementService
        svc = MemoryEnhancementService()
        # 手动添加遗忘记录
        from app.services.memory_enhancement_service import ForgottenMemory
        svc._forgotten_records.append(ForgottenMemory(
            id="f1", agent_id="a1", content="被遗忘的内容",
            memory_type="short_term", importance_score=0.1,
            forget_reason="low_importance",
        ))
        records = svc.get_forgotten_records(agent_id="a1")
        assert len(records) == 1
        assert records[0]["id"] == "f1"

    def test_restore(self):
        from app.services.memory_enhancement_service import MemoryEnhancementService, ForgottenMemory
        svc = MemoryEnhancementService()
        svc._forgotten_records.append(ForgottenMemory(id="f2", content="恢复我"))
        result = svc.restore_forgotten("f2")
        assert result["restored"] is True
        assert len(svc._forgotten_records) == 0

    def test_restore_nonexistent(self):
        from app.services.memory_enhancement_service import MemoryEnhancementService
        svc = MemoryEnhancementService()
        result = svc.restore_forgotten("nonexistent")
        assert result["restored"] is False


class TestWordCloud:
    """词云"""

    def test_generate(self):
        from app.services.memory_enhancement_service import MemoryEnhancementService
        svc = MemoryEnhancementService()
        memories = [
            {"content": "Python 编程 模型 训练", "importance_score": 0.8},
            {"content": "Python 模型 推理 部署", "importance_score": 0.9},
            {"content": "数据库 SQL 查询优化", "importance_score": 0.6},
        ]
        cloud = svc.generate_word_cloud(memories, max_words=10)
        assert len(cloud) > 0
        # Python 应出现 2 次
        py_entry = next((e for e in cloud if e["word"] == "python"), None)
        assert py_entry is not None
        assert py_entry["count"] == 2

    def test_empty(self):
        from app.services.memory_enhancement_service import MemoryEnhancementService
        svc = MemoryEnhancementService()
        cloud = svc.generate_word_cloud([])
        assert cloud == []


class TestTypeDistribution:
    """类型分布"""

    def test_distribution(self):
        from app.services.memory_enhancement_service import MemoryEnhancementService
        svc = MemoryEnhancementService()
        now = time.time()
        memories = [
            {"memory_type": "short_term", "importance_score": 0.5, "access_count": 3, "created_at": now - 3600},
            {"memory_type": "short_term", "importance_score": 0.4, "access_count": 1, "created_at": now - 7200},
            {"memory_type": "long_term", "importance_score": 0.8, "access_count": 10, "created_at": now - 86400},
            {"memory_type": "shared", "importance_score": 0.6, "access_count": 5, "created_at": now - 172800},
        ]
        dist = svc.get_type_distribution(memories)
        assert len(dist) == 3
        # short_term 应为最多
        assert dist[0]["memory_type"] == "short_term"
        assert dist[0]["count"] == 2
        assert dist[0]["percentage"] == 50.0


class TestForgetStatistics:
    def test_stats(self):
        from app.services.memory_enhancement_service import MemoryEnhancementService, ForgottenMemory
        svc = MemoryEnhancementService()
        svc._forgotten_records.extend([
            ForgottenMemory(id="f1", memory_type="short_term", importance_score=0.1, forget_reason="low_importance"),
            ForgottenMemory(id="f2", memory_type="long_term", importance_score=0.15, forget_reason="lru_expired"),
        ])
        stats = svc.get_forget_statistics()
        assert stats["total_forgotten"] == 2
        assert stats["by_reason"]["low_importance"] == 1
        assert stats["by_reason"]["lru_expired"] == 1
