"""
知识库分块与混合搜索服务

功能:
- 自定义分块策略（大小/重叠/分隔符）
- 混合搜索（向量 + 关键词）权重配置
- 检索测试
- 文档级/段落级权限控制
- 分块统计
"""

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ChunkingStrategy(str, Enum):
    FIXED_SIZE = "fixed_size"       # 固定大小
    SENTENCE = "sentence"           # 按句子
    PARAGRAPH = "paragraph"         # 按段落
    SEMANTIC = "semantic"           # 按语义（基于分隔符）
    RECURSIVE = "recursive"         # 递归分割


class SearchMode(str, Enum):
    VECTOR_ONLY = "vector_only"
    KEYWORD_ONLY = "keyword_only"
    HYBRID = "hybrid"


@dataclass
class ChunkingConfig:
    """分块配置"""
    strategy: ChunkingStrategy = ChunkingStrategy.FIXED_SIZE
    chunk_size: int = 500          # 字符数
    chunk_overlap: int = 50        # 重叠字符数
    separators: list[str] = field(default_factory=lambda: ["\n\n", "\n", "。", ".", " "])
    min_chunk_size: int = 50
    max_chunk_size: int = 2000


@dataclass
class SearchWeights:
    """搜索权重配置"""
    vector_weight: float = 0.7     # 向量搜索权重
    keyword_weight: float = 0.3    # 关键词搜索权重
    recency_boost: float = 0.1     # 时间新鲜度加权
    popularity_boost: float = 0.05 # 热度加权


@dataclass
class Chunk:
    """分块"""
    id: str = ""
    document_id: str = ""
    chunk_index: int = 0
    content: str = ""
    start_pos: int = 0
    end_pos: int = 0
    token_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """搜索结果"""
    chunk_id: str = ""
    document_id: str = ""
    content: str = ""
    score: float = 0.0
    vector_score: float = 0.0
    keyword_score: float = 0.0
    rank: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AccessPermission:
    """访问权限"""
    resource_type: str = "document"  # document / chunk
    resource_id: str = ""
    user_id: str = ""
    permission: str = "read"        # read / write / admin
    granted_by: str = ""
    granted_at: Optional[datetime] = None


class KnowledgeChunkingService:
    """
    知识库分块与混合搜索服务
    """

    def __init__(self):
        self._configs: dict[str, ChunkingConfig] = {}
        self._search_weights: SearchWeights = SearchWeights()
        self._permissions: dict[str, list[AccessPermission]] = {}
        self._search_history: list[dict[str, Any]] = []

    # ----------------------------------------------------------
    # 分块
    # ----------------------------------------------------------

    def configure(
        self,
        document_id: str,
        config: Optional[ChunkingConfig] = None,
    ) -> ChunkingConfig:
        """配置文档分块策略"""
        if config is None:
            config = ChunkingConfig()
        self._configs[document_id] = config
        return config

    def chunk_document(
        self,
        document_id: str,
        content: str,
        config: Optional[ChunkingConfig] = None,
    ) -> list[Chunk]:
        """对文档进行分块"""
        if config is None:
            config = self._configs.get(document_id, ChunkingConfig())

        if config.strategy == ChunkingStrategy.FIXED_SIZE:
            chunks = self._chunk_fixed_size(document_id, content, config)
        elif config.strategy == ChunkingStrategy.SENTENCE:
            chunks = self._chunk_by_sentence(document_id, content, config)
        elif config.strategy == ChunkingStrategy.PARAGRAPH:
            chunks = self._chunk_by_paragraph(document_id, content, config)
        elif config.strategy == ChunkingStrategy.SEMANTIC:
            chunks = self._chunk_by_separators(document_id, content, config)
        elif config.strategy == ChunkingStrategy.RECURSIVE:
            chunks = self._chunk_recursive(document_id, content, config)
        else:
            chunks = self._chunk_fixed_size(document_id, content, config)

        logger.info(f"Document {document_id} chunked into {len(chunks)} pieces (strategy={config.strategy.value})")
        return chunks

    def _chunk_fixed_size(self, doc_id: str, content: str, config: ChunkingConfig) -> list[Chunk]:
        """固定大小分块"""
        chunks = []
        pos = 0
        idx = 0
        while pos < len(content):
            end = min(pos + config.chunk_size, len(content))
            chunk_content = content[pos:end]
            if len(chunk_content) >= config.min_chunk_size:
                chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    document_id=doc_id,
                    chunk_index=idx,
                    content=chunk_content,
                    start_pos=pos,
                    end_pos=end,
                    token_count=self._estimate_tokens(chunk_content),
                ))
                idx += 1
            pos += config.chunk_size - config.chunk_overlap
        return chunks

    def _chunk_by_sentence(self, doc_id: str, content: str, config: ChunkingConfig) -> list[Chunk]:
        """按句子分块"""
        sentences = re.split(r'([。！？\.!\?])', content)
        chunks = []
        current = ""
        pos = 0
        idx = 0

        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            punct = sentences[i + 1] if i + 1 < len(sentences) else ""
            piece = sentence + punct

            if len(current) + len(piece) > config.chunk_size and current:
                if len(current) >= config.min_chunk_size:
                    chunks.append(Chunk(
                        id=str(uuid.uuid4()),
                        document_id=doc_id,
                        chunk_index=idx,
                        content=current,
                        start_pos=pos,
                        end_pos=pos + len(current),
                        token_count=self._estimate_tokens(current),
                    ))
                    idx += 1
                    pos += len(current) - config.chunk_overlap
                current = piece
            else:
                current += piece

        if current and len(current) >= config.min_chunk_size:
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                chunk_index=idx,
                content=current,
                start_pos=pos,
                end_pos=pos + len(current),
                token_count=self._estimate_tokens(current),
            ))
        return chunks

    def _chunk_by_paragraph(self, doc_id: str, content: str, config: ChunkingConfig) -> list[Chunk]:
        """按段落分块"""
        paragraphs = content.split("\n\n")
        chunks = []
        current = ""
        pos = 0
        idx = 0

        for para in paragraphs:
            if len(current) + len(para) > config.chunk_size and current:
                chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    document_id=doc_id,
                    chunk_index=idx,
                    content=current.strip(),
                    start_pos=pos,
                    end_pos=pos + len(current),
                    token_count=self._estimate_tokens(current),
                ))
                idx += 1
                pos += len(current)
                current = para + "\n\n"
            else:
                current += para + "\n\n"

        if current.strip() and len(current.strip()) >= config.min_chunk_size:
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                chunk_index=idx,
                content=current.strip(),
                start_pos=pos,
                end_pos=pos + len(current),
                token_count=self._estimate_tokens(current),
            ))
        return chunks

    def _chunk_by_separators(self, doc_id: str, content: str, config: ChunkingConfig) -> list[Chunk]:
        """按语义分隔符分块"""
        chunks = []
        current = content
        idx = 0

        for sep in config.separators:
            if len(current) <= config.chunk_size:
                break
            parts = current.split(sep)
            current = ""
            for part in parts:
                if len(current) + len(part) + len(sep) > config.chunk_size:
                    if current and len(current) >= config.min_chunk_size:
                        chunks.append(Chunk(
                            id=str(uuid.uuid4()),
                            document_id=doc_id,
                            chunk_index=idx,
                            content=current,
                            start_pos=0,
                            end_pos=len(current),
                            token_count=self._estimate_tokens(current),
                        ))
                        idx += 1
                    current = part
                else:
                    current += part + sep

        if current and len(current) >= config.min_chunk_size:
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                chunk_index=idx,
                content=current,
                start_pos=0,
                end_pos=len(current),
                token_count=self._estimate_tokens(current),
            ))
        return chunks

    def _chunk_recursive(self, doc_id: str, content: str, config: ChunkingConfig) -> list[Chunk]:
        """递归分割"""
        if len(content) <= config.chunk_size:
            return [Chunk(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                chunk_index=0,
                content=content,
                token_count=self._estimate_tokens(content),
            )]

        mid = len(content) // 2
        # 尝试在最近的分隔符处分割
        best_sep_pos = mid
        for sep in config.separators:
            pos = content.rfind(sep, mid - 100, mid + 100)
            if pos > 0:
                best_sep_pos = pos + len(sep)
                break

        left = content[:best_sep_pos]
        right = content[best_sep_pos:]

        left_chunks = self._chunk_recursive(doc_id, left, config)
        right_chunks = self._chunk_recursive(doc_id, right, config)

        # 更新索引
        for i, chunk in enumerate(right_chunks):
            chunk.chunk_index = len(left_chunks) + i

        return left_chunks + right_chunks

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """粗略估算 token 数"""
        return max(1, len(text) // 2)

    # ----------------------------------------------------------
    # 混合搜索
    # ----------------------------------------------------------

    def configure_search(self, weights: SearchWeights):
        """配置搜索权重"""
        self._search_weights = weights

    def hybrid_search(
        self,
        query: str,
        vector_results: Optional[list[dict[str, Any]]] = None,
        keyword_results: Optional[list[dict[str, Any]]] = None,
        mode: SearchMode = SearchMode.HYBRID,
        limit: int = 10,
    ) -> list[SearchResult]:
        """
        混合搜索

        vector_results: [{"chunk_id": "...", "score": 0.9, "content": "..."}]
        keyword_results: [{"chunk_id": "...", "score": 0.8, "content": "..."}]
        """
        vector_results = vector_results or []
        keyword_results = keyword_results or []
        w = self._search_weights

        if mode == SearchMode.VECTOR_ONLY:
            return self._merge_results(vector_results, [], w.vector_weight, 0, limit)
        elif mode == SearchMode.KEYWORD_ONLY:
            return self._merge_results([], keyword_results, 0, w.keyword_weight, limit)
        else:
            return self._merge_results(vector_results, keyword_results, w.vector_weight, w.keyword_weight, limit)

    def _merge_results(
        self,
        vector_results: list[dict],
        keyword_results: list[dict],
        v_weight: float,
        k_weight: float,
        limit: int,
    ) -> list[SearchResult]:
        """合并搜索结果"""
        scores: dict[str, dict[str, float]] = {}

        for r in vector_results:
            cid = r.get("chunk_id", "")
            if cid not in scores:
                scores[cid] = {"vector": 0, "keyword": 0, "content": r.get("content", ""), "doc_id": r.get("document_id", "")}
            scores[cid]["vector"] = r.get("score", 0) * v_weight

        for r in keyword_results:
            cid = r.get("chunk_id", "")
            if cid not in scores:
                scores[cid] = {"vector": 0, "keyword": 0, "content": r.get("content", ""), "doc_id": r.get("document_id", "")}
            scores[cid]["keyword"] = r.get("score", 0) * k_weight

        # 计算综合分
        results = []
        for cid, data in scores.items():
            combined = data["vector"] + data["keyword"]
            results.append(SearchResult(
                chunk_id=cid,
                document_id=data["doc_id"],
                content=data["content"],
                score=combined,
                vector_score=data["vector"],
                keyword_score=data["keyword"],
            ))

        results.sort(key=lambda x: x.score, reverse=True)

        for i, r in enumerate(results[:limit]):
            r.rank = i + 1

        return results[:limit]

    # ----------------------------------------------------------
    # 权限控制
    # ----------------------------------------------------------

    def grant_permission(
        self,
        resource_type: str,
        resource_id: str,
        user_id: str,
        permission: str = "read",
        granted_by: str = "",
    ) -> AccessPermission:
        perm = AccessPermission(
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            permission=permission,
            granted_by=granted_by,
            granted_at=datetime.now(timezone.utc),
        )
        key = f"{resource_type}:{resource_id}"
        if key not in self._permissions:
            self._permissions[key] = []
        self._permissions[key].append(perm)
        return perm

    def check_permission(
        self,
        resource_type: str,
        resource_id: str,
        user_id: str,
        permission: str = "read",
    ) -> bool:
        """检查权限"""
        key = f"{resource_type}:{resource_id}"
        perms = self._permissions.get(key, [])
        for p in perms:
            if p.user_id == user_id and p.permission in (permission, "admin", "write"):
                return True
        # 检查通配符
        wildcard_key = f"{resource_type}:*"
        for p in self._permissions.get(wildcard_key, []):
            if p.user_id == user_id and p.permission in (permission, "admin"):
                return True
        return False

    def revoke_permission(self, resource_type: str, resource_id: str, user_id: str) -> bool:
        key = f"{resource_type}:{resource_id}"
        if key in self._permissions:
            before = len(self._permissions[key])
            self._permissions[key] = [
                p for p in self._permissions[key] if p.user_id != user_id
            ]
            return len(self._permissions[key]) < before
        return False

    def list_permissions(self, resource_type: str = "", resource_id: str = "") -> list[dict[str, Any]]:
        results = []
        for key, perms in self._permissions.items():
            rt, rid = key.split(":", 1) if ":" in key else (key, "")
            if resource_type and rt != resource_type:
                continue
            if resource_id and rid != resource_id:
                continue
            for p in perms:
                results.append({
                    "resource_type": p.resource_type,
                    "resource_id": p.resource_id,
                    "user_id": p.user_id,
                    "permission": p.permission,
                    "granted_by": p.granted_by,
                })
        return results
