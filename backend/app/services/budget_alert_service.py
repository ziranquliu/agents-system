"""
预算告警服务 — Token 成本控制

功能:
- 多级预算阈值告警（50% / 80% / 90% / 100%）
- 超额自动模型降级（GPT-4o → GPT-4o-mini）
- 按用户/Agent/全局维度设定预算
- 预算使用趋势分析
- 月度自动重置
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class BudgetLevel(str, Enum):
    OK = "ok"
    WARNING = "warning"          # 50%
    CRITICAL = "critical"        # 80%
    EMERGENCY = "emergency"      # 90%
    EXCEEDED = "exceeded"        # 100%+


class BudgetDimension(str, Enum):
    GLOBAL = "global"
    USER = "user"
    AGENT = "agent"
    PROJECT = "project"


@dataclass
class BudgetConfig:
    """预算配置"""
    dimension: BudgetDimension = BudgetDimension.GLOBAL
    dimension_id: str = "system"       # user_id / agent_id / project_id
    daily_limit_tokens: int = 0        # 0 = 不限制
    monthly_limit_tokens: int = 0
    daily_limit_cost: float = 0.0      # 美元
    monthly_limit_cost: float = 0.0
    threshold_warning: float = 0.5     # 50%
    threshold_critical: float = 0.8    # 80%
    threshold_emergency: float = 0.9   # 90%
    threshold_hard_limit: float = 1.0  # 100%
    auto_downgrade_enabled: bool = True
    downgrade_model: str = "gpt-4o-mini"
    original_model: str = "gpt-4o"
    enabled: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class BudgetUsage:
    """预算使用量"""
    date: str = ""
    daily_tokens: int = 0
    monthly_tokens: int = 0
    daily_cost: float = 0.0
    monthly_cost: float = 0.0
    downgraded: bool = False
    downgraded_at: Optional[datetime] = None
    restored_at: Optional[datetime] = None


@dataclass
class BudgetAlert:
    """预算告警"""
    level: BudgetLevel = BudgetLevel.OK
    dimension: BudgetDimension = BudgetDimension.GLOBAL
    dimension_id: str = ""
    threshold_percent: float = 0.0
    current_tokens: int = 0
    limit_tokens: int = 0
    current_cost: float = 0.0
    limit_cost: float = 0.0
    message: str = ""
    timestamp: Optional[datetime] = None
    auto_action: str = ""  # downgrade / none


class BudgetAlertService:
    """
    预算告警服务

    支持多维度（全局/用户/Agent/项目）× 多周期（日/月）的预算管理
    """

    def __init__(self):
        # 内存存储（生产应接入 DB）
        self._configs: dict[str, BudgetConfig] = {}
        self._usage: dict[str, BudgetUsage] = {}
        self._alerts: list[BudgetAlert] = []
        self._downgrade_log: list[dict[str, Any]] = []

    # ----------------------------------------------------------
    # 预算配置
    # ----------------------------------------------------------

    def set_budget(self, config: BudgetConfig) -> BudgetConfig:
        """设置/更新预算"""
        config.updated_at = datetime.now(timezone.utc)
        if not config.created_at:
            config.created_at = config.updated_at
        key = self._key(config.dimension, config.dimension_id)
        self._configs[key] = config
        logger.info(f"Budget set for {key}: daily={config.daily_limit_tokens}, monthly={config.monthly_limit_tokens}")
        return config

    def get_budget(
        self,
        dimension: BudgetDimension = BudgetDimension.GLOBAL,
        dimension_id: str = "system",
    ) -> Optional[BudgetConfig]:
        """获取预算配置"""
        return self._configs.get(self._key(dimension, dimension_id))

    def list_budgets(self) -> list[BudgetConfig]:
        """列出所有预算"""
        return list(self._configs.values())

    # ----------------------------------------------------------
    # 使用量记录与检查
    # ----------------------------------------------------------

    def record_usage(
        self,
        tokens: int,
        cost: float = 0.0,
        model: str = "",
        dimension: BudgetDimension = BudgetDimension.GLOBAL,
        dimension_id: str = "system",
    ) -> list[BudgetAlert]:
        """
        记录 Token 使用量并检查预算阈值

        Returns:
            触发的告警列表（可能为 0~4 个）
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        month_key = datetime.now(timezone.utc).strftime("%Y-%m")
        key = self._key(dimension, dimension_id)
        usage_key = f"{key}:{today}"

        # 获取或创建 usage
        if usage_key not in self._usage:
            self._usage[usage_key] = BudgetUsage(date=today)
        usage = self._usage[usage_key]

        usage.daily_tokens += tokens
        usage.daily_cost += cost

        # 月度累计（简化：所有当日 usage 累加）
        monthly_key = f"{key}:{month_key}"
        if monthly_key not in self._usage:
            self._usage[monthly_key] = BudgetUsage(date=month_key)
        monthly_usage = self._usage[monthly_key]
        monthly_usage.monthly_tokens += tokens
        monthly_usage.monthly_cost += cost

        # 检查阈值
        config = self.get_budget(dimension, dimension_id)
        if not config or not config.enabled:
            return []

        alerts = []

        # 检查日限额
        if config.daily_limit_tokens > 0:
            ratio = usage.daily_tokens / config.daily_limit_tokens
            alerts.extend(
                self._check_thresholds(config, usage.daily_tokens, config.daily_limit_tokens, ratio, "daily")
            )

        # 检查月限额
        if config.monthly_limit_tokens > 0:
            ratio = usage.monthly_tokens / config.monthly_limit_tokens
            alerts.extend(
                self._check_thresholds(config, usage.monthly_tokens, config.monthly_limit_tokens, ratio, "monthly")
            )

        # 检查日费用
        if config.daily_limit_cost > 0:
            cost_ratio = usage.daily_cost / config.daily_limit_cost
            alerts.extend(
                self._check_thresholds_cost(config, usage.daily_cost, config.daily_limit_cost, cost_ratio, "daily")
            )

        # 检查月费用
        if config.monthly_limit_cost > 0:
            cost_ratio = usage.monthly_cost / config.monthly_limit_cost
            alerts.extend(
                self._check_thresholds_cost(config, usage.monthly_cost, config.monthly_limit_cost, cost_ratio, "monthly")
            )

        # 自动降级
        if alerts and config.auto_downgrade_enabled:
            max_level = max(alerts, key=lambda a: list(BudgetLevel).index(a.level))
            if max_level.level in (BudgetLevel.CRITICAL, BudgetLevel.EMERGENCY, BudgetLevel.EXCEEDED):
                self._trigger_downgrade(config, dimension, dimension_id)
                for a in alerts:
                    a.auto_action = "downgrade"

        return alerts

    def _check_thresholds(
        self,
        config: BudgetConfig,
        current: int,
        limit: int,
        ratio: float,
        period: str,
    ) -> list[BudgetAlert]:
        """检查 token 阈值"""
        alerts = []
        ts = datetime.now(timezone.utc)

        threshold_map = [
            (config.threshold_warning, BudgetLevel.WARNING, "接近预算上限"),
            (config.threshold_critical, BudgetLevel.CRITICAL, "预算严重超支"),
            (config.threshold_emergency, BudgetLevel.EMERGENCY, "预算紧急告警"),
            (config.threshold_hard_limit, BudgetLevel.EXCEEDED, "预算已超额"),
        ]

        for threshold, level, msg in threshold_map:
            if ratio >= threshold:
                alert = BudgetAlert(
                    level=level,
                    dimension=config.dimension,
                    dimension_id=config.dimension_id,
                    threshold_percent=round(ratio * 100, 1),
                    current_tokens=current,
                    limit_tokens=limit,
                    message=f"[{period}] {msg}: 已用 {current}/{limit} ({ratio*100:.1f}%)",
                    timestamp=ts,
                )
                alerts.append(alert)
                self._alerts.append(alert)

        return alerts

    def _check_thresholds_cost(
        self,
        config: BudgetConfig,
        current: float,
        limit: float,
        ratio: float,
        period: str,
    ) -> list[BudgetAlert]:
        """检查费用阈值"""
        alerts = []
        ts = datetime.now(timezone.utc)

        threshold_map = [
            (config.threshold_warning, BudgetLevel.WARNING, "费用接近预算"),
            (config.threshold_critical, BudgetLevel.CRITICAL, "费用严重超支"),
            (config.threshold_emergency, BudgetLevel.EMERGENCY, "费用紧急告警"),
            (config.threshold_hard_limit, BudgetLevel.EXCEEDED, "费用已超额"),
        ]

        for threshold, level, msg in threshold_map:
            if ratio >= threshold:
                alert = BudgetAlert(
                    level=level,
                    dimension=config.dimension,
                    dimension_id=config.dimension_id,
                    threshold_percent=round(ratio * 100, 1),
                    current_cost=current,
                    limit_cost=limit,
                    message=f"[{period}] {msg}: 已用 ${current:.2f}/${limit:.2f} ({ratio*100:.1f}%)",
                    timestamp=ts,
                )
                alerts.append(alert)
                self._alerts.append(alert)

        return alerts

    # ----------------------------------------------------------
    # 自动降级与恢复
    # ----------------------------------------------------------

    def _trigger_downgrade(
        self,
        config: BudgetConfig,
        dimension: BudgetDimension,
        dimension_id: str,
    ):
        """触发模型降级"""
        key = self._key(dimension, dimension_id)
        usage_key = f"{key}:{datetime.now(timezone.utc).strftime('%Y-%m')}"
        if usage_key in self._usage:
            usage = self._usage[usage_key]
            if not usage.downgraded:
                usage.downgraded = True
                usage.downgraded_at = datetime.now(timezone.utc)
                record = {
                    "dimension": dimension.value,
                    "dimension_id": dimension_id,
                    "from_model": config.original_model,
                    "to_model": config.downgrade_model,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "reason": "budget_exceeded",
                }
                self._downgrade_log.append(record)
                logger.warning(
                    f"Auto-downgrade triggered for {key}: "
                    f"{config.original_model} → {config.downgrade_model}"
                )

    def restore_model(
        self,
        dimension: BudgetDimension = BudgetDimension.GLOBAL,
        dimension_id: str = "system",
    ) -> bool:
        """恢复模型（手动或月度自动重置）"""
        key = self._key(dimension, dimension_id)
        month_key = f"{key}:{datetime.now(timezone.utc).strftime('%Y-%m')}"
        if month_key in self._usage:
            usage = self._usage[month_key]
            if usage.downgraded:
                usage.downgraded = False
                usage.restored_at = datetime.now(timezone.utc)
                logger.info(f"Model restored for {key}")
                return True
        return False

    def auto_monthly_reset(self):
        """月度自动重置 — 新月开始时恢复所有降级"""
        first_day = datetime.now(timezone.utc).day
        if first_day == 1:
            for key, usage in self._usage.items():
                if usage.downgraded:
                    usage.downgraded = False
                    usage.restored_at = datetime.now(timezone.utc)
                    logger.info(f"Monthly auto-restore: {key}")

    # ----------------------------------------------------------
    # 状态查询
    # ----------------------------------------------------------

    def get_budget_status(
        self,
        dimension: BudgetDimension = BudgetDimension.GLOBAL,
        dimension_id: str = "system",
    ) -> dict[str, Any]:
        """获取完整预算状态"""
        config = self.get_budget(dimension, dimension_id)
        if not config:
            return {"error": "No budget configured"}

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        month_key = datetime.now(timezone.utc).strftime("%Y-%m")
        key = self._key(dimension, dimension_id)

        usage_key = f"{key}:{today}"
        usage = self._usage.get(usage_key, BudgetUsage(date=today))

        monthly_key = f"{key}:{month_key}"
        monthly_usage = self._usage.get(monthly_key, BudgetUsage(date=month_key))

        daily_token_pct = (
            (usage.daily_tokens / config.daily_limit_tokens * 100)
            if config.daily_limit_tokens > 0 else 0
        )
        monthly_token_pct = (
            (monthly_usage.monthly_tokens / config.monthly_limit_tokens * 100)
            if config.monthly_limit_tokens > 0 else 0
        )

        return {
            "dimension": dimension.value,
            "dimension_id": dimension_id,
            "daily": {
                "tokens_used": usage.daily_tokens,
                "tokens_limit": config.daily_limit_tokens,
                "token_pct": round(daily_token_pct, 1),
                "cost_used": round(usage.daily_cost, 4),
                "cost_limit": config.daily_limit_cost,
                "level": self._compute_level(daily_token_pct, config).value,
            },
            "monthly": {
                "tokens_used": monthly_usage.monthly_tokens,
                "tokens_limit": config.monthly_limit_tokens,
                "token_pct": round(monthly_token_pct, 1),
                "cost_used": round(monthly_usage.monthly_cost, 4),
                "cost_limit": config.monthly_limit_cost,
                "level": self._compute_level(monthly_token_pct, config).value,
            },
            "downgraded": usage.downgraded,
            "downgraded_at": usage.downgraded_at.isoformat() if usage.downgraded_at else None,
            "auto_downgrade_enabled": config.auto_downgrade_enabled,
            "downgrade_model": config.downgrade_model,
            "original_model": config.original_model,
        }

    def _compute_level(self, pct: float, config: BudgetConfig) -> BudgetLevel:
        if pct >= config.threshold_hard_limit * 100:
            return BudgetLevel.EXCEEDED
        elif pct >= config.threshold_emergency * 100:
            return BudgetLevel.EMERGENCY
        elif pct >= config.threshold_critical * 100:
            return BudgetLevel.CRITICAL
        elif pct >= config.threshold_warning * 100:
            return BudgetLevel.WARNING
        return BudgetLevel.OK

    def get_budget_history(
        self,
        dimension: BudgetDimension = BudgetDimension.GLOBAL,
        dimension_id: str = "system",
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """获取预算使用历史"""
        key = self._key(dimension, dimension_id)
        history = []
        now = datetime.now(timezone.utc)
        for i in range(days):
            d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            usage_key = f"{key}:{d}"
            usage = self._usage.get(usage_key)
            if usage:
                history.append({
                    "date": d,
                    "daily_tokens": usage.daily_tokens,
                    "daily_cost": round(usage.daily_cost, 4),
                })
        return list(reversed(history))

    def get_recent_alerts(self, limit: int = 50) -> list[dict[str, Any]]:
        """获取最近的告警"""
        return [
            {
                "level": a.level.value,
                "dimension": a.dimension.value,
                "dimension_id": a.dimension_id,
                "threshold_percent": a.threshold_percent,
                "message": a.message,
                "auto_action": a.auto_action,
                "timestamp": a.timestamp.isoformat() if a.timestamp else None,
            }
            for a in self._alerts[-limit:]
        ]

    def get_downgrade_log(self, limit: int = 50) -> list[dict[str, Any]]:
        """获取降级日志"""
        return self._downgrade_log[-limit:]

    @staticmethod
    def _key(dimension: BudgetDimension, dimension_id: str) -> str:
        return f"{dimension.value}:{dimension_id}"
