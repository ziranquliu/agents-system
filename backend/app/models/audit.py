"""
操作审计（增强）模型
覆盖：审计日志（哈希链防篡改/追加写入/分区）、归档（冷热分离）、
异常行为检测规则与告警、审计配置（保留期/SIEM/脱敏）
"""
import hashlib
import json
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, Date

from app.db.session import Base


class AuditCategory:
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    SECURITY = "security"


class AuditResult:
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"


class AnomalyType:
    OFF_HOURS = "off_hours"
    HIGH_FREQ_FAILURE = "high_freq_failure"
    PERMISSION_ESCALATION = "permission_escalation"
    BATCH_DELETE = "batch_delete"
    SENSITIVE_OP = "sensitive_op"
    ABNORMAL_IP = "abnormal_ip"


class AlertSeverity:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditLog(Base):
    """审计日志（追加写入，仅 INSERT；哈希链防篡改）"""
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    operator_id = Column(String(128), index=True)
    operator_name = Column(String(128), nullable=True)
    operator_ip = Column(String(64), nullable=True)
    device_info = Column(String(256), nullable=True)
    category = Column(String(32), index=True)  # user/agent/system/security
    action_type = Column(String(64), index=True)  # 资源.操作 命名规范
    target_id = Column(String(256), nullable=True, index=True)
    details = Column(Text, nullable=True)  # JSON: {"before": {...}, "after": {...}}
    result = Column(String(16), index=True)  # success/failure/denied
    failure_reason = Column(String(256), nullable=True)
    trace_id = Column(String(64), nullable=True)
    partition_date = Column(Date, default=lambda: datetime.utcnow().date(), index=True)
    prev_hash = Column(String(64), nullable=True)  # 前一条记录的 SHA-256
    curr_hash = Column(String(64), nullable=True)  # 本条记录的 SHA-256
    verified = Column(Boolean, default=False)  # 写后读校验标记
    created_at = Column(DateTime, default=datetime.utcnow)

    def compute_hash(self) -> str:
        """
        计算本条记录的 SHA-256 哈希（防篡改哈希链）

        哈希输入 = timestamp + operator_id + action_type + target_id + details_json + prev_hash
        """
        ts_str = self.timestamp.isoformat() if self.timestamp else ""
        prev = self.prev_hash or ""
        details_str = self.details or ""
        raw = f"{ts_str}|{self.operator_id or ''}|{self.action_type or ''}|{self.target_id or ''}|{details_str}|{prev}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def verify_chain(self, prev_record_hash: str) -> bool:
        """验证本条记录是否与前一条记录的哈希链一致"""
        if self.prev_hash != prev_record_hash:
            return False
        return self.curr_hash == self.compute_hash()


class AuditArchive(Base):
    """审计归档记录（冷热分离 / 归档元信息）"""
    __tablename__ = "audit_archives"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    archive_key = Column(String(255), index=True)  # 归档文件标识（含日期范围）
    start_date = Column(Date)
    end_date = Column(Date)
    record_count = Column(Integer, default=0)
    archive_path = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditRule(Base):
    """异常行为检测规则（内置规则引擎）"""
    __tablename__ = "audit_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_name = Column(String(128), nullable=False)
    rule_type = Column(String(32), index=True)  # off_hours/high_freq_failure/...
    params = Column(Text, nullable=True)  # JSON 规则参数
    enabled = Column(Boolean, default=True)
    severity = Column(String(16), default="medium")  # low/medium/high/critical
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditAlert(Base):
    """异常行为告警"""
    __tablename__ = "audit_alerts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    alert_type = Column(String(32), index=True)
    severity = Column(String(16), default="medium")
    operator_id = Column(String(128), nullable=True, index=True)
    description = Column(Text, nullable=True)
    evidence = Column(Text, nullable=True)  # JSON 证据
    status = Column(String(16), default="open")  # open/acknowledged/resolved
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class AuditConfig(Base):
    """审计系统配置（合规保留期 / 轮转 / SIEM / 脱敏）"""
    __tablename__ = "audit_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    retention_days = Column(Integer, default=180)  # 合规保留期 ≥ 180 天
    archive_after_days = Column(Integer, default=90)  # 超过 N 天自动归档（冷热分离）
    rotation_size_mb = Column(Integer, default=10240)  # 按大小轮转阈值（每 10GB）
    siem_enabled = Column(Boolean, default=False)
    siem_host = Column(String(255), nullable=True)
    siem_port = Column(Integer, default=514)
    siem_protocol = Column(String(16), default="syslog")  # syslog/udp/tcp
    mask_sensitive = Column(Boolean, default=True)  # 隐私脱敏（IP/用户ID匿名化）
    updated_at = Column(DateTime, default=datetime.utcnow)
