"""
任务管理模型
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text

from app.db.session import Base


class Task(Base):
    """任务"""
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), default="todo")  # todo / in_progress / done / cancelled
    priority = Column(String(10), default="medium")  # low / medium / high / urgent
    assigned_to = Column(String(36), nullable=True)
    created_by = Column(String(36), nullable=False)
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
