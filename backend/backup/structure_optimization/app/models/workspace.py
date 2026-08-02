"""
工作空间模型 - 多租户资源隔离
"""
import uuid

from sqlalchemy import Column, String, Text, DateTime, Boolean, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class Workspace(Base):
    """工作空间表"""
    __tablename__ = "workspaces"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    owner_id = Column(String(36), nullable=False, index=True)
    member_count = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class WorkspaceMember(Base):
    """工作空间成员表"""
    __tablename__ = "workspace_members"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), default="member")  # owner | admin | member
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
