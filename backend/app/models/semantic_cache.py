"""
Semantic Cache 模型 - 语义缓存条目

基于查询向量 + 余弦相似度实现语义缓存（A8）：
- 缓存键: query_embedding（查询向量）
- 命中判定: 与缓存条目余弦相似度 > 阈值（如 0.92）
- 存储: answer + 时间戳（TTL 过期清理）
"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.db.session import Base

# 默认语义缓存配置
DEFAULT_SIMILARITY_THRESHOLD = 0.92
DEFAULT_TTL_SECONDS = 3600  # 1 小时


class SemanticCacheEntry(Base):
    """语义缓存条目"""

    __tablename__ = "semantic_cache_entries"

    id = Column(String(36), primary_key=True)
    query_text = Column(Text, nullable=False)  # 原始查询文本（调试用）
    query_embedding = Column(Text, nullable=False)  # 查询向量 JSON 数组
    answer = Column(Text, nullable=False)  # 缓存答案
    model = Column(String(100), nullable=True)  # 命中的模型名（区分不同模型的缓存）
    threshold = Column(Float, default=DEFAULT_SIMILARITY_THRESHOLD)  # 命中阈值
    ttl_seconds = Column(Integer, default=DEFAULT_TTL_SECONDS)  # TTL
    hit_count = Column(Integer, default=0)  # 命中次数（统计用）
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # 过期时间

    @property
    def is_expired(self) -> bool:
        """是否已过期（TTL 内才有效）"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def ttl(self) -> int:
        """剩余 TTL（秒）"""
        if self.expires_at is None:
            return self.ttl_seconds or DEFAULT_TTL_SECONDS
        remain = (self.expires_at - datetime.utcnow()).total_seconds()
        return max(int(remain), 0)

    @classmethod
    def make_expires_at(cls, ttl_seconds: Optional[int]) -> Optional[datetime]:
        """根据 TTL 计算过期时间"""
        if ttl_seconds is None:
            return None
        return datetime.utcnow() + timedelta(seconds=ttl_seconds)
