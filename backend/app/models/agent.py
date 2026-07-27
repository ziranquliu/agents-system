"""
Agent 模型 (占位)
"""
from sqlalchemy import Column, String, Text, DateTime, Enum
from sqlalchemy.sql import func
import enum
from app.db.session import Base


class AgentStatus(str, enum.Enum):
    DRAFT = "draft"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    ARCHIVED = "archived"


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    status = Column(Enum(AgentStatus), default=AgentStatus.DRAFT)
    model_config = Column(Text)  # JSON model config template reference
    system_prompt = Column(Text)
    workspace_id = Column(String(36), nullable=False)
    created_by = Column(String(36), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
