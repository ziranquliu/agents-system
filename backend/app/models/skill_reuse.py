"""
Skill 跨 Agent 复用 - 直接引用/复制/模板三种模式
"""
import uuid

from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.sql import func

from app.db.session import Base


class SkillReuseRelation(Base):
    """Skill 复用关系表"""
    __tablename__ = "skill_reuse_relations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 源 Skill（原始定义）
    source_skill_id = Column(String(36), nullable=False, index=True)
    source_skill_name = Column(String(100))
    source_agent_id = Column(String(36))  # 源 Agent（直接引用模式下）

    # 目标 Skill（复用后的副本或引用）
    target_skill_id = Column(String(36), nullable=False, index=True)
    target_skill_name = Column(String(100))
    target_agent_id = Column(String(36), nullable=False, index=True)

    # 复用模式
    reuse_mode = Column(String(20), nullable=False)  # direct_ref | copy | template

    # 同步模式（direct_ref/template 模式有效）
    sync_mode = Column(String(20), default="manual")  # auto | manual | none

    # 状态
    status = Column(String(20), default="active")  # active | outdated | modified | conflict

    # 版本追踪
    source_version = Column(String(20))  # 源 Skill 版本
    target_version = Column(String(20))  # 目标 Skill 版本
    synced_version = Column(String(20))  # 已同步到的版本

    # 变更通知
    last_notified_at = Column(DateTime(timezone=True))
    last_synced_at = Column(DateTime(timezone=True))

    # 统计
    reuse_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
