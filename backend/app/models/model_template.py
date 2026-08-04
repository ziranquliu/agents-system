"""
模型配置模板增强 - 版本管理 + 绑定复用 + 灰度同步
"""
import uuid

from sqlalchemy import Column, String, Text, DateTime, Integer
from sqlalchemy.sql import func

from app.db.session import Base


class ModelTemplateVersion(Base):
    """模型配置模板版本历史"""
    __tablename__ = "model_template_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id = Column(String(36), nullable=False, index=True)
    version = Column(Integer, nullable=False)  # 版本号，从1开始
    change_log = Column(String(500))  # 变更说明

    # 快照：完整的配置内容
    name = Column(String(100), nullable=False)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    config = Column(Text)  # JSON
    description = Column(Text)

    created_by = Column(String(36))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ModelTemplateBinding(Base):
    """模型模板与智能体的绑定关系"""
    __tablename__ = "model_template_bindings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id = Column(String(36), nullable=False, index=True)
    agent_id = Column(String(36), nullable=False, index=True)

    # 参数覆盖（仅存覆盖项，其余继承模板）
    override_config = Column(Text)  # JSON: {"temperature": 0.5, "max_tokens": 2048}
    override_model = Column(String(100))  # 可覆盖模型名
    override_provider = Column(String(50))  # 可覆盖供应商

    # 同步模式
    sync_mode = Column(String(20), default="auto")  # auto | manual | gray

    # 灰度同步
    gray_percentage = Column(Integer, default=100)  # 灰度百分比 0-100
    gray_status = Column(String(20), default="synced")  # pending | syncing | synced | failed | rolled_back
    gray_synced_version = Column(Integer)  # 已同步到的模板版本
    gray_error = Column(String(500))

    # 同步历史
    last_synced_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
