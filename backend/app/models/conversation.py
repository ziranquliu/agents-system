"""
对话与消息模型
"""
import uuid

from sqlalchemy import Column, String, Text, DateTime, Integer
from sqlalchemy.sql import func

from app.db.session import Base


class Conversation(Base):
    """对话会话表"""
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(200))
    agent_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    workspace_id = Column(String(36), nullable=False, index=True)
    status = Column(String(20), default="active")  # active | archived | deleted
    message_count = Column(Integer, default=0)
    token_count = Column(Integer, default=0)

    # 上下文压缩
    compressed = Column(Integer, default=0)  # 压缩轮数
    summary = Column(Text)  # 对话摘要

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 注: ORM 关系在后续开发中按需添加


class Message(Base):
    """消息表"""
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), nullable=False, index=True)  # user | assistant | system | tool
    content = Column(Text, nullable=False)
    content_type = Column(String(20), default="text")  # text | code | image | tool_call

    # Token 统计
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)

    # 元数据
    model_used = Column(String(100))  # 生成该消息使用的模型
    tool_calls = Column(Text)  # JSON: 工具调用详情
    metadata_json = Column(Text)  # JSON: 扩展元数据

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    # 注: ORM 关系在后续开发中按需添加
