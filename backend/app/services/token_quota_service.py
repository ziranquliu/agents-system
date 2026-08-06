"""
用户/Agent Token 配额管理服务

功能:
- Token 配额 CRUD (daily/monthly/total)
- 按用户/Agent/项目维度
- 配额使用跟踪
- 超限通知
- 配额调整历史
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TokenQuota:
    """Token 配额"""
    id: str = ""
    entity_type: str = "user"  # user / agent / project
    entity_id: str = ""
    daily_limit: int = 0  # 0 = 无限制
    monthly_limit: int = 0
    total_limit: int = 0
    daily_used: int = 0
    monthly_used: int = 0
    total_used: int = 0
    period_reset_at: str = ""
    created_at: str = ""
    updated_at: str = ""
    alert_threshold: float = 0.8  # 80% 告警


@dataclass
class QuotaUsageRecord:
    """配额使用记录"""
    timestamp: str = ""
    tokens: int = 0
    model: str = ""
    agent_id: str = ""
    operation: str = ""  # chat / completion / embedding


@dataclass
class QuotaAlert:
    """配额告警"""
    quota_id: str = ""
    entity_id: str = ""
    alert_type: str = ""  # threshold / exceeded
    dimension: str = ""  # daily / monthly / total
    usage_percent: float = 0
    limit: int = 0
    used: int = 0
    timestamp: str = ""


class TokenQuotaService:
    """
    Token 配额管理服务

    - 3 维度: daily / monthly / total
    - 3 实体: user / agent / project
    - 使用跟踪 + 告警
    - 配额调整历史
    """

    def __init__(self):
        self._quotas: dict[str, TokenQuota] = {}
        self._usage_records: dict[str, list[QuotaUsageRecord]] = defaultdict(list)
        self._alerts: list[QuotaAlert] = []
        self._adjustments: list[dict] = []
        self._on_exceed_callbacks: list[Any] = []

    # ----------------------------------------------------------
    # CRUD
    # ----------------------------------------------------------

    def create_quota(
        self,
        entity_type: str,
        entity_id: str,
        daily_limit: int = 0,
        monthly_limit: int = 0,
        total_limit: int = 0,
        alert_threshold: float = 0.8,
    ) -> dict:
        """创建配额"""
        quota_id = f"quota_{entity_type}_{entity_id}"
        if quota_id in self._quotas:
            return {"error": "配额已存在"}

        now = datetime.now(timezone.utc).isoformat()
        quota = TokenQuota(
            id=quota_id,
            entity_type=entity_type,
            entity_id=entity_id,
            daily_limit=daily_limit,
            monthly_limit=monthly_limit,
            total_limit=total_limit,
            alert_threshold=alert_threshold,
            created_at=now,
            updated_at=now,
        )
        self._quotas[quota_id] = quota
        return {"quota_id": quota_id, "created": True}

    def get_quota(self, quota_id: str) -> Optional[dict]:
        q = self._quotas.get(quota_id)
        if not q:
            return None
        return {
            "id": q.id,
            "entity_type": q.entity_type,
            "entity_id": q.entity_id,
            "daily_limit": q.daily_limit,
            "monthly_limit": q.monthly_limit,
            "total_limit": q.total_limit,
            "daily_used": q.daily_used,
            "monthly_used": q.monthly_used,
            "total_used": q.total_used,
            "daily_remaining": q.daily_limit - q.daily_used if q.daily_limit else None,
            "monthly_remaining": q.monthly_limit - q.monthly_used if q.monthly_limit else None,
            "total_remaining": q.total_limit - q.total_used if q.total_limit else None,
            "alert_threshold": q.alert_threshold,
            "created_at": q.created_at,
            "updated_at": q.updated_at,
        }

    def list_quotas(
        self, entity_type: str = "", entity_id: str = "", limit: int = 50
    ) -> list[dict]:
        quotas = list(self._quotas.values())
        if entity_type:
            quotas = [q for q in quotas if q.entity_type == entity_type]
        if entity_id:
            quotas = [q for q in quotas if q.entity_id == entity_id]
        return [
            {"id": q.id, "entity_type": q.entity_type, "entity_id": q.entity_id,
             "daily_used": q.daily_used, "monthly_used": q.monthly_used}
            for q in quotas[:limit]
        ]

    def update_quota(self, quota_id: str, updates: dict) -> dict:
        """更新配额限制"""
        q = self._quotas.get(quota_id)
        if not q:
            return {"error": "配额不存在"}

        allowed = {"daily_limit", "monthly_limit", "total_limit", "alert_threshold"}
        for k, v in updates.items():
            if k in allowed:
                setattr(q, k, v)
        q.updated_at = datetime.now(timezone.utc).isoformat()

        self._adjustments.append({
            "quota_id": quota_id,
            "updates": updates,
            "timestamp": q.updated_at,
        })
        return {"updated": True, "quota_id": quota_id}

    def delete_quota(self, quota_id: str) -> dict:
        if quota_id in self._quotas:
            del self._quotas[quota_id]
            return {"deleted": True}
        return {"error": "配额不存在"}

    # ----------------------------------------------------------
    # 使用跟踪
    # ----------------------------------------------------------

    def record_usage(
        self,
        entity_type: str,
        entity_id: str,
        tokens: int,
        model: str = "",
        agent_id: str = "",
        operation: str = "chat",
    ) -> dict:
        """记录 Token 使用"""
        quota_id = f"quota_{entity_type}_{entity_id}"
        quota = self._quotas.get(quota_id)
        if not quota:
            return {"error": "配额不存在"}

        record = QuotaUsageRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            tokens=tokens,
            model=model,
            agent_id=agent_id,
            operation=operation,
        )
        self._usage_records[quota_id].append(record)

        quota.daily_used += tokens
        quota.monthly_used += tokens
        quota.total_used += tokens
        quota.updated_at = record.timestamp

        # 告警检查
        alerts = self._check_thresholds(quota)
        if alerts:
            self._alerts.extend(alerts)

        # 限制检查
        exceeded = self._check_exceeded(quota)
        return {
            "recorded": True,
            "tokens": tokens,
            "daily_used": quota.daily_used,
            "monthly_used": quota.monthly_used,
            "total_used": quota.total_used,
            "alerts": [
                {"type": a.alert_type, "dimension": a.dimension, "percent": a.usage_percent}
                for a in alerts
            ],
            "exceeded": exceeded,
        }

    def check_available(self, entity_type: str, entity_id: str, requested_tokens: int) -> dict:
        """检查是否可用"""
        quota_id = f"quota_{entity_type}_{entity_id}"
        quota = self._quotas.get(quota_id)
        if not quota:
            return {"available": True, "reason": "无配额限制"}

        reasons = []
        available = True

        if quota.daily_limit and quota.daily_used + requested_tokens > quota.daily_limit:
            available = False
            reasons.append(f"日配额不足: {quota.daily_used}/{quota.daily_limit}")

        if quota.monthly_limit and quota.monthly_used + requested_tokens > quota.monthly_limit:
            available = False
            reasons.append(f"月配额不足: {quota.monthly_used}/{quota.monthly_limit}")

        if quota.total_limit and quota.total_used + requested_tokens > quota.total_limit:
            available = False
            reasons.append(f"总配额不足: {quota.total_used}/{quota.total_limit}")

        return {"available": available, "reasons": reasons}

    def reset_daily(self):
        """重置日配额 (定时任务调用)"""
        for q in self._quotas.values():
            q.daily_used = 0
        logger.info("已重置所有日配额")

    def reset_monthly(self):
        """重置月配额"""
        for q in self._quotas.values():
            q.monthly_used = 0
        logger.info("已重置所有月配额")

    # ----------------------------------------------------------
    # 告警
    # ----------------------------------------------------------

    def _check_thresholds(self, quota: TokenQuota) -> list[QuotaAlert]:
        """检查告警阈值"""
        alerts = []
        now = datetime.now(timezone.utc).isoformat()

        for dim, limit, used in [
            ("daily", quota.daily_limit, quota.daily_used),
            ("monthly", quota.monthly_limit, quota.monthly_used),
            ("total", quota.total_limit, quota.total_used),
        ]:
            if limit > 0:
                pct = used / limit
                if pct >= quota.alert_threshold:
                    alerts.append(QuotaAlert(
                        quota_id=quota.id,
                        entity_id=quota.entity_id,
                        alert_type="exceeded" if pct >= 1.0 else "threshold",
                        dimension=dim,
                        usage_percent=round(pct * 100, 1),
                        limit=limit,
                        used=used,
                        timestamp=now,
                    ))
        return alerts

    def _check_exceeded(self, quota: TokenQuota) -> list[str]:
        """检查是否超限"""
        exceeded = []
        if quota.daily_limit and quota.daily_used > quota.daily_limit:
            exceeded.append("daily")
        if quota.monthly_limit and quota.monthly_used > quota.monthly_limit:
            exceeded.append("monthly")
        if quota.total_limit and quota.total_used > quota.total_limit:
            exceeded.append("total")
        return exceeded

    # ----------------------------------------------------------
    # 查询
    # ----------------------------------------------------------

    def get_usage_history(self, quota_id: str, limit: int = 100) -> list[dict]:
        records = self._usage_records.get(quota_id, [])
        return [
            {"timestamp": r.timestamp, "tokens": r.tokens, "model": r.model, "operation": r.operation}
            for r in records[-limit:]
        ]

    def get_alerts(self, limit: int = 50) -> list[dict]:
        return [
            {
                "quota_id": a.quota_id,
                "entity_id": a.entity_id,
                "alert_type": a.alert_type,
                "dimension": a.dimension,
                "usage_percent": a.usage_percent,
                "timestamp": a.timestamp,
            }
            for a in self._alerts[-limit:]
        ]

    def get_adjustments(self, limit: int = 50) -> list[dict]:
        return self._adjustments[-limit:]

    def get_statistics(self) -> dict:
        quotas = list(self._quotas.values())
        total_daily = sum(q.daily_limit for q in quotas if q.daily_limit > 0)
        total_used_daily = sum(q.daily_used for q in quotas)
        return {
            "total_quotas": len(quotas),
            "by_entity_type": {
                et: len([q for q in quotas if q.entity_type == et])
                for et in {"user", "agent", "project"}
            },
            "total_daily_limit": total_daily,
            "total_daily_used": total_used_daily,
            "total_alerts": len(self._alerts),
            "total_adjustments": len(self._adjustments),
        }


# 全局实例
_quota_service: Optional[TokenQuotaService] = None


def get_quota_service() -> TokenQuotaService:
    global _quota_service
    if _quota_service is None:
        _quota_service = TokenQuotaService()
    return _quota_service
