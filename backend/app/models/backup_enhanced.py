"""
各智能体备份与恢复(增强)模型
覆盖：增量备份、事件触发备份、部分恢复、AES-256 加密、SHA-256 校验、密钥轮换、恢复演练
"""
import uuid
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Text, JSON, DateTime, Integer, Float, Boolean, String
import enum


class BackupType(str, enum.Enum):
    FULL = "full"                # 全量备份
    INCREMENTAL = "incremental"  # 增量备份
    EVENT = "event"              # 事件触发备份


class BackupStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    VERIFYING = "verifying"


class BackupScope(str, enum.Enum):
    ALL = "all"                  # 全量（配置+记忆+会话）
    CONFIG = "config"            # 仅配置
    MEMORY = "memory"            # 仅记忆
    CONVERSATIONS = "conversations"  # 仅会话


class EncryptionAlgo(str, enum.Enum):
    NONE = "none"
    AES_256_GCM = "aes_256_gcm"


class RestoreType(str, enum.Enum):
    FULL = "full"                # 完整恢复
    CONFIG = "config"            # 仅配置
    MEMORY = "memory"            # 仅记忆
    CONVERSATIONS = "conversations"  # 仅会话


class RestoreStatus(str, enum.Enum):
    PENDING = "pending"
    PRECHECK = "precheck"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class DrillStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class BackupRecord(SQLModel, table=True):
    """备份记录"""
    __tablename__ = "backup_records"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    agent_id: str = Field(max_length=255)
    agent_name: str = Field(max_length=255)
    backup_type: BackupType = Field(default=BackupType.FULL)
    scope: BackupScope = Field(default=BackupScope.ALL)
    status: BackupStatus = Field(default=BackupStatus.PENDING)
    # 增量备份父备份
    base_backup_id: Optional[str] = Field(default=None, max_length=255)
    # 文件与校验
    file_path: Optional[str] = Field(default=None, max_length=1024)
    size_bytes: Optional[int] = Field(default=None)
    checksum_sha256: Optional[str] = Field(default=None, max_length=128)
    # 加密
    encryption_algo: EncryptionAlgo = Field(default=EncryptionAlgo.NONE)
    key_id: Optional[str] = Field(default=None, max_length=64)
    # 数据统计
    data_stats: Optional[str] = Field(default=None, sa_type=JSON)  # {table: count}
    # 保留策略
    retained_until: Optional[datetime] = Field(default=None, sa_type=DateTime)
    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)
    completed_at: Optional[datetime] = Field(default=None, sa_type=DateTime)
    duration_seconds: Optional[float] = Field(default=None, sa_type=Float)
    error_message: Optional[str] = Field(default=None, sa_type=Text)
    created_by: str = Field(max_length=255, default="system")
    is_deleted: bool = Field(default=False)


class BackupPolicy(SQLModel, table=True):
    """备份策略（按 Agent）"""
    __tablename__ = "backup_policies"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    agent_id: str = Field(max_length=255, unique=True)
    agent_name: str = Field(max_length=255)
    enabled: bool = Field(default=True)
    # 全量备份 cron（默认每日 03:00）
    full_backup_cron: str = Field(default="0 3 * * *", max_length=64)
    # 增量备份间隔（小时），0 表示不启用
    incremental_interval_hours: int = Field(default=6)
    # 事件触发
    event_trigger_enabled: bool = Field(default=True)
    event_types: Optional[str] = Field(default=None, sa_type=JSON)  # ["config_change","skill_bind","mcp_bind","memory_write"]
    # 加密
    encryption_enabled: bool = Field(default=True)
    # 保留策略
    retention_full_count: int = Field(default=7)     # 保留最近 N 个全量
    retention_incremental_count: int = Field(default=48)  # 保留最近 N 个增量
    retention_days: int = Field(default=90)          # 总保留天数
    # 恢复演练
    drill_enabled: bool = Field(default=True)
    drill_cron: str = Field(default="0 4 * * 0", max_length=64)  # 每周日 04:00
    # 范围
    default_scope: BackupScope = Field(default=BackupScope.ALL)
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)
    updated_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)


class BackupEventLog(SQLModel, table=True):
    """事件触发备份日志"""
    __tablename__ = "backup_event_logs"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    agent_id: str = Field(max_length=255)
    event_type: str = Field(max_length=128)
    event_meta: Optional[str] = Field(default=None, sa_type=JSON)
    backup_id: Optional[str] = Field(default=None, max_length=255)
    triggered_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)
    status: str = Field(default="processed")  # processed/skipped/failed


class RestoreOperation(SQLModel, table=True):
    """恢复操作记录"""
    __tablename__ = "restore_operations"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    backup_id: str = Field(max_length=255)
    restore_type: RestoreType = Field(default=RestoreType.FULL)
    # 恢复目标（默认原 Agent，支持跨 Agent 恢复）
    target_agent_id: str = Field(max_length=255)
    target_agent_name: str = Field(max_length=255)
    source_agent_name: Optional[str] = Field(default=None, max_length=255)
    status: RestoreStatus = Field(default=RestoreStatus.PENDING)
    precheck_result: Optional[str] = Field(default=None, sa_type=JSON)
    # 恢复统计
    restored_stats: Optional[str] = Field(default=None, sa_type=JSON)
    health_score_after: Optional[float] = Field(default=None, sa_type=Float)
    error_message: Optional[str] = Field(default=None, sa_type=Text)
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)
    completed_at: Optional[datetime] = Field(default=None, sa_type=DateTime)
    duration_seconds: Optional[float] = Field(default=None, sa_type=Float)
    created_by: str = Field(max_length=255, default="system")


class RestoreDrill(SQLModel, table=True):
    """恢复演练记录"""
    __tablename__ = "restore_drills"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    agent_id: str = Field(max_length=255)
    agent_name: str = Field(max_length=255)
    backup_id: str = Field(max_length=255)
    status: DrillStatus = Field(default=DrillStatus.SCHEDULED)
    scheduled_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)
    started_at: Optional[datetime] = Field(default=None, sa_type=DateTime)
    completed_at: Optional[datetime] = Field(default=None, sa_type=DateTime)
    # 演练报告
    restore_ok: Optional[bool] = Field(default=None)
    duration_seconds: Optional[float] = Field(default=None, sa_type=Float)
    report_data: Optional[str] = Field(default=None, sa_type=JSON)
    error_message: Optional[str] = Field(default=None, sa_type=Text)
    created_by: str = Field(max_length=255, default="system")


class EncryptionKey(SQLModel, table=True):
    """加密密钥元数据（密钥本体仅存于密钥库文件）"""
    __tablename__ = "encryption_keys"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    key_id: str = Field(max_length=64, unique=True)
    algorithm: str = Field(default="aes_256_gcm")
    status: str = Field(default="active")  # active/retired
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_type=DateTime)
    retired_at: Optional[datetime] = Field(default=None, sa_type=DateTime)
    note: Optional[str] = Field(default=None, max_length=512)
