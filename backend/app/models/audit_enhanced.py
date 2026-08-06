"""
审计增强模型 — 分区表 + 冷热分离 + device_info + trace_id

功能:
- PostgreSQL PARTITION BY RANGE (按月分区)
- 冷热分离 (hot: 90天, cold: 1年)
- 审计记录增强字段 (device_info, trace_id, geo_ip)
"""

import hashlib
import json
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime, Date,
    Index, CheckConstraint,
)
from app.db.session import Base


class AuditLogPartitioned(Base):
    """
    审计日志（分区版）

    生产部署时应使用 PostgreSQL 分区表:
    CREATE TABLE audit_logs_partitioned (...) PARTITION BY RANGE (partition_date);

    CREATE TABLE audit_logs_2025_01 PARTITION OF audit_logs_partitioned
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
    """
    __tablename__ = "audit_logs_partitioned"
    __table_args__ = (
        Index("idx_audit_partition_date", "partition_date"),
        Index("idx_audit_operator", "operator_id"),
        Index("idx_audit_action", "action_type"),
        Index("idx_audit_target", "target_id"),
        Index("idx_audit_trace", "trace_id"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=lambda: datetime.utcnow(), nullable=False)
    partition_date = Column(Date, nullable=False, index=True)
    operator_id = Column(String(64), nullable=False, index=True)
    operator_ip = Column(String(64), default="")
    action_type = Column(String(64), nullable=False, index=True)
    target_id = Column(String(128), default="", index=True)
    target_type = Column(String(64), default="")
    details = Column(Text, default="")
    result = Column(String(16), default="success")
    # 增强字段
    device_info = Column(Text, default="")     # 浏览器/OS 信息
    trace_id = Column(String(64), default="", index=True)  # OpenTelemetry trace_id
    geo_ip = Column(String(64), default="")    # 地理位置
    prev_hash = Column(String(64), default="") # 哈希链
    curr_hash = Column(String(64), default="") # 哈希链
    workspace_id = Column(String(36), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    def compute_hash(self) -> str:
        ts_str = self.timestamp.isoformat() if self.timestamp else ""
        raw = f"{ts_str}|{self.operator_id or ''}|{self.action_type or ''}|{self.target_id or ''}|{self.details or ''}|{self.prev_hash or ''}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class AuditArchive(Base):
    """
    审计归档（冷存储）

    超过 90 天的审计记录迁移到此表
    """
    __tablename__ = "audit_archives"

    id = Column(String(36), primary_key=True)
    timestamp = Column(DateTime, nullable=False)
    partition_date = Column(Date, nullable=False, index=True)
    operator_id = Column(String(64), nullable=False)
    operator_ip = Column(String(64), default="")
    action_type = Column(String(64), nullable=False)
    target_id = Column(String(128), default="")
    target_type = Column(String(64), default="")
    details = Column(Text, default="")
    result = Column(String(16), default="success")
    device_info = Column(Text, default="")
    trace_id = Column(String(64), default="")
    geo_ip = Column(String(64), default="")
    prev_hash = Column(String(64), default="")
    curr_hash = Column(String(64), default="")
    workspace_id = Column(String(36), default="")
    archived_at = Column(DateTime, default=datetime.utcnow)
