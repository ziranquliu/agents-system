"""
通知配置模型 - 自愈通知通道（Webhook/邮件）全局配置
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text

from app.db.session import Base


class NotifyMethod:
    """通知方式（字符串常量）"""
    WEBHOOK = "webhook"
    EMAIL = "email"
    BOTH = "both"
    OFF = "off"


class NotificationConfig(Base):
    """通知全局配置 - 单行记录（id 固定为 'default'）"""
    __tablename__ = "notification_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 通知方式: webhook | email | both | off
    notify_method = Column(String(16), default=NotifyMethod.BOTH)

    # Webhook
    webhook_url = Column(String(500), nullable=True)  # 全局默认 Webhook，Agent 级 webhook_url 优先

    # SMTP
    smtp_host = Column(String(255), nullable=True)
    smtp_port = Column(Integer, default=465)
    smtp_user = Column(String(255), nullable=True)
    smtp_password = Column(String(255), nullable=True)
    smtp_use_ssl = Column(Boolean, default=True)
    smtp_from = Column(String(255), nullable=True)  # 发件人地址，默认 smtp_user

    # 邮件默认收件人（逗号分隔，可为空，调用方显式传入）
    default_recipients = Column(Text, nullable=True)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def default_id() -> str:
        return "default"
