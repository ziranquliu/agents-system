"""
审计增强模型

- AuditLogPartitioned: 按月分区的审计日志表（与 audit_logs 分表）
"""
import datetime
import uuid
from sqlalchemy import Column, String, DateTime, Text, Date, Index
from app.db.session import Base


class AuditLogPartitioned(Base):
    """按月分区的审计日志表"""
    __tablename__ = "audit_logs_partitioned"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    partition_date = Column(Date, nullable=False)
    operator_id = Column(String(64), nullable=False)
    operator_ip = Column(String(64), server_default="")
    action_type = Column(String(64), nullable=False)
    target_id = Column(String(128), server_default="")
    target_type = Column(String(64), server_default="")
    details = Column(Text, server_default="")
    result = Column(String(16), server_default="success")
    device_info = Column(Text, server_default="")
    trace_id = Column(String(64), server_default="")
    geo_ip = Column(String(64), server_default="")
    prev_hash = Column(String(64), server_default="")
    curr_hash = Column(String(64), server_default="")
    workspace_id = Column(String(36), server_default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (
        Index("idx_audit_partition_date", "partition_date"),
        Index("idx_audit_operator", "operator_id"),
        Index("idx_audit_action", "action_type"),
        Index("idx_audit_target", "target_id"),
        Index("idx_audit_trace", "trace_id"),
    )
