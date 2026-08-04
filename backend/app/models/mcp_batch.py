"""
MCP 批量安装与跨 Agent 同步模型
"""
import uuid

from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean
from sqlalchemy.sql import func

from app.db.session import Base


class MCPAgentBinding(Base):
    """MCP 与 Agent 绑定关系（跨 Agent 同步）"""
    __tablename__ = "mcp_agent_bindings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mcp_server_id = Column(String(36), nullable=False, index=True)
    mcp_server_name = Column(String(100))
    agent_id = Column(String(36), nullable=False, index=True)
    agent_name = Column(String(100))

    # 同步模式
    sync_mode = Column(String(20), default="shared")  # shared | independent | template

    # 连接配置覆盖
    override_config = Column(Text)  # JSON: {"url": "...", "api_key": "..."}
    override_protocol = Column(String(20))
    override_auth = Column(Text)  # JSON: 敏感配置（加密存储）

    # 模板模式：引用模板 ID
    template_id = Column(String(36))

    # 状态
    status = Column(String(20), default="active")  # active | outdated | error | syncing

    # 版本追踪
    source_version = Column(String(20))
    synced_version = Column(String(20))

    # 加密
    is_encrypted = Column(Boolean, default=False)
    encryption_method = Column(String(20))  # aes-256

    # 同步历史
    last_synced_at = Column(DateTime(timezone=True))
    sync_error = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class MCPBatchInstallQueue(Base):
    """MCP 批量安装队列"""
    __tablename__ = "mcp_batch_install_queues"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String(20), default="pending")  # pending | running | completed | failed
    total_items = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)
    created_by = Column(String(36))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))


class MCPBatchInstallItem(Base):
    """MCP 批量安装项"""
    __tablename__ = "mcp_batch_install_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    queue_id = Column(String(36), nullable=False, index=True)
    mcp_server_id = Column(String(36), nullable=False)
    mcp_server_name = Column(String(100))
    agent_id = Column(String(36), nullable=False)
    sync_mode = Column(String(20), default="shared")
    status = Column(String(20), default="pending")  # pending | success | failed | skipped
    error_message = Column(Text)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
