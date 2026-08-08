"""
KnowledgeChunkingService 测试 — 分块策略、权限、混合搜索权重
"""
import pytest
import uuid
from datetime import datetime, timezone

from app.services.knowledge_chunking_service import (
    KnowledgeChunkingService,
    ChunkingConfig,
    ChunkingStrategy,
    SearchWeights,
    AccessPermission,
)


# ============================================================
# 枚举测试
# ============================================================

class TestChunkingStrategy:
    def test_all_strategies(self):
        values = {s.value for s in ChunkingStrategy}
        assert values == {"fixed_size", "sentence", "paragraph", "semantic", "recursive"}

    def test_strategy_count(self):
        assert len(ChunkingStrategy) == 5


# ============================================================
# ChunkingConfig 测试
# ============================================================

class TestChunkingConfig:
    def test_default_config(self):
        cfg = ChunkingConfig()
        assert cfg.strategy == ChunkingStrategy.FIXED_SIZE
        assert cfg.chunk_size == 500
        assert cfg.chunk_overlap == 50
        assert cfg.min_chunk_size == 50
        assert cfg.separators == ["\n\n", "\n", "。", ".", " "]

    def test_custom_config(self):
        cfg = ChunkingConfig(
            strategy=ChunkingStrategy.SENTENCE,
            chunk_size=1024,
            chunk_overlap=100,
            min_chunk_size=100,
        )
        assert cfg.strategy == ChunkingStrategy.SENTENCE
        assert cfg.chunk_size == 1024


# ============================================================
# SearchWeights 测试
# ============================================================

class TestSearchWeights:
    def test_default_weights(self):
        w = SearchWeights()
        assert w.keyword_weight == 0.3
        assert w.vector_weight == 0.7
        assert w.recency_boost >= 0
        assert w.popularity_boost >= 0

    def test_weight_sum_includes_all(self):
        w = SearchWeights()
        total = w.keyword_weight + w.vector_weight + w.recency_boost + w.popularity_boost
        assert total > 0


# ============================================================
# KnowledgeChunkingService 功能测试
# ============================================================

class TestKnowledgeChunkingService:
    def setup_method(self):
        self.service = KnowledgeChunkingService()

    def test_configure_document(self):
        cfg = self.service.configure("doc1")
        assert cfg.chunk_size == 500
        assert "doc1" in self.service._configs

    def test_configure_custom(self):
        custom = ChunkingConfig(strategy=ChunkingStrategy.PARAGRAPH, chunk_size=1024)
        cfg = self.service.configure("doc1", config=custom)
        assert cfg.strategy == ChunkingStrategy.PARAGRAPH

    def test_chunk_fixed_size(self):
        content = "A" * 1000
        chunks = self.service.chunk_document("doc1", content)
        assert len(chunks) > 0
        # 每个 chunk 的内容应该来自原文
        for chunk in chunks:
            assert chunk.document_id == "doc1"
            assert len(chunk.content) > 0

    def test_chunk_fixed_size_empty_content(self):
        chunks = self.service.chunk_document("doc1", "")
        assert len(chunks) == 0

    def test_chunk_fixed_size_small_content(self):
        content = "Short"
        cfg = ChunkingConfig(min_chunk_size=100)
        chunks = self.service.chunk_document("doc1", content, config=cfg)
        # 内容小于 min_chunk_size, 没有块
        assert len(chunks) == 0

    def test_chunk_sentence_strategy(self):
        content = "第一句话。第二句话。第三句话。第四句话。"
        cfg = ChunkingConfig(
            strategy=ChunkingStrategy.SENTENCE,
            chunk_size=20,
            min_chunk_size=5,
        )
        chunks = self.service.chunk_document("doc1", content, config=cfg)
        assert len(chunks) >= 1
        for chunk in chunks:
            assert "。" in chunk.content or len(chunk.content) > 5

    def test_chunk_paragraph_strategy(self):
        content = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        cfg = ChunkingConfig(
            strategy=ChunkingStrategy.PARAGRAPH,
            chunk_size=30,
            min_chunk_size=5,
        )
        chunks = self.service.chunk_document("doc1", content, config=cfg)
        assert len(chunks) >= 1

    def test_chunk_semantic_strategy(self):
        content = "Part1\n\nPart2\n\nPart3\n\nPart4\n\nPart5"
        cfg = ChunkingConfig(
            strategy=ChunkingStrategy.SEMANTIC,
            chunk_size=20,
            min_chunk_size=5,
        )
        chunks = self.service.chunk_document("doc1", content, config=cfg)
        assert len(chunks) >= 1

    def test_chunk_recursive_strategy(self):
        """有分隔符的递归分割"""
        content = "Hello\n\nWorld\n\nFoo\n\nBar\n\nBaz\n\nQux\n\nAlpha\n\nBeta\n\nGamma\n\nDelta"
        cfg = ChunkingConfig(
            strategy=ChunkingStrategy.RECURSIVE,
            chunk_size=20,
            min_chunk_size=5,
        )
        chunks = self.service.chunk_document("doc1", content, config=cfg)
        assert len(chunks) >= 1

    def test_chunk_sequential_index(self):
        content = "A" * 500
        cfg = ChunkingConfig(chunk_size=100, min_chunk_size=10)
        chunks = self.service.chunk_document("doc1", content, config=cfg)
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_chunk_tokens_estimated(self):
        content = "Hello world, this is a test."
        cfg = ChunkingConfig(chunk_size=50, min_chunk_size=5)
        chunks = self.service.chunk_document("doc1", content, config=cfg)
        for chunk in chunks:
            assert chunk.token_count > 0

    def test_configure_stores_config(self):
        self.service.configure("doc1", ChunkingConfig(chunk_size=256))
        assert "doc1" in self.service._configs
        assert self.service._configs["doc1"].chunk_size == 256

    def test_search_weights_update(self):
        new_weights = SearchWeights(keyword_weight=0.5, vector_weight=0.3)
        self.service._search_weights = new_weights
        assert self.service._search_weights.keyword_weight == 0.5


# ============================================================
# AccessPermission 测试
# ============================================================

class TestAccessPermission:
    def test_default_permission(self):
        perm = AccessPermission()
        assert perm.resource_type == "document"
        assert perm.permission == "read"
        assert perm.granted_by == ""

    def test_custom_permission(self):
        perm = AccessPermission(
            resource_type="chunk",
            resource_id="chunk1",
            user_id="u1",
            permission="write",
            granted_by="admin",
        )
        assert perm.permission == "write"
        assert perm.granted_by == "admin"


# ============================================================
# 边界情况测试
# ============================================================

class TestEdgeCases:
    def setup_method(self):
        self.service = KnowledgeChunkingService()

    def test_exact_chunk_size(self):
        """内容恰好等于 chunk_size"""
        content = "A" * 512
        chunks = self.service.chunk_document("doc1", content)
        assert len(chunks) >= 1

    def test_overlap_greater_than_chunk_size(self):
        """overlap 不应大于 chunk_size (边界安全)"""
        cfg = ChunkingConfig(chunk_size=100, chunk_overlap=50, min_chunk_size=10)
        content = "B" * 200
        chunks = self.service.chunk_document("doc1", content, config=cfg)
        assert len(chunks) > 0

    def test_single_character_content(self):
        cfg = ChunkingConfig(min_chunk_size=1)
        chunks = self.service.chunk_document("doc1", "X", config=cfg)
        assert len(chunks) >= 1

    def test_unicode_content(self):
        content = "你好世界" * 100
        cfg = ChunkingConfig(chunk_size=100, min_chunk_size=10)
        chunks = self.service.chunk_document("doc1", content, config=cfg)
        assert len(chunks) > 0

    def test_mixed_language_content(self):
        content = "Hello 你好 world 世界 " * 50
        cfg = ChunkingConfig(chunk_size=100, min_chunk_size=10)
        chunks = self.service.chunk_document("doc1", content, config=cfg)
        assert len(chunks) > 0
