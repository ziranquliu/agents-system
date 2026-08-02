"""
记忆管理模型 - 三层记忆体系（短期/长期/共享）
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, Integer, Float, Boolean
from sqlalchemy.sql import func

from app.db.session import Base


class MemoryType:
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    SHARED = "shared"


class MemoryCategory:
    CONVERSATION = "conversation"
    KNOWLEDGE = "knowledge"
    PREFERENCE = "preference"
    BEHAVIOR = "behavior"
    CUSTOM = "custom"


class AgentMemory(Base):
    """智能体记忆表 - 覆盖三层记忆"""
    __tablename__ = "agent_memories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), nullable=False, index=True)

    # 记忆层级
    memory_type = Column(String(20), default=MemoryType.LONG_TERM, index=True)

    # 记忆内容
    title = Column(String(200))
    content = Column(Text, nullable=False)
    summary = Column(String(500))
    category = Column(String(30), default=MemoryCategory.CONVERSATION, index=True)

    # 标签和关键词（JSON）
    tags = Column(Text)
    keywords = Column(Text)

    # 嵌入向量引用
    embedding_text = Column(Text)
    embedding_vector_id = Column(String(100))

    # 重要性评分
    importance_score = Column(Float, default=0.0, index=True)
    access_count = Column(Integer, default=0)
    last_accessed_at = Column(DateTime(timezone=True))

    # 遗忘与生命周期
    is_forgotten = Column(Boolean, default=False)
    forget_reason = Column(String(100))
    forgotten_at = Column(DateTime(timezone=True))
    ttl_seconds = Column(Integer)
    expires_at = Column(DateTime(timezone=True))

    # 隐私与合规
    is_sensitive = Column(Boolean, default=False)
    sensitive_info_type = Column(String(50))
    masked_content = Column(Text)

    # 来源
    source_type = Column(String(50))
    source_id = Column(String(36))
    created_by = Column(String(36))

    # 共享记忆相关
    shared_to_agents = Column(Text)
    is_public = Column(Boolean, default=False)

    # 元数据
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class MemoryAnalytics(Base):
    """记忆分析统计表"""
    __tablename__ = "memory_analytics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), nullable=False, index=True)
    period = Column(String(20))

    # 统计
    total_memories = Column(Integer, default=0)
    short_term_count = Column(Integer, default=0)
    long_term_count = Column(Integer, default=0)
    shared_count = Column(Integer, default=0)
    forgotten_count = Column(Integer, default=0)
    merged_count = Column(Integer, default=0)

    # 类型分布（JSON）
    category_distribution = Column(Text)

    # 重要性分布
    avg_importance = Column(Float, default=0.0)
    high_importance_count = Column(Integer, default=0)
    medium_importance_count = Column(Integer, default=0)
    low_importance_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
