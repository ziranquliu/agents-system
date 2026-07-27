from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func
from app.db.session import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True)
    title = Column(String(200))
    agent_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=False)
    workspace_id = Column(String(36), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True)
    conversation_id = Column(String(36), nullable=False)
    role = Column(String(20), nullable=False)  # user | assistant | system
    content = Column(Text, nullable=False)
    token_count = Column(String(20))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
