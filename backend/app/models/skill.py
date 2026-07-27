"""
技能与 MCP 模型 (占位)
"""
from sqlalchemy import Column, String, Text, DateTime, Boolean
from sqlalchemy.sql import func
from app.db.session import Base


class Skill(Base):
    __tablename__ = "skills"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    version = Column(String(20), nullable=False)
    description = Column(Text)
    type = Column(String(50))  # tool | skill | plugin
    source = Column(String(20), default="local")  # local | marketplace
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class MCPServer(Base):
    __tablename__ = "mcp_servers"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    protocol = Column(String(20), default="sse")  # sse | stdio
    status = Column(String(20), default="active")  # active | inactive | error
    config = Column(Text)  # JSON config
    created_at = Column(DateTime(timezone=True), server_default=func.now())
