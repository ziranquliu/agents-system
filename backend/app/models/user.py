"""
用户模型 (占位)
"""
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="user")  # admin | developer | user | guest
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
