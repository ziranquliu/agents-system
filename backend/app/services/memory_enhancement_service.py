"""
记忆管理增强服务 — 重要性评分自动遗忘 / 合并去重 / 遗忘追溯 / 词云 / 分布图

功能:
1. 重要性评分自动遗忘: 综合 LRU + 重要性分 → 自动压缩/归档
2. 记忆合并与去重: 定期语义相似度去重 (cosine > 0.95)
3. 遗忘记录追溯: 查看被自动遗忘的记忆内容及原因
4. 高频记忆词云: 提取记忆高频实体生成词云数据
5. 记忆类型分布: 短期/长期/共享记忆占比统计

设计:
  本服务基于 memory_service 已有的数据模型进行增强。
  所有操作均为异步, 支持大规模记忆数据处理。
"""

import asyncio
import logging
import math
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ForgottenMemory:
    """遗忘记忆记录"""
    id: str = ""
    agent_id: str = ""
    content: str = ""
    memory_type: str = ""
    importance_score: float = 0.0
    access_count: int = 0
    forgotten_at: str = ""
    forget_reason: str = ""  # low_importance / lru_expired / merged / manual
    original_importance: float = 0.0


@dataclass
class MergeCandidate:
    """合并候选"""
    memory_a_id: str = ""
    memory_b_id: str = ""
    similarity: float = 0.0
    content_a: str = ""
    content_b: str = ""
    merged_content: str = ""


@dataclass
class WordCloudEntry:
    """词云条目"""
    word: str = ""
    count: int = 0
    weight: float = 0.0
    category: str = ""  # entity / topic / action / concept


@dataclass
class TypeDistribution:
    """记忆类型分布"""
    memory_type: str = ""
    count: int = 0
    percentage: float = 0.0
    avg_importance: float = 0.0
    avg_access_count: float = 0.0
    oldest_memory_age_days: float = 0.0
    newest_memory_age_days: float = 0.0


class MemoryEnhancementService:
    """
    记忆管理增强服务

    - 重要性自动遗忘: importance = 0.4×recency + 0.3×frequency + 0.3×relevance
    - 合并去重: cosine > 0.95 → 合并
    - 遗忘追溯: 全量遗忘记录, 支持恢复
    - 词云: TF-IDF 提取高频实体
    - 分布: 按类型统计
    """

    # 遗忘阈值
    LOW_IMPORTANCE_THRESHOLD = 0.2  # 重要性低于此值会被遗忘
    LRU_EXPIRY_DAYS = 30  # 30 天未访问
    MERGE_SIMILARITY_THRESHOLD = 0.95  # 相似度高于此值合并
    MAX_FORGOTTEN_RECORDS = 10000  # 最多保留 10000 条遗忘记录

    # 停用词
    STOP_WORDS = {
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
        "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "to", "of", "in", "for", "on", "with",
        "at", "by", "from", "it", "this", "that", "as", "i", "you", "he", "she",
        "we", "they", "me", "him", "her", "us", "them", "my", "your", "his",
        "our", "their", "and", "or", "but", "not", "so", "if", "then",
    }

    def __init__(self):
        self._forgotten_records: list[ForgottenMemory] = []
        self._merge_history: list[MergeCandidate] = []
        self._word_cloud_cache: dict[str, list[WordCloudEntry]] = {}
        self._stats: dict[str, Any] = {}

    # ----------------------------------------------------------
    # 1. 重要性评分计算
    # ----------------------------------------------------------

    def compute_importance(
        self,
        created_at: float,
        last_accessed: float,
        access_count: int,
        relevance_score: float = 0.5,
    ) -> float:
        """
        计算记忆重要性分数 (0-1)

        importance = 0.4 × recency + 0.3 × frequency + 0.3 × relevance
        """
        now = time.time()

        # 1. 时效性 (越新越高)
        age_days = max(0, (now - created_at) / 86400)
        recency = max(0, 1.0 - age_days / 90)  # 90 天衰减到 0

        # 2. 访问频率
        frequency = min(1.0, access_count / 20)  # 20 次达到满分

        # 3. 相关性 (外部传入)
        relevance = max(0, min(1.0, relevance_score))

        importance = 0.4 * recency + 0.3 * frequency + 0.3 * relevance
        return round(importance, 4)

    # ----------------------------------------------------------
    # 2. 自动遗忘
    # ----------------------------------------------------------

    async def auto_forget(
        self,
        memories: list[dict],
        threshold: float = 0.0,
    ) -> dict:
        """
        自动遗忘低重要性记忆

        遗忘条件:
        1. 重要性 < threshold
        2. 超过 LRU_EXPIRY_DAYS 未访问
        """
        actual_threshold = threshold or self.LOW_IMPORTANCE_THRESHOLD
        forgotten = []
        kept = []

        for mem in memories:
            importance = mem.get("importance_score", 0)
            last_accessed = mem.get("last_accessed", mem.get("created_at", 0))
            access_count = mem.get("access_count", 0)
            created_at = mem.get("created_at", time.time())

            computed = self.compute_importance(created_at, last_accessed, access_count, importance)
            age_days = (time.time() - last_accessed) / 86400 if last_accessed else 999

            should_forget = False
            reason = ""

            if computed < actual_threshold:
                should_forget = True
                reason = "low_importance"
            elif age_days > self.LRU_EXPIRY_DAYS:
                should_forget = True
                reason = "lru_expired"

            if should_forget:
                record = ForgottenMemory(
                    id=mem.get("id", ""),
                    agent_id=mem.get("agent_id", ""),
                    content=mem.get("content", "")[:500],
                    memory_type=mem.get("memory_type", ""),
                    importance_score=computed,
                    access_count=access_count,
                    forgotten_at=datetime.now(timezone.utc).isoformat(),
                    forget_reason=reason,
                    original_importance=importance,
                )
                forgotten.append(record)
                self._forgotten_records.append(record)
            else:
                kept.append(mem.get("id", ""))

        # 限制遗忘记录数量
        if len(self._forgotten_records) > self.MAX_FORGOTTEN_RECORDS:
            self._forgotten_records = self._forgotten_records[-self.MAX_FORGOTTEN_RECORDS:]

        return {
            "total_evaluated": len(memories),
            "forgotten": len(forgotten),
            "kept": len(kept),
            "forgotten_ids": [f.id for f in forgotten],
            "kept_ids": kept,
            "reasons": {
                "low_importance": sum(1 for f in forgotten if f.forget_reason == "low_importance"),
                "lru_expired": sum(1 for f in forgotten if f.forget_reason == "lru_expired"),
            },
        }

    # ----------------------------------------------------------
    # 3. 记忆合并与去重
    # ----------------------------------------------------------

    async def merge_duplicates(
        self,
        memories: list[dict],
        similarity_threshold: float = 0.0,
    ) -> dict:
        """
        合并语义相似的记忆

        相似度 > threshold → 合并为一条
        """
        threshold = similarity_threshold or self.MERGE_SIMILARITY_THRESHOLD
        candidates: list[MergeCandidate] = []
        merged_ids: set[str] = set()

        for i in range(len(memories)):
            if memories[i].get("id") in merged_ids:
                continue
            for j in range(i + 1, len(memories)):
                if memories[j].get("id") in merged_ids:
                    continue

                vec_a = memories[i].get("embedding_vector", [])
                vec_b = memories[j].get("embedding_vector", [])

                if vec_a and vec_b and len(vec_a) == len(vec_b):
                    sim = self._cosine_similarity(vec_a, vec_b)
                else:
                    sim = self._text_similarity(
                        memories[i].get("content", ""),
                        memories[j].get("content", ""),
                    )

                if sim >= threshold:
                    merged_content = self._merge_content(
                        memories[i].get("content", ""),
                        memories[j].get("content", ""),
                    )
                    candidates.append(MergeCandidate(
                        memory_a_id=memories[i].get("id", ""),
                        memory_b_id=memories[j].get("id", ""),
                        similarity=round(sim, 4),
                        content_a=memories[i].get("content", "")[:200],
                        content_b=memories[j].get("content", "")[:200],
                        merged_content=merged_content[:500],
                    ))
                    # 保留较高重要性的记忆, 标记另一个为合并
                    imp_a = memories[i].get("importance_score", 0)
                    imp_b = memories[j].get("importance_score", 0)
                    if imp_a >= imp_b:
                        merged_ids.add(memories[j].get("id", ""))
                    else:
                        merged_ids.add(memories[i].get("id", ""))

        self._merge_history.extend(candidates)

        return {
            "total_evaluated": len(memories),
            "merge_candidates": len(candidates),
            "merged_ids": list(merged_ids),
            "candidates": [
                {
                    "a": c.memory_a_id,
                    "b": c.memory_b_id,
                    "similarity": c.similarity,
                    "merged_preview": c.merged_content[:200],
                }
                for c in candidates[:50]
            ],
        }

    # ----------------------------------------------------------
    # 4. 遗忘记录追溯
    # ----------------------------------------------------------

    def get_forgotten_records(
        self,
        agent_id: str = "",
        reason: str = "",
        limit: int = 100,
    ) -> list[dict]:
        """获取遗忘记录"""
        records = self._forgotten_records

        if agent_id:
            records = [r for r in records if r.agent_id == agent_id]
        if reason:
            records = [r for r in records if r.forget_reason == reason]

        return [
            {
                "id": r.id,
                "agent_id": r.agent_id,
                "content": r.content,
                "memory_type": r.memory_type,
                "importance_score": r.importance_score,
                "access_count": r.access_count,
                "forgotten_at": r.forgotten_at,
                "forget_reason": r.forget_reason,
                "original_importance": r.original_importance,
            }
            for r in records[-limit:]
        ]

    def restore_forgotten(self, memory_id: str) -> dict:
        """恢复已遗忘的记忆"""
        for i, r in enumerate(self._forgotten_records):
            if r.id == memory_id:
                restored = self._forgotten_records.pop(i)
                return {
                    "restored": True,
                    "memory_id": restored.id,
                    "content": restored.content,
                    "agent_id": restored.agent_id,
                }
        return {"restored": False, "error": "遗忘记录不存在"}

    def get_forget_statistics(self) -> dict:
        """遗忘统计"""
        reasons = Counter(r.forget_reason for r in self._forgotten_records)
        types = Counter(r.memory_type for r in self._forgotten_records)
        return {
            "total_forgotten": len(self._forgotten_records),
            "by_reason": dict(reasons),
            "by_type": dict(types),
            "avg_importance_when_forgotten": (
                round(sum(r.importance_score for r in self._forgotten_records) / max(len(self._forgotten_records), 1), 4)
            ),
        }

    # ----------------------------------------------------------
    # 5. 高频记忆词云
    # ----------------------------------------------------------

    def generate_word_cloud(
        self,
        memories: list[dict],
        max_words: int = 200,
    ) -> list[dict]:
        """
        生成词云数据

        基于 TF 权重 + 重要性加权
        """
        word_counter: Counter = Counter()
        word_importance: dict[str, float] = defaultdict(float)

        for mem in memories:
            content = mem.get("content", "")
            importance = mem.get("importance_score", 0.5)
            words = self._extract_words(content)

            for word in words:
                word_counter[word] += 1
                word_importance[word] = max(word_importance[word], importance)

        # 计算权重 = TF × importance
        entries: list[WordCloudEntry] = []
        max_count = max(word_counter.values()) if word_counter else 1

        for word, count in word_counter.most_common(max_words):
            weight = (count / max_count) * word_importance.get(word, 0.5)
            category = self._categorize_word(word)
            entries.append(WordCloudEntry(
                word=word,
                count=count,
                weight=round(weight, 4),
                category=category,
            ))

        # 按权重排序
        entries.sort(key=lambda e: e.weight, reverse=True)

        return [
            {"word": e.word, "count": e.count, "weight": e.weight, "category": e.category}
            for e in entries
        ]

    # ----------------------------------------------------------
    # 6. 记忆类型分布
    # ----------------------------------------------------------

    def get_type_distribution(self, memories: list[dict]) -> list[dict]:
        """
        记忆类型分布统计

        返回每种类型的:
        - count: 数量
        - percentage: 占比
        - avg_importance: 平均重要性
        - avg_access_count: 平均访问次数
        - age_range: 最老/最新记忆的年龄
        """
        now = time.time()
        by_type: dict[str, list[dict]] = defaultdict(list)
        for mem in memories:
            mem_type = mem.get("memory_type", "unknown")
            by_type[mem_type].append(mem)

        total = len(memories) or 1
        distributions: list[TypeDistribution] = []

        for mem_type, mems in by_type.items():
            count = len(mems)
            avg_importance = sum(m.get("importance_score", 0) for m in mems) / max(count, 1)
            avg_access = sum(m.get("access_count", 0) for m in mems) / max(count, 1)

            ages = [
                (now - m.get("created_at", now)) / 86400
                for m in mems
                if m.get("created_at")
            ]
            oldest = max(ages) if ages else 0
            newest = min(ages) if ages else 0

            distributions.append(TypeDistribution(
                memory_type=mem_type,
                count=count,
                percentage=round(count / total * 100, 1),
                avg_importance=round(avg_importance, 4),
                avg_access_count=round(avg_access, 1),
                oldest_memory_age_days=round(oldest, 1),
                newest_memory_age_days=round(newest, 1),
            ))

        distributions.sort(key=lambda d: d.count, reverse=True)

        return [
            {
                "memory_type": d.memory_type,
                "count": d.count,
                "percentage": d.percentage,
                "avg_importance": d.avg_importance,
                "avg_access_count": d.avg_access_count,
                "oldest_memory_age_days": d.oldest_memory_age_days,
                "newest_memory_age_days": d.newest_memory_age_days,
            }
            for d in distributions
        ]

    # ----------------------------------------------------------
    # 工具方法
    # ----------------------------------------------------------

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return sum(x * y for x, y in zip(a, b)) / (norm_a * norm_b)

    def _text_similarity(self, text_a: str, text_b: str) -> float:
        """基于词汇重叠的文本相似度"""
        words_a = set(self._extract_words(text_a))
        words_b = set(self._extract_words(text_b))
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / max(len(union), 1)

    def _extract_words(self, text: str) -> list[str]:
        """提取关键词"""
        text_lower = text.lower()
        cn_words = re.findall(r'[\u4e00-\u9fff]{2,6}', text_lower)
        en_words = re.findall(r'[a-z_][a-z0-9_]{1,30}', text_lower)
        return [w for w in cn_words + en_words if w not in self.STOP_WORDS and len(w) >= 2]

    def _merge_content(self, content_a: str, content_b: str) -> str:
        """合并两条内容 (取较长的 + 补充)"""
        if len(content_a) >= len(content_b):
            return content_a
        return content_b

    def _categorize_word(self, word: str) -> str:
        """简单词性分类"""
        if re.match(r'^[a-z_][a-z0-9_]+$', word):
            return "entity"
        if any(kw in word for kw in ["模型", "算法", "训练", "推理", "network", "model", "train"]):
            return "concept"
        if any(kw in word for kw in ["创建", "删除", "修改", "执行", "create", "delete", "run"]):
            return "action"
        return "topic"


# 全局实例
_memory_enhancement_service: Optional[MemoryEnhancementService] = None


def get_memory_enhancement_service() -> MemoryEnhancementService:
    global _memory_enhancement_service
    if _memory_enhancement_service is None:
        _memory_enhancement_service = MemoryEnhancementService()
    return _memory_enhancement_service
