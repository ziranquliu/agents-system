"""
4.16 Token 使用管理与优化 模型
覆盖：Token 用量持久化记录、用户配额与预算、预算告警、模型级联规则、优化效果统计
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text
from sqlalchemy.sql import func

from app.db.session import Base


class TokenUsage(Base):
    """Token 用量记录（持久化，按请求粒度）"""
    __tablename__ = "token_usages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), index=True)
    agent_id = Column(String(36), index=True, nullable=True)
    conversation_id = Column(String(36), index=True, nullable=True)
    model_name = Column(String(100), index=True)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cached_tokens = Column(Integer, default=0)  # 缓存命中 token 数
    compressed_tokens = Column(Integer, default=0)  # 上下文裁剪节省 token 数
    cost = Column(Float, default=0.0)  # USD
    usage_date = Column(String(10), index=True)  # YYYY-MM-DD（便于按日聚合）
    # 成本分摊
    project_id = Column(String(100), nullable=True, index=True)    # 项目 ID
    department = Column(String(100), nullable=True, index=True)    # 部门名称
    tags = Column(Text, nullable=True)  # JSON: 自定义标签 {"env": "prod", "team": "ai"}
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc))


class TokenBudget(Base):
    """用户 Token 预算与配额（成本控制）"""
    __tablename__ = "token_budgets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), unique=True, index=True)
    monthly_budget = Column(Float, default=10.0)  # 月度预算上限（USD）
    token_quota = Column(Integer, default=10_000_000)  # 月度 Token 配额
    alert_threshold = Column(Integer, default=80)  # 用量达阈值比例(%)时告警
    block_when_exceeded = Column(Boolean, default=False)  # 超限是否阻断
    cascade_enabled = Column(Boolean, default=True)  # 是否启用模型级联降级
    cascade_chain = Column(Text, nullable=True)  # JSON: ["gpt-4o","gpt-4o-mini","deepseek-chat"]
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), default=lambda: datetime.now(timezone.utc))


class TokenAlert(Base):
    """Token 预算/配额告警"""
    __tablename__ = "token_alerts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), index=True)
    alert_type = Column(String(32))  # budget / quota / cascade
    severity = Column(String(16), default="warning")  # info | warning | critical
    message = Column(String(255))
    threshold_pct = Column(Integer, nullable=True)
    current_usage = Column(Float, nullable=True)
    status = Column(String(16), default="open")  # open | acknowledged | resolved
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc))


class ModelCascadeRule(Base):
    """模型级联规则（任务类型 → 降级链）"""
    __tablename__ = "model_cascade_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_type = Column(String(32), unique=True, index=True)  # chat / code / analysis / writing / translation
    primary_model = Column(String(100))
    fallback_chain = Column(Text, nullable=True)  # JSON 数组（降级顺序）
    max_input_tokens = Column(Integer, default=8000)
    enabled = Column(Boolean, default=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), default=lambda: datetime.now(timezone.utc))


class TokenOptimizationStat(Base):
    """Token 优化效果评估（压缩率/缓存命中率/成本节省）"""
    __tablename__ = "token_optimization_stats"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    usage_date = Column(String(10), index=True)  # YYYY-MM-DD
    total_input = Column(Integer, default=0)
    total_output = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    cached_tokens = Column(Integer, default=0)
    compressed_tokens = Column(Integer, default=0)
    cascade_saved_cost = Column(Float, default=0.0)  # 级联降级节省成本
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc))
