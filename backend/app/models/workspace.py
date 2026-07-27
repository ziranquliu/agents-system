"""
工作空间模型 (占位)
"""
from sqlalchemy import Column, String, DateTime
from sqlalchemy.sql import func
from app.db.session import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    owner_id = Column(String(36), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"

    id = Column(String(36), primary_key=True)
    workspace_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=False)
    role = Column(String(20), default="member")  # owner | admin | member
    created_at = Column(DateTime(timezone=True), server_default=func.now())
