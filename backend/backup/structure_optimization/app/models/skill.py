"""
技能 (Skill) 与 MCP Server 模型
"""
import uuid

from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer
from sqlalchemy.sql import func

from app.db.session import Base


class Skill(Base):
    """技能表 - 独立一等公民"""
    __tablename__ = "skills"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, index=True)
    version = Column(String(20), nullable=False)
    description = Column(Text)
    type = Column(String(50))  # tool | skill | plugin
    category = Column(String(50))  # 分类: analysis | search | code | etc.

    # 来源
    source = Column(String(20), default="local")  # local | marketplace
    source_url = Column(String(500))  # 市场来源链接
    icon = Column(String(500))

    # 配置
    entry_point = Column(String(200))  # 入口文件或函数
    parameters = Column(Text)  # JSON: 参数定义
    dependencies = Column(Text)  # JSON: 依赖项 ["python:requests>=2.0", "node:axios"]

    # 统计
    installed_count = Column(Integer, default=0)
    rating = Column(Integer, default=0)  # 评分 1-5

    # 状态
    enabled = Column(Boolean, default=True)
    is_system = Column(Boolean, default=False)  # 系统内置

    workspace_id = Column(String(36), index=True)
    created_by = Column(String(36))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SkillBinding(Base):
    """Agent-Skill 绑定表 - 多对多关系"""
    __tablename__ = "skill_bindings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), nullable=False, index=True)
    skill_id = Column(String(36), nullable=False, index=True)
    config = Column(Text)  # JSON: 技能特定配置
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MCPServer(Base):
    """MCP Server 注册表"""
    __tablename__ = "mcp_servers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    protocol = Column(String(20), default="sse")  # sse | stdio | websocket
    status = Column(String(20), default="active")  # active | inactive | error
    version = Column(String(20))
    description = Column(Text)

    # 认证
    auth_type = Column(String(20))  # none | api_key | bearer | basic
    auth_config = Column(Text)  # JSON: 认证配置

    # 健康检查
    health_check_url = Column(String(500))
    last_health_check = Column(DateTime(timezone=True))
    health_status = Column(String(20), default="unknown")  # healthy | unhealthy | unknown

    config = Column(Text)  # JSON: 完整配置
    workspace_id = Column(String(36), index=True)
    created_by = Column(String(36))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
