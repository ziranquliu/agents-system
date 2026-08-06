"""
多智能体监控看板模型 — 指标 / 告警 / 面板
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, Integer, Float, Boolean
from sqlalchemy.sql import func

from app.db.session import Base


class AgentMetric(Base):
    """Agent 指标时间序列"""
    __tablename__ = "agent_metrics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), nullable=False, index=True)
    agent_name = Column(String(100))

    # 指标
    qps = Column(Float, default=0.0)
    success_rate = Column(Float, default=100.0)
    latency_p50 = Column(Float, default=0.0)
    latency_p95 = Column(Float, default=0.0)
    latency_p99 = Column(Float, default=0.0)
    memory_mb = Column(Float, default=0.0)
    cpu_percent = Column(Float, default=0.0)

    # 健康评分（0-100）
    health_score = Column(Float, default=100.0)

    # 时间
    recorded_at = Column(DateTime(timezone=True), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc))


class AlertConfig(Base):
    """告警配置"""
    __tablename__ = "alert_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(Text)
    priority = Column(String(10), default="P2")  # P0 | P1 | P2 | P3

    # 触发条件
    metric_name = Column(String(50), nullable=False)  # qps | success_rate | latency_p50 | latency_p95 | health_score | memory_mb | cpu_percent
    operator = Column(String(10), nullable=False)  # gt | lt | gte | lte | eq
    threshold = Column(Float, nullable=False)
    duration_seconds = Column(Integer, default=60)  # 持续多久触发

    # 范围
    target_type = Column(String(20), default="all")  # all | specific_agent
    target_agent_id = Column(String(36))

    # 通知
    notify_method = Column(String(50))  # webhook | email | system_message
    notify_target = Column(String(200))

    enabled = Column(Boolean, default=True)

    # 静默管理
    silence_start = Column(String(16), nullable=True)   # "HH:MM" UTC — 静默开始时间
    silence_end = Column(String(16), nullable=True)     # "HH:MM" UTC — 静默结束时间
    silence_days = Column(Text, nullable=True)          # JSON: [0,1,2,3,4,5,6] 星期几(0=周一)
    cooldown_minutes = Column(Integer, default=15)      # 同一告警冷却时间(分钟),避免重复通知

    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), default=lambda: datetime.now(timezone.utc))


class AlertRecord(Base):
    """告警记录"""
    __tablename__ = "alert_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    config_id = Column(String(36), index=True)
    alert_name = Column(String(100))
    priority = Column(String(10))

    # 触发详情
    agent_id = Column(String(36), index=True)
    metric_name = Column(String(50))
    current_value = Column(Float)
    threshold = Column(Float)
    operator = Column(String(10))

    # 状态
    status = Column(String(20), default="firing")  # firing | acknowledged | resolved
    acknowledged_by = Column(String(36))
    acknowledged_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True))

    fired_at = Column(DateTime(timezone=True), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc))


class DashboardPanel(Base):
    """自定义看板面板"""
    __tablename__ = "dashboard_panels"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(100), nullable=False)
    chart_type = Column(String(30))  # line | bar | radar | gauge | number | table
    metric_names = Column(Text)  # JSON: ["qps", "latency_p95"]
    agent_ids = Column(Text)  # JSON: ["agent-1", "agent-2"]

    # 布局
    position_x = Column(Integer, default=0)
    position_y = Column(Integer, default=0)
    width = Column(Integer, default=2)
    height = Column(Integer, default=2)

    # 自定义配置
    config = Column(Text)  # JSON

    enabled = Column(Boolean, default=True)
    created_by = Column(String(36))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), default=lambda: datetime.now(timezone.utc))
