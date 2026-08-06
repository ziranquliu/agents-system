"""
事件日志模型 — 持久化 Event Bus 事件

覆盖：事件发布记录、死信队列（DLQ）、事件重放支持
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, Integer, DateTime, JSON, Boolean

from app.db.session import Base


class EventLog(Base):
    """事件日志（追加写入，不可修改）"""
    __tablename__ = "event_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(128), index=True, nullable=False)
    payload = Column(JSON, nullable=True)
    source = Column(String(64), default="system", index=True)
    priority = Column(String(16), default="normal")  # low/normal/high/critical
    timestamp = Column(DateTime, default=lambda: datetime.utcnow(), index=True)
    correlation_id = Column(String(36), index=True)
    delivered = Column(Boolean, default=False)
    delivery_attempts = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DeadLetterQueue(Base):
    """死信队列 — 投递失败的事件"""
    __tablename__ = "dead_letter_queue"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_event_id = Column(String(36), index=True)
    event_type = Column(String(128), index=True)
    payload = Column(JSON, nullable=True)
    source = Column(String(64), default="system")
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    status = Column(String(16), default="pending")  # pending/retrying/resolved/discarded
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    resolved_at = Column(DateTime, nullable=True)
