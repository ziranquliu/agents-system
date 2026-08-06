"""
告警静默管理器 — 时间窗口静默 + 冷却去重 + 告警生命周期管理

功能:
1. 时间窗口静默: 按 HH:MM 和星期几自动静默告警通知
2. 冷却去重: 同一告警在 cooldown_minutes 内不重复通知
3. 告警生命周期: firing → acknowledged → resolved
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.monitoring import AlertConfig, AlertRecord

logger = logging.getLogger(__name__)


def _safe_json(s, default=None):
    if not s:
        return default if default is not None else []
    try:
        return json.loads(s) if isinstance(s, str) else s
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else []


class AlertSilenceManager:
    """告警静默管理器"""

    @staticmethod
    def is_silenced(config: AlertConfig, now: Optional[datetime] = None) -> bool:
        """
        判断当前时间是否在告警静默窗口内。

        规则:
        1. 如果 silence_start 和 silence_end 都为空 → 不静默
        2. 如果 silence_days 配置了,检查当前星期几是否在列表中
        3. 检查当前 UTC 时间是否在 silence_start ~ silence_end 范围内
        4. 支持跨天静默(如 silence_start="22:00", silence_end="06:00")
        """
        if not config.silence_start or not config.silence_end:
            return False

        now = now or datetime.now(timezone.utc)

        # 星期几过滤
        silence_days = _safe_json(config.silence_days, [])
        if silence_days:
            # weekday(): 0=周一, 6=周日
            current_weekday = now.weekday()
            if current_weekday not in silence_days:
                return False

        # 解析时间
        try:
            start_h, start_m = map(int, config.silence_start.split(":"))
            end_h, end_m = map(int, config.silence_end.split(":"))
        except (ValueError, AttributeError):
            return False

        current_minutes = now.hour * 60 + now.minute
        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m

        if start_minutes <= end_minutes:
            # 同天静默: 如 12:00 ~ 18:00
            return start_minutes <= current_minutes <= end_minutes
        else:
            # 跨天静默: 如 22:00 ~ 06:00
            return current_minutes >= start_minutes or current_minutes <= end_minutes

    @staticmethod
    def is_in_cooldown(config: AlertConfig, last_fired_at: Optional[datetime]) -> bool:
        """
        判断告警是否在冷却期内。

        如果 last_fired_at 为空 → 不在冷却期
        如果当前时间 - last_fired_at < cooldown_minutes → 在冷却期
        """
        if not last_fired_at:
            return False

        cooldown = config.cooldown_minutes or 15
        now = datetime.now(timezone.utc)
        elapsed = (now - last_fired_at).total_seconds() / 60
        return elapsed < cooldown

    @staticmethod
    async def should_notify(
        db: AsyncSession,
        config: AlertConfig,
    ) -> tuple[bool, str]:
        """
        综合判断是否应发送通知。

        返回: (should_send, reason)
        """
        # 1. 告警是否启用
        if not config.enabled:
            return False, "告警配置已禁用"

        # 2. 时间窗口静默
        if AlertSilenceManager.is_silenced(config):
            return False, f"当前在静默窗口内({config.silence_start}~{config.silence_end})"

        # 3. 冷却期检查 — 查找最近一次 firing 记录
        result = await db.execute(
            select(AlertRecord)
            .where(
                and_(
                    AlertRecord.config_id == config.id,
                    AlertRecord.status == "firing",
                )
            )
            .order_by(AlertRecord.fired_at.desc())
            .limit(1)
        )
        last_record = result.scalar_one_or_none()
        if last_record and AlertSilenceManager.is_in_cooldown(config, last_record.fired_at):
            remaining = config.cooldown_minutes - (datetime.now(timezone.utc) - last_record.fired_at).total_seconds() / 60
            return False, f"冷却期中(剩余{remaining:.0f}分钟)"

        return True, "允许通知"

    @staticmethod
    async def acknowledge_alert(
        db: AsyncSession, record_id: str, user_id: str
    ) -> Optional[AlertRecord]:
        """确认告警"""
        result = await db.execute(
            select(AlertRecord).where(AlertRecord.id == record_id)
        )
        record = result.scalar_one_or_none()
        if not record or record.status != "firing":
            return None
        record.status = "acknowledged"
        record.acknowledged_by = user_id
        record.acknowledged_at = datetime.now(timezone.utc)
        await db.flush()
        return record

    @staticmethod
    async def resolve_alert(db: AsyncSession, record_id: str) -> Optional[AlertRecord]:
        """解除告警"""
        result = await db.execute(
            select(AlertRecord).where(AlertRecord.id == record_id)
        )
        record = result.scalar_one_or_none()
        if not record or record.status == "resolved":
            return None
        record.status = "resolved"
        record.resolved_at = datetime.now(timezone.utc)
        await db.flush()
        return record

    @staticmethod
    async def silence_alert_config(
        db: AsyncSession,
        config_id: str,
        silence_start: str,
        silence_end: str,
        silence_days: Optional[list] = None,
        cooldown_minutes: int = 15,
    ) -> Optional[AlertConfig]:
        """配置告警静默规则"""
        result = await db.execute(
            select(AlertConfig).where(AlertConfig.id == config_id)
        )
        config = result.scalar_one_or_none()
        if not config:
            return None

        config.silence_start = silence_start
        config.silence_end = silence_end
        if silence_days is not None:
            config.silence_days = json.dumps(silence_days)
        config.cooldown_minutes = cooldown_minutes
        config.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return config

    @staticmethod
    async def clear_silence(
        db: AsyncSession, config_id: str
    ) -> Optional[AlertConfig]:
        """清除告警静默规则"""
        result = await db.execute(
            select(AlertConfig).where(AlertConfig.id == config_id)
        )
        config = result.scalar_one_or_none()
        if not config:
            return None
        config.silence_start = None
        config.silence_end = None
        config.silence_days = None
        config.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return config

    @staticmethod
    async def batch_resolve(
        db: AsyncSession, agent_id: Optional[str] = None
    ) -> int:
        """批量解除某 Agent 的所有 firing 告警"""
        where = [AlertRecord.status == "firing"]
        if agent_id:
            where.append(AlertRecord.agent_id == agent_id)

        result = await db.execute(
            select(AlertRecord).where(and_(*where))
        )
        records = result.scalars().all()
        now = datetime.now(timezone.utc)
        for record in records:
            record.status = "resolved"
            record.resolved_at = now
        await db.flush()
        return len(records)

    @staticmethod
    async def get_active_alerts(
        db: AsyncSession,
        priority: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> list[AlertRecord]:
        """获取当前活跃告警(firing + acknowledged)"""
        where = [AlertRecord.status.in_(["firing", "acknowledged"])]
        if priority:
            where.append(AlertRecord.priority == priority)
        if agent_id:
            where.append(AlertRecord.agent_id == agent_id)

        result = await db.execute(
            select(AlertRecord)
            .where(and_(*where))
            .order_by(AlertRecord.fired_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_alert_stats(db: AsyncSession) -> dict:
        """获取告警统计"""
        total_result = await db.execute(select(AlertRecord))
        records = list(total_result.scalars().all())

        stats = {"total": len(records), "firing": 0, "acknowledged": 0, "resolved": 0}
        by_priority = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}

        for r in records:
            status = r.status
            if status in stats:
                stats[status] += 1
            priority = r.priority or "P2"
            if priority in by_priority:
                by_priority[priority] += 1

        stats["by_priority"] = by_priority
        return stats
