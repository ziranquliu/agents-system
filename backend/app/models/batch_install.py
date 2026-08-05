"""
批量 Skill 分配与安装模型 - 依赖预检、安装队列、报告
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, Integer
from sqlalchemy.sql import func

from app.db.session import Base


class BatchInstallQueue(Base):
    """批量安装队列"""
    __tablename__ = "batch_install_queues"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    operation = Column(String(20), nullable=False)  # install | uninstall | bind | unbind
    status = Column(String(20), default="pending")  # pending | prechecking | running | completed | failed | cancelled

    # 统计
    total_items = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)
    warn_count = Column(Integer, default=0)

    # 依赖预检
    precheck_status = Column(String(20))  # passed | warning | blocked
    precheck_summary = Column(Text)  # JSON

    # 来源
    created_by = Column(String(36))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True))


class BatchInstallItem(Base):
    """批量安装项（每个 Skill-Agent 对）"""
    __tablename__ = "batch_install_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    queue_id = Column(String(36), nullable=False, index=True)
    skill_id = Column(String(36), nullable=False)
    skill_name = Column(String(100))
    agent_id = Column(String(36), nullable=False)
    agent_name = Column(String(100))

    # 依赖预检结果
    dep_check_status = Column(String(20))  # passed | warning | blocked
    dep_check_detail = Column(Text)  # JSON: 每个依赖的检查详情

    # 安装状态
    status = Column(String(20), default="pending")  # pending | running | success | failed | skipped
    error_message = Column(Text)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc))
