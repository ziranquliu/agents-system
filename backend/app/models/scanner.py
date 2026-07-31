"""
本地组件扫描器模型 - 扫描会话及其结果
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class ComponentScan(Base):
    """组件扫描会话"""
    __tablename__ = "component_scans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String(20), default="running")  # running / completed / failed
    summary = Column(Text, nullable=True)  # JSON: total_checked, passed, warning, error
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    triggered_by = Column(String(36), nullable=True)  # user_id or "system"
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("ComponentScanItem", back_populates="scan", cascade="all, delete-orphan")


class ComponentScanItem(Base):
    """单个组件的扫描结果"""
    __tablename__ = "component_scan_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scan_id = Column(String(36), ForeignKey("component_scans.id", ondelete="CASCADE"), nullable=False, index=True)
    component_type = Column(String(20), nullable=False, index=True)  # agent / skill / mcp
    component_id = Column(String(36), nullable=False)
    component_name = Column(String(200), nullable=True)
    status = Column(String(20), default="unknown")  # healthy / warning / error / unknown
    error_message = Column(Text, nullable=True)
    details = Column(Text, nullable=True)  # JSON: extra info
    scanned_at = Column(DateTime, default=datetime.utcnow)

    scan = relationship("ComponentScan", back_populates="items")


class ScannerAlert(Base):
    """扫描变化告警 — 上次扫描与本次扫描状态变化时生成"""
    __tablename__ = "scanner_alerts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    component_type = Column(String(20), index=True)  # agent / skill / mcp
    component_id = Column(String(36), index=True)
    component_name = Column(String(200), nullable=True)
    previous_status = Column(String(20), nullable=True)
    current_status = Column(String(20))
    severity = Column(String(16), default="info")  # info / warning / critical
    message = Column(Text, nullable=True)
    scan_id = Column(String(36), nullable=True)
    status = Column(String(16), default="open")  # open / acknowledged / resolved
    created_at = Column(DateTime, default=datetime.utcnow)
