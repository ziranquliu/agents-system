"""
智能体自动化运维模型
覆盖：自动部署、Auto Scaling、日志管理、定期维护、异常自愈、运维报告
"""
import uuid
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Column, JSON, String, Text, Float, Integer, Boolean, DateTime, Enum as SAEnum
import enum


# ==================== 4.22.1 自动部署 ====================

class AgentDeploymentStatus(str, enum.Enum):
    PENDING = "pending"
    DEPLOYING = "deploying"
    HEALTH_CHECKING = "health_checking"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class AgentDeployment(SQLModel, table=True):
    """Agent 部署记录"""
    __tablename__ = "agent_deployments"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    agent_name: str = Field(max_length=255)
    version: str = Field(max_length=64, default="1.0.0")
    template_yaml: str = Field(sa_type=Text)
    parameters: Optional[str] = Field(default=None, sa_type=JSON)  # 参数化变量 JSON
    status: AgentDeploymentStatus = Field(default=AgentDeploymentStatus.PENDING)
    health_score: Optional[float] = Field(default=None, sa_type=Float)
    error_message: Optional[str] = Field(default=None, sa_type=Text)
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)
    deployed_at: Optional[datetime] = Field(default=None, sa_type=DateTime)
    rolled_back_at: Optional[datetime] = Field(default=None, sa_type=DateTime)
    created_by: str = Field(max_length=255, default="system")
    is_active: bool = Field(default=True)


# ==================== 4.22.2 Auto Scaling ====================

class ScalingMetricType(str, enum.Enum):
    QPS = "qps"
    TOKEN_RATE = "token_rate"
    P95_LATENCY = "p95_latency"
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"


class ScalingDirection(str, enum.Enum):
    SCALE_OUT = "scale_out"
    SCALE_IN = "scale_in"


class ScalingPolicy(SQLModel, table=True):
    """扩缩容策略配置"""
    __tablename__ = "scaling_policies"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    agent_id: str = Field(max_length=255)
    agent_name: str = Field(max_length=255)
    enabled: bool = Field(default=True)
    # 扩缩指标
    metric_type: ScalingMetricType = Field(default=ScalingMetricType.CPU_USAGE)
    scale_out_threshold: float = Field(default=70.0, sa_type=Float)  # 扩容阈值
    scale_in_threshold: float = Field(default=30.0, sa_type=Float)  # 缩容阈值
    # 实例范围
    min_instances: int = Field(default=1)
    max_instances: int = Field(default=10)
    # 冷却期（秒）
    scale_out_cooldown: int = Field(default=60)
    scale_in_cooldown: int = Field(default=180)
    # 策略
    scale_out_step: int = Field(default=2)  # 快速扩容步长
    scale_in_step: int = Field(default=1)   # 平稳缩容步长
    # 计划性扩容
    scheduled_scale_out: Optional[str] = Field(default=None, sa_type=Text)  # JSON: [{cron, replicas}]
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)


class ScalingEvent(SQLModel, table=True):
    """扩缩容事件记录"""
    __tablename__ = "scaling_events"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    agent_id: str = Field(max_length=255)
    agent_name: str = Field(max_length=255)
    direction: ScalingDirection
    previous_instances: int
    new_instances: int
    trigger_reason: str = Field(sa_type=Text)
    metric_value: float = Field(sa_type=Float)
    success: bool = Field(default=True)
    error_message: Optional[str] = Field(default=None, sa_type=Text)
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)


# ==================== 4.22.3 日志管理 ====================

class LogSourceType(str, enum.Enum):
    AGENT = "agent"
    SKILL = "skill"
    MCP = "mcp"
    SYSTEM = "system"


class LogLevel(str, enum.Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    FATAL = "FATAL"


class LogEntry(SQLModel, table=True):
    """日志条目（结构化存储）"""
    __tablename__ = "log_entries"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)
    level: LogLevel = Field(default=LogLevel.INFO)
    logger: str = Field(max_length=255)
    message: str = Field(sa_type=Text)
    source_type: LogSourceType = Field(default=LogSourceType.SYSTEM)
    source_id: Optional[str] = Field(default=None, max_length=255)
    agent_id: Optional[str] = Field(default=None, max_length=255)
    trace_id: Optional[str] = Field(default=None, max_length=255)
    metadata: Optional[str] = Field(default=None, sa_type=JSON)  # 额外结构化信息
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)


class LogCollectionConfig(SQLModel, table=True):
    """日志采集配置"""
    __tablename__ = "log_collection_configs"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    agent_id: str = Field(max_length=255, unique=True)
    log_level: LogLevel = Field(default=LogLevel.INFO)
    sources: str = Field(sa_type=JSON, default='["agent","skill","mcp","system"]')  # 采集源列表
    rotation_size_mb: int = Field(default=500)
    rotation_interval_days: int = Field(default=1)
    retention_days: int = Field(default=30)
    enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)


# ==================== 4.22.4 定期维护 ====================

class MaintenanceType(str, enum.Enum):
    SESSION_CLEANUP = "session_cleanup"
    CACHE_CLEANUP = "cache_cleanup"
    TEMP_FILE_CLEANUP = "temp_file_cleanup"
    INDEX_REBUILD = "index_rebuild"
    STATISTICS_ANALYSIS = "statistics_analysis"


class MaintenanceTask(SQLModel, table=True):
    """定期维护任务定义"""
    __tablename__ = "maintenance_tasks"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    task_type: MaintenanceType
    name: str = Field(max_length=255)
    description: Optional[str] = Field(default=None, sa_type=Text)
    cron_expression: str = Field(max_length=64)  # 定时表达式
    enabled: bool = Field(default=True)
    maintenance_window_start: Optional[str] = Field(default=None, max_length=8)  # HH:MM
    maintenance_window_end: Optional[str] = Field(default=None, max_length=8)    # HH:MM
    timeout_seconds: int = Field(default=3600)
    last_run_at: Optional[datetime] = Field(default=None, sa_type=DateTime)
    last_run_result: Optional[str] = Field(default=None, sa_type=Text)
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)


class MaintenanceExecution(SQLModel, table=True):
    """维护任务执行记录"""
    __tablename__ = "maintenance_executions"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    task_id: str = Field(max_length=255)
    task_type: MaintenanceType
    started_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)
    completed_at: Optional[datetime] = Field(default=None, sa_type=DateTime)
    status: str = Field(default="running")  # running/success/failed
    items_processed: int = Field(default=0)
    items_cleaned: int = Field(default=0)
    error_message: Optional[str] = Field(default=None, sa_type=Text)
    duration_seconds: Optional[float] = Field(default=None, sa_type=Float)


# ==================== 4.22.5 异常自愈 ====================

class HealLevel(str, enum.Enum):
    LEVEL_1_RESTART = "restart"
    LEVEL_2_ROLLBACK = "rollback"
    LEVEL_3_DEGRADE = "degrade"


class HealStatus(str, enum.Enum):
    DETECTED = "detected"
    HEALING = "healing"
    VERIFYING = "verifying"
    SUCCESS = "success"
    FAILED = "failed"
    ESCALATED = "escalated"


class SelfHealRecord(SQLModel, table=True):
    """异常自愈记录"""
    __tablename__ = "self_heal_records"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    agent_id: str = Field(max_length=255)
    agent_name: str = Field(max_length=255)
    anomaly_type: str = Field(max_length=255)  # error_rate/latency/health_drop
    anomaly_value: float = Field(sa_type=Float)
    threshold_value: float = Field(sa_type=Float)
    consecutive_count: int = Field(default=1)
    heal_level: HealLevel = Field(default=HealLevel.LEVEL_1_RESTART)
    status: HealStatus = Field(default=HealStatus.DETECTED)
    action_taken: Optional[str] = Field(default=None, sa_type=Text)
    health_score_before: Optional[float] = Field(default=None, sa_type=Float)
    health_score_after: Optional[float] = Field(default=None, sa_type=Float)
    verified: bool = Field(default=False)
    error_message: Optional[str] = Field(default=None, sa_type=Text)
    detected_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)
    healed_at: Optional[datetime] = Field(default=None, sa_type=DateTime)
    duration_seconds: Optional[float] = Field(default=None, sa_type=Float)


class HealRule(SQLModel, table=True):
    """自愈规则配置"""
    __tablename__ = "heal_rules"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    agent_id: str = Field(max_length=255)
    anomaly_type: str = Field(max_length=255)
    consecutive_threshold: int = Field(default=3)  # 连续 N 次触发
    error_rate_threshold: Optional[float] = Field(default=None, sa_type=Float)
    p99_latency_threshold_ms: Optional[float] = Field(default=None, sa_type=Float)
    health_drop_threshold: Optional[float] = Field(default=None, sa_type=Float)
    heal_level: HealLevel = Field(default=HealLevel.LEVEL_1_RESTART)
    auto_heal: bool = Field(default=True)
    enabled: bool = Field(default=True)
    cooldown_seconds: int = Field(default=300)  # 自愈冷却
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)


# ==================== 4.22.6 运维报告 ====================

class ReportType(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class OpsReport(SQLModel, table=True):
    """运维报告"""
    __tablename__ = "ops_reports"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    report_type: ReportType
    title: str = Field(max_length=255)
    period_start: datetime
    period_end: datetime
    # 报告数据（JSON）
    availability_rate: Optional[float] = Field(default=None, sa_type=Float)
    total_requests: Optional[int] = Field(default=None)
    error_count: Optional[int] = Field(default=None)
    anomaly_count: Optional[int] = Field(default=None)
    heal_count: Optional[int] = Field(default=None)
    scaling_events: Optional[int] = Field(default=None)
    maintenance_executions: Optional[int] = Field(default=None)
    top_agents: Optional[str] = Field(default=None, sa_type=JSON)  # Top N 异常 Agent
    resource_trends: Optional[str] = Field(default=None, sa_type=JSON)  # 资源趋势
    suggestions: Optional[str] = Field(default=None, sa_type=Text)
    raw_data: Optional[str] = Field(default=None, sa_type=JSON)  # 完整报告数据
    generated_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)
    created_by: str = Field(max_length=255, default="system")
