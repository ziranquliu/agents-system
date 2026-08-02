"""
各智能体健康监控模型
覆盖：L1-L4 四级健康检查、健康评分（权重可配）、健康面板（Top5/趋势/雷达）
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime, JSON
from sqlalchemy.sql import func

from app.db.session import Base


class HealthLevel:
    L1_ALIVE = "l1_alive"
    L2_READY = "l2_ready"
    L3_CAPABILITY = "l3_capability"
    L4_E2E = "l4_e2e"


class CheckStatus:
    PASS = "pass"
    DEGRADED = "degraded"
    FAIL = "fail"


class AgentHealthStatus:
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"


class HealthCheckRun(Base):
    """健康检查执行记录"""
    __tablename__ = "health_check_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(255), index=True)
    agent_name = Column(String(255))
    level = Column(String(32), default="l1_alive")  # l1_alive/l2_ready/l3_capability/l4_e2e
    status = Column(String(16), default="pass")  # pass/degraded/fail
    latency_ms = Column(Float, nullable=True)
    details = Column(Text, nullable=True)  # JSON
    error_message = Column(Text, nullable=True)
    checked_at = Column(DateTime, default=datetime.utcnow, index=True)


class HealthSnapshot(Base):
    """Agent 健康快照（最新一次四合一检查）"""
    __tablename__ = "health_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(255), unique=True, index=True)
    agent_name = Column(String(255))
    status = Column(String(32), default="healthy")  # healthy/degraded/unhealthy/offline
    score = Column(Float, default=100.0)
    score_details = Column(Text, nullable=True)  # JSON
    l1_status = Column(String(16), default="pass")
    l2_status = Column(String(16), default="pass")
    l3_status = Column(String(16), default="pass")
    l4_status = Column(String(16), default="pass")
    l1_latency = Column(Float, nullable=True)
    l2_latency = Column(Float, nullable=True)
    l3_latency = Column(Float, nullable=True)
    l4_latency = Column(Float, nullable=True)
    l3_failed_items = Column(Text, nullable=True)  # JSON
    uptime_seconds = Column(Float, nullable=True)
    last_checked_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class HealthScoreWeight(Base):
    """健康评分权重模板"""
    __tablename__ = "health_score_weights"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    template_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    weight_response_time = Column(Float, default=30.0)
    weight_token = Column(Float, default=20.0)
    weight_error_rate = Column(Float, default=25.0)
    weight_session_success = Column(Float, default=15.0)
    weight_dependency = Column(Float, default=10.0)
    threshold_p95_warn_ms = Column(Float, default=5000)
    threshold_p95_critical_ms = Column(Float, default=10000)
    threshold_error_rate_warn = Column(Float, default=1.0)
    threshold_error_rate_critical = Column(Float, default=5.0)
    threshold_session_success_warn = Column(Float, default=95.0)
    threshold_session_success_critical = Column(Float, default=80.0)
    apply_agents = Column(Text, nullable=True)  # JSON: agent_id 列表
    is_default = Column(Boolean, default=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentHealthConfig(Base):
    """Agent 健康检查配置"""
    __tablename__ = "agent_health_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(255), unique=True, index=True)
    l1_interval_sec = Column(Integer, default=10)
    l2_interval_sec = Column(Integer, default=30)
    l3_interval_sec = Column(Integer, default=300)
    l4_interval_sec = Column(Integer, default=900)
    ready_endpoint = Column(String(512), nullable=True)
    pid = Column(Integer, nullable=True)
    process_name = Column(String(255), nullable=True)
    l3_skills = Column(Text, nullable=True)  # JSON
    l3_mcp_servers = Column(Text, nullable=True)  # JSON
    l3_model_id = Column(String(255), nullable=True)
    l4_test_prompt = Column(Text, nullable=True)
    auto_restart_on_l1_fail = Column(Boolean, default=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class HealthTrendPoint(Base):
    """健康趋势数据点（定时聚合）"""
    __tablename__ = "health_trend_points"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(255), index=True)
    score = Column(Float, nullable=False)
    bucket_minute = Column(DateTime, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class HealthEvent(Base):
    """健康事件（状态变更/告警）"""
    __tablename__ = "health_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(255), index=True)
    agent_name = Column(String(255))
    event_type = Column(String(128))  # status_change/alarm/recovered
    level = Column(String(32))  # info/warning/critical
    message = Column(Text)
    score_before = Column(Float, nullable=True)
    score_after = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
