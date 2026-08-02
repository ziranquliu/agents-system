import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Boolean
from app.db.session import Base

"""
统一更新检测中心 — 更新快照/回滚 模型
"""




class UpdateSnapshot(Base):
    """更新快照 — 每次更新前保留旧状态，用于回滚"""
    __tablename__ = "update_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    component_type = Column(String(20), index=True)  # skill / mcp / agent / model
    component_id = Column(String(36), index=True)
    component_name = Column(String(200), nullable=True)
    old_version = Column(String(50), nullable=True)
    new_version = Column(String(50), nullable=True)
    before_state = Column(Text, nullable=True)  # JSON: 更新前的完整状态（版本/配置快照）
    after_state = Column(Text, nullable=True)  # JSON: 更新后的状态
    created_by = Column(String(100), nullable=True)
    rolled_back = Column(Boolean, default=False)  # 是否已回滚
    rollback_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class UpdateLog(Base):
    """更新操作日志 — 更新时间/变更内容/兼容性结果/回滚状态"""
    __tablename__ = "update_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    component_type = Column(String(20), index=True)
    component_id = Column(String(36), index=True)
    component_name = Column(String(200), nullable=True)
    action = Column(String(20), default="update")  # update / rollback / batch_update
    old_version = Column(String(50), nullable=True)
    new_version = Column(String(50), nullable=True)
    compatibility = Column(String(20), default="pass")  # pass / warning / fail
    detail = Column(Text, nullable=True)
    status = Column(String(20), default="success")  # success / failed / rolled_back
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
