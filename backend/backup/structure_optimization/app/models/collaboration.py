"""
多智能体协作模型 - 协作任务/消息/会话
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


class Collaboration(Base):
    """多智能体协作会话"""
    __tablename__ = "collaborations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    mode = Column(String(20), default="sequential")  # sequential / parallel / broadcast / supervisor / debate
    status = Column(String(20), default="draft")  # draft / running / completed / failed
    context = Column(Text, nullable=True)  # JSON: shared context/input
    result = Column(Text, nullable=True)  # JSON: final result
    created_by = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tasks = relationship("CollaborationTask", back_populates="collaboration", cascade="all, delete-orphan",
                         order_by="CollaborationTask.order")


class CollaborationTask(Base):
    """协作中的单个任务"""
    __tablename__ = "collaboration_tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    collaboration_id = Column(String(36), ForeignKey("collaborations.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String(36), nullable=False)
    agent_name = Column(String(200), nullable=True)
    order = Column(Integer, default=0)
    role = Column(String(50), nullable=True)  # supervisor / executor / reviewer / debater
    input_text = Column(Text, nullable=True)
    output_text = Column(Text, nullable=True)
    status = Column(String(20), default="pending")  # pending / running / completed / failed
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    collaboration = relationship("Collaboration", back_populates="tasks")
