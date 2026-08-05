"""
对话功能增强模型 — Human-in-the-loop / 质量评分 / 满意度
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, Integer, Float, Boolean
from sqlalchemy.sql import func

from app.db.session import Base


class HumanIntervention(Base):
    """人工介入记录 (Human-in-the-loop)"""
    __tablename__ = "human_interventions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), nullable=False, index=True)
    message_id = Column(String(36))  # 被介入的消息
    agent_id = Column(String(36), nullable=False, index=True)

    # 介入类型
    intervention_type = Column(String(20), nullable=False)  # review | approve | reject | modify | override | pause

    # 介入前内容
    original_content = Column(Text)
    original_metadata = Column(Text)  # JSON

    # 修改后内容
    modified_content = Column(Text)
    modified_metadata = Column(Text)  # JSON

    # 审批
    approved = Column(Boolean)
    approval_note = Column(Text)

    # 处理人
    handled_by = Column(String(36))  # user_id
    handled_at = Column(DateTime(timezone=True))

    # 状态
    status = Column(String(20), default="pending")  # pending | approved | rejected | modified

    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), default=lambda: datetime.now(timezone.utc))


class DialogueRating(Base):
    """对话质量评分与满意度"""
    __tablename__ = "dialogue_ratings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), nullable=False, index=True)
    message_id = Column(String(36))  # 针对某条消息评分

    # 满意度（1-5分）
    satisfaction_score = Column(Integer)  # 1-5

    # 质量评分维度（1-10分）
    relevance_score = Column(Integer)    # 相关性
    accuracy_score = Column(Integer)     # 准确性
    completeness_score = Column(Integer) # 完整性
    clarity_score = Column(Integer)      # 清晰度
    speed_score = Column(Integer)        # 响应速度

    # 综合评分（自动计算）
    overall_score = Column(Float)

    # 反馈
    feedback_text = Column(Text)
    feedback_category = Column(String(30))  # positive | negative | neutral | bug_report | feature_request

    # 评分来源
    rated_by = Column(String(36))  # user_id or system
    rated_by_type = Column(String(20))  # user | system | admin

    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc))


class RatingAnalytics(Base):
    """评分分析快照"""
    __tablename__ = "rating_analytics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    period = Column(String(20))  # daily | weekly | monthly

    total_ratings = Column(Integer, default=0)
    avg_satisfaction = Column(Float, default=0.0)
    avg_relevance = Column(Float, default=0.0)
    avg_accuracy = Column(Float, default=0.0)
    avg_completeness = Column(Float, default=0.0)
    avg_clarity = Column(Float, default=0.0)
    avg_speed = Column(Float, default=0.0)
    avg_overall = Column(Float, default=0.0)

    # 分布
    satisfaction_distribution = Column(Text)  # JSON: {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    category_distribution = Column(Text)  # JSON: {"positive": 10, "negative": 2}

    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc))
