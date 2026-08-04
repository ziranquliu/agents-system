"""
自愈通知服务 - Webhook / 邮件通知通道

提供:
- send_webhook(url, payload): POST JSON 到 Webhook，失败降级为日志
- send_email(to, subject, body): 通过配置的 SMTP 发送邮件
- notify(method, target, title, content): 统一入口，按方式分发
"""
import logging
import smtplib
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.notification import NotificationConfig, NotifyMethod

logger = logging.getLogger(__name__)


async def send_webhook(url: str, payload: dict) -> bool:
    """向 Webhook 发送 JSON 负载。失败时记录日志并返回 False（不抛出）。"""
    if not url:
        logger.warning("send_webhook: url 为空，跳过")
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code >= 300:
                logger.warning(
                    "send_webhook: 目标 %s 返回非 2xx 状态 %s，响应: %s",
                    url, resp.status_code, resp.text[:500],
                )
                return False
            logger.info("send_webhook: 成功发送到 %s (status=%s)", url, resp.status_code)
            return True
    except Exception as exc:  # noqa: BLE001 - 通知失败不影响主流程
        logger.error("send_webhook: 发送到 %s 失败: %s", url, exc)
        return False


async def send_email(to: str, subject: str, body: str,
                     cfg: Optional[NotificationConfig] = None) -> bool:
    """通过配置的 SMTP 发送邮件。cfg 为 None 时读取全局配置。"""
    if not cfg or not cfg.smtp_host:
        logger.warning("send_email: SMTP 未配置，跳过")
        return False
    if not to:
        logger.warning("send_email: 收件人为空，跳过")
        return False
    try:
        smtp_from = cfg.smtp_from or cfg.smtp_user or "noreply@localhost"
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = formataddr((str(Header("Agent System", "utf-8")), smtp_from))
        msg["To"] = to

        if cfg.smtp_use_ssl:
            server = smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port or 465, timeout=15)
        else:
            server = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port or 25, timeout=15)
            server.starttls()
        try:
            if cfg.smtp_user:
                from app.core.encryption import decrypt_secret
                server.login(cfg.smtp_user, decrypt_secret(cfg.smtp_password) or "")
            server.sendmail(smtp_from, [t.strip() for t in to.split(",") if t.strip()], msg.as_string())
            logger.info("send_email: 已发送到 %s", to)
            return True
        finally:
            try:
                server.quit()
            except Exception:  # noqa: BLE001
                pass
    except Exception as exc:  # noqa: BLE001 - 通知失败不影响主流程
        logger.error("send_email: 发送到 %s 失败: %s", to, exc)
        return False


async def notify(method: str, target: Optional[str], title: str, content: str,
                 webhook_url: Optional[str] = None,
                 cfg: Optional[NotificationConfig] = None) -> dict:
    """
    统一通知入口。

    参数:
        method: webhook | email | both | off（来自 NotifyMethod 常量）
        target: 邮件收件人（逗号分隔），webhook 模式下可为空
        title: 通知标题
        content: 通知正文
        webhook_url: 优先使用的 Webhook 地址（Agent 级）
        cfg: 通知配置对象；为 None 时仅能发送 webhook（未配置 SMTP 时邮件降级）

    返回:
        {"webhook": bool, "email": bool} 各通道是否成功
    """
    if method == NotifyMethod.OFF or not method:
        logger.info("notify: 通知方式为 off，跳过")
        return {"webhook": False, "email": False}

    send_web = method in (NotifyMethod.WEBHOOK, NotifyMethod.BOTH)
    send_mail = method in (NotifyMethod.EMAIL, NotifyMethod.BOTH)

    payload = {
        "title": title,
        "content": content,
        "event": "self_heal",
        "timestamp": None,  # 由调用方填充
    }

    webhook_ok = email_ok = False

    # Webhook：优先 Agent 级 webhook_url，其次全局配置
    if send_web:
        url = webhook_url or (cfg.webhook_url if cfg else None)
        webhook_ok = await send_webhook(url, payload)

    # 邮件：需要收件人 + SMTP 配置
    if send_mail and target:
        email_ok = await send_email(target, title, content, cfg)

    return {"webhook": webhook_ok, "email": email_ok}


async def get_notification_config(db: AsyncSession) -> NotificationConfig:
    """读取全局通知配置（单行），不存在则创建默认记录。"""
    result = await db.execute(select(NotificationConfig).limit(1))
    cfg = result.scalars().first()
    if cfg is None:
        cfg = NotificationConfig(id=NotificationConfig.default_id())
        db.add(cfg)
        await db.commit()
        await db.refresh(cfg)
    return cfg
