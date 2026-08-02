"""
各智能体备份与恢复(增强)模型
覆盖：增量备份、事件触发备份、部分恢复、AES-256 加密、SHA-256 校验、密钥轮换、恢复演练
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime

from app.db.session import Base


class BackupType:
    FULL = "full"
    INCREMENTAL = "incremental"
    EVENT = "event"


class BackupStatus:
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    VERIFYING = "verifying"


class BackupScope:
    ALL = "all"
    CONFIG = "config"
    MEMORY = "memory"
    CONVERSATIONS = "conversations"


class EncryptionAlgo:
    NONE = "none"
    AES_256_GCM = "aes_256_gcm"


class RestoreType:
    FULL = "full"
    CONFIG = "config"
    MEMORY = "memory"
    CONVERSATIONS = "conversations"


class RestoreStatus:
    PENDING = "pending"
    PRECHECK = "precheck"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class DrillStatus:
    SCHEDULED = "scheduled"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class BackupRecord(Base):
    """备份记录"""
    __tablename__ = "backup_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(255), index=True)
    agent_name = Column(String(255))
    backup_type = Column(String(16), default=BackupType.FULL)
    scope = Column(String(32), default=BackupScope.ALL)
    status = Column(String(16), default=BackupStatus.PENDING)
    base_backup_id = Column(String(255), nullable=True)
    file_path = Column(String(1024), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    checksum_sha256 = Column(String(128), nullable=True)
    encryption_algo = Column(String(32), default=EncryptionAlgo.NONE)
    key_id = Column(String(64), nullable=True)
    data_stats = Column(Text, nullable=True)  # JSON
    retained_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    created_by = Column(String(255), default="system")
    is_deleted = Column(Boolean, default=False)


class BackupPolicy(Base):
    """备份策略（按 Agent）"""
    __tablename__ = "backup_policies"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(255), unique=True, index=True)
    agent_name = Column(String(255))
    enabled = Column(Boolean, default=True)
    full_backup_cron = Column(String(64), default="0 3 * * *")
    incremental_interval_hours = Column(Integer, default=6)
    event_trigger_enabled = Column(Boolean, default=True)
    event_types = Column(Text, nullable=True)  # JSON
    encryption_enabled = Column(Boolean, default=True)
    retention_full_count = Column(Integer, default=7)
    retention_incremental_count = Column(Integer, default=48)
    retention_days = Column(Integer, default=90)
    drill_enabled = Column(Boolean, default=True)
    drill_cron = Column(String(64), default="0 4 * * 0")
    default_scope = Column(String(32), default=BackupScope.ALL)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BackupEventLog(Base):
    """事件触发备份日志"""
    __tablename__ = "backup_event_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(255), index=True)
    event_type = Column(String(128))
    event_meta = Column(Text, nullable=True)  # JSON
    backup_id = Column(String(255), nullable=True)
    triggered_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(16), default="processed")


class RestoreOperation(Base):
    """恢复操作记录"""
    __tablename__ = "restore_operations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    backup_id = Column(String(255), index=True)
    restore_type = Column(String(32), default=RestoreType.FULL)
    target_agent_id = Column(String(255), index=True)
    target_agent_name = Column(String(255))
    source_agent_name = Column(String(255), nullable=True)
    status = Column(String(32), default=RestoreStatus.PENDING)
    precheck_result = Column(Text, nullable=True)  # JSON
    restored_stats = Column(Text, nullable=True)  # JSON
    health_score_after = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    created_by = Column(String(255), default="system")


class RestoreDrill(Base):
    """恢复演练记录"""
    __tablename__ = "restore_drills"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(255), index=True)
    agent_name = Column(String(255))
    backup_id = Column(String(255))
    status = Column(String(16), default=DrillStatus.SCHEDULED)
    scheduled_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    restore_ok = Column(Boolean, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    report_data = Column(Text, nullable=True)  # JSON
    error_message = Column(Text, nullable=True)
    created_by = Column(String(255), default="system")


class EncryptionKey(Base):
    """加密密钥元数据（密钥本体仅存于密钥库文件）"""
    __tablename__ = "encryption_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key_id = Column(String(64), unique=True)
    algorithm = Column(String(32), default="aes_256_gcm")
    status = Column(String(16), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    retired_at = Column(DateTime, nullable=True)
    note = Column(String(512), nullable=True)
