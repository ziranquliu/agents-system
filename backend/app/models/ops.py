"""
智能体自动化运维模型
覆盖：自动部署、Auto Scaling、日志管理、定期维护、异常自愈、运维报告
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime

from app.db.session import Base


class AgentDeploymentStatus:
    PENDING = "pending"
    DEPLOYING = "deploying"
    HEALTH_CHECKING = "health_checking"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ScalingMetricType:
    QPS = "qps"
    TOKEN_RATE = "token_rate"
    P95_LATENCY = "p95_latency"
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"


class ScalingDirection:
    SCALE_OUT = "scale_out"
    SCALE_IN = "scale_in"


class LogSourceType:
    AGENT = "agent"
    SKILL = "skill"
    MCP = "mcp"
    SYSTEM = "system"


class LogLevel:
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    FATAL = "FATAL"


class MaintenanceType:
    SESSION_CLEANUP = "session_cleanup"
    CACHE_CLEANUP = "cache_cleanup"
    TEMP_FILE_CLEANUP = "temp_file_cleanup"
    INDEX_REBUILD = "index_rebuild"
    STATISTICS_ANALYSIS = "statistics_analysis"


class HealLevel:
    LEVEL_1_RESTART = "restart"
    LEVEL_2_ROLLBACK = "rollback"
    LEVEL_3_DEGRADE = "degrade"


class HealStatus:
    DETECTED = "detected"
    HEALING = "healing"
    VERIFYING = "verifying"
    SUCCESS = "success"
    FAILED = "failed"
    ESCALATED = "escalated"


class ReportType:
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class AgentDeployment(Base):
    """Agent 部署记录"""
    __tablename__ = "agent_deployments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_name = Column(String(255), nullable=False)
    version = Column(String(64), default="1.0.0")
    template_yaml = Column(Text)
    parameters = Column(Text, nullable=True)  # JSON
    status = Column(String(32), default=AgentDeploymentStatus.PENDING)
    health_score = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deployed_at = Column(DateTime, nullable=True)
    rolled_back_at = Column(DateTime, nullable=True)
    created_by = Column(String(255), default="system")
    is_active = Column(Boolean, default=True)


class ScalingPolicy(Base):
    """扩缩容策略配置"""
    __tablename__ = "scaling_policies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(255), index=True)
    agent_name = Column(String(255))
    enabled = Column(Boolean, default=True)
    metric_type = Column(String(32), default=ScalingMetricType.CPU_USAGE)
    scale_out_threshold = Column(Float, default=70.0)
    scale_in_threshold = Column(Float, default=30.0)
    min_instances = Column(Integer, default=1)
    max_instances = Column(Integer, default=10)
    scale_out_cooldown = Column(Integer, default=60)
    scale_in_cooldown = Column(Integer, default=180)
    scale_out_step = Column(Integer, default=2)
    scale_in_step = Column(Integer, default=1)
    scheduled_scale_out = Column(Text, nullable=True)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ScalingEvent(Base):
    """扩缩容事件记录"""
    __tablename__ = "scaling_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(255), index=True)
    agent_name = Column(String(255))
    direction = Column(String(32), default=ScalingDirection.SCALE_OUT)
    previous_instances = Column(Integer)
    new_instances = Column(Integer)
    trigger_reason = Column(Text)
    metric_value = Column(Float)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class LogEntry(Base):
    """日志条目（结构化存储）"""
    __tablename__ = "log_entries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    level = Column(String(16), default=LogLevel.INFO, index=True)
    logger = Column(String(255))
    message = Column(Text)
    source_type = Column(String(32), default=LogSourceType.SYSTEM)
    source_id = Column(String(255), nullable=True)
    agent_id = Column(String(255), nullable=True, index=True)
    trace_id = Column(String(255), nullable=True)
    log_metadata = Column(Text, nullable=True)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow)


class LogCollectionConfig(Base):
    """日志采集配置"""
    __tablename__ = "log_collection_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(255), unique=True)
    log_level = Column(String(16), default=LogLevel.INFO)
    sources = Column(Text, default='["agent","skill","mcp","system"]')  # JSON
    rotation_size_mb = Column(Integer, default=500)
    rotation_interval_days = Column(Integer, default=1)
    retention_days = Column(Integer, default=30)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MaintenanceTask(Base):
    """定期维护任务定义"""
    __tablename__ = "maintenance_tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_type = Column(String(32), default=MaintenanceType.SESSION_CLEANUP)
    name = Column(String(255))
    description = Column(Text, nullable=True)
    cron_expression = Column(String(64))
    enabled = Column(Boolean, default=True)
    maintenance_window_start = Column(String(8), nullable=True)
    maintenance_window_end = Column(String(8), nullable=True)
    timeout_seconds = Column(Integer, default=3600)
    last_run_at = Column(DateTime, nullable=True)
    last_run_result = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MaintenanceExecution(Base):
    """维护任务执行记录"""
    __tablename__ = "maintenance_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(255), index=True)
    task_type = Column(String(32))
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(16), default="running")
    items_processed = Column(Integer, default=0)
    items_cleaned = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    duration_seconds = Column(Float, nullable=True)


class SelfHealRecord(Base):
    """异常自愈记录"""
    __tablename__ = "self_heal_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(255), index=True)
    agent_name = Column(String(255))
    anomaly_type = Column(String(255))
    anomaly_value = Column(Float)
    threshold_value = Column(Float)
    consecutive_count = Column(Integer, default=1)
    heal_level = Column(String(32), default=HealLevel.LEVEL_1_RESTART)
    status = Column(String(32), default=HealStatus.DETECTED)
    action_taken = Column(Text, nullable=True)
    health_score_before = Column(Float, nullable=True)
    health_score_after = Column(Float, nullable=True)
    verified = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)
    healed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)


class HealRule(Base):
    """自愈规则配置"""
    __tablename__ = "heal_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(255), index=True)
    anomaly_type = Column(String(255))
    consecutive_threshold = Column(Integer, default=3)
    error_rate_threshold = Column(Float, nullable=True)
    p99_latency_threshold_ms = Column(Float, nullable=True)
    health_drop_threshold = Column(Float, nullable=True)
    heal_level = Column(String(32), default=HealLevel.LEVEL_1_RESTART)
    auto_heal = Column(Boolean, default=True)
    enabled = Column(Boolean, default=True)
    cooldown_seconds = Column(Integer, default=300)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OpsReport(Base):
    """运维报告"""
    __tablename__ = "ops_reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    report_type = Column(String(16), default=ReportType.DAILY)
    title = Column(String(255))
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    availability_rate = Column(Float, nullable=True)
    total_requests = Column(Integer, nullable=True)
    error_count = Column(Integer, nullable=True)
    anomaly_count = Column(Integer, nullable=True)
    heal_count = Column(Integer, nullable=True)
    scaling_events = Column(Integer, nullable=True)
    maintenance_executions = Column(Integer, nullable=True)
    top_agents = Column(Text, nullable=True)  # JSON
    resource_trends = Column(Text, nullable=True)  # JSON
    suggestions = Column(Text, nullable=True)
    raw_data = Column(Text, nullable=True)  # JSON
    generated_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(255), default="system")
