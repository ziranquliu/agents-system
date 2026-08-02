"""
Agent 模型 - 智能体定义和生命周期管理
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, Float
from sqlalchemy.sql import func

from app.db.session import Base


class Agent(Base):
    """Agent 表 - 核心实体"""
    __tablename__ = "agents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text)
    status = Column(String(20), default="draft", index=True)  # draft | running | stopped | error | archived
    avatar = Column(String(500))

    # 模型配置
    model_provider = Column(String(50))  # openai | ollama | openrouter | etc.
    model_name = Column(String(100))
    model_config_template_id = Column(String(36))  # 引用模型配置模板
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=4096)

    # 系统提示词和上下文
    system_prompt = Column(Text)
    welcome_message = Column(Text)
    context_window = Column(Integer, default=8192)

    # Skill 和 MCP 配置 (JSON)
    enabled_skills = Column(Text)  # JSON: ["skill_id_1", "skill_id_2"]
    enabled_mcp_servers = Column(Text)  # JSON: ["mcp_id_1"]

    # 通知通道
    webhook_url = Column(String(500))  # Agent 级 Webhook，自愈通知用（优先级高于全局配置）

    # 归属
    workspace_id = Column(String(36), nullable=False, index=True)
    created_by = Column(String(36), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 注: ORM 关系在后续开发中按需添加


class ModelConfigTemplate(Base):
    """模型配置模板 - 支持一键复用"""
    __tablename__ = "model_config_templates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    description = Column(Text)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    config = Column(Text)  # JSON: temperature, max_tokens, top_p, etc.
    is_default = Column(Boolean, default=False)
    workspace_id = Column(String(36), index=True)
    created_by = Column(String(36))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
