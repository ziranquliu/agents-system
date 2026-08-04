"""
用户与角色模型
"""
import uuid

from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.sql import func

from app.db.session import Base


class User(Base):
    """用户表 - 支持多角色"""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    display_name = Column(String(100))
    role = Column(String(20), default="user")  # admin | developer | user | guest
    is_active = Column(Boolean, default=True)
    avatar_url = Column(String(500))
    last_login_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # 注: 关联关系定义在子模型中 (Agent.created_by, Conversation.user_id)


class Role(Base):
    """角色表 - RBAC"""
    __tablename__ = "roles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(500))
    permissions = Column(Text)  # JSON: 权限列表
    is_system = Column(Boolean, default=False)  # 系统内置角色不可删除
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OperationLog(Base):
    """操作审计日志"""
    __tablename__ = "operation_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False, index=True)
    action = Column(String(100), nullable=False)  # create | update | delete | login | etc.
    resource_type = Column(String(50), nullable=False)  # agent | skill | conversation | etc.
    resource_id = Column(String(36))
    detail = Column(Text)  # JSON: 操作详情
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
