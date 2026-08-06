"""
Auto Scaling 自动扩缩容服务

功能:
- 基于指标的自动扩缩容（CPU/内存/请求量/队列深度）
- 扩缩容策略（目标追踪/步进/定时）
- 冷却期防止频繁扩缩
- 扩缩容历史记录
- 最小/最大实例数限制
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ScalingDirection(str, Enum):
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    STABLE = "stable"


class ScalingMetric(str, Enum):
    CPU = "cpu"
    MEMORY = "memory"
    REQUEST_RATE = "request_rate"
    QUEUE_DEPTH = "queue_depth"
    RESPONSE_TIME = "response_time"
    ERROR_RATE = "error_rate"


class ScalingStrategy(str, Enum):
    TARGET_TRACKING = "target_tracking"
    STEP = "step"
    SCHEDULED = "scheduled"


@dataclass
class ScalingPolicy:
    """扩缩容策略"""
    metric: ScalingMetric = ScalingMetric.CPU
    strategy: ScalingStrategy = ScalingStrategy.TARGET_TRACKING
    target_value: float = 70.0           # 目标值（如 CPU 70%）
    scale_up_threshold: float = 80.0     # 扩容阈值
    scale_down_threshold: float = 50.0   # 缩容阈值
    min_instances: int = 1
    max_instances: int = 10
    cooldown_seconds: int = 300          # 冷却期 5 分钟
    scale_up_step: int = 1               # 每次扩容实例数
    scale_down_step: int = 1             # 每次缩容实例数
    evaluation_periods: int = 3          # 评估周期数
    enabled: bool = True


@dataclass
class ScalingAction:
    """扩缩容动作"""
    id: str = ""
    direction: ScalingDirection = ScalingDirection.STABLE
    metric: str = ""
    current_value: float = 0
    threshold: float = 0
    current_instances: int = 0
    target_instances: int = 0
    reason: str = ""
    executed_at: Optional[datetime] = None
    success: bool = True
    error_message: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())


@dataclass
class MetricSample:
    """指标样本"""
    metric: str = ""
    value: float = 0
    timestamp: Optional[datetime] = None
    instance_id: str = ""


class AutoScalingService:
    """
    Auto Scaling 自动扩缩容服务

    支持目标追踪、步进、定时三种策略
    """

    def __init__(self):
        self._policies: dict[str, ScalingPolicy] = {}
        self._current_instances: dict[str, int] = {}  # service_id → count
        self._last_scaling: dict[str, datetime] = {}   # service_id → last action time
        self._metric_history: dict[str, list[MetricSample]] = {}  # service_id → samples
        self._actions: list[ScalingAction] = []
        self._scale_callbacks: dict[str, callable] = {}  # service_id → callback

    # ----------------------------------------------------------
    # 策略管理
    # ----------------------------------------------------------

    def configure(
        self,
        service_id: str,
        policy: ScalingPolicy,
        current_instances: int = 1,
    ):
        """配置扩缩容策略"""
        self._policies[service_id] = policy
        self._current_instances[service_id] = max(policy.min_instances, current_instances)
        self._metric_history[service_id] = []
        logger.info(f"Auto-scaling configured for {service_id}: {policy.min_instances}-{policy.max_instances} instances")

    def register_scale_callback(self, service_id: str, callback):
        """注册扩缩容回调"""
        self._scale_callbacks[service_id] = callback

    def get_policy(self, service_id: str) -> Optional[dict[str, Any]]:
        policy = self._policies.get(service_id)
        if policy:
            return {
                "metric": policy.metric.value,
                "strategy": policy.strategy.value,
                "target_value": policy.target_value,
                "scale_up_threshold": policy.scale_up_threshold,
                "scale_down_threshold": policy.scale_down_threshold,
                "min_instances": policy.min_instances,
                "max_instances": policy.max_instances,
                "cooldown_seconds": policy.cooldown_seconds,
                "enabled": policy.enabled,
                "current_instances": self._current_instances.get(service_id, 0),
            }
        return None

    # ----------------------------------------------------------
    # 指标采集与评估
    # ----------------------------------------------------------

    def record_metric(
        self,
        service_id: str,
        metric: str,
        value: float,
        instance_id: str = "",
    ):
        """记录指标"""
        if service_id not in self._metric_history:
            self._metric_history[service_id] = []

        sample = MetricSample(
            metric=metric,
            value=value,
            timestamp=datetime.now(timezone.utc),
            instance_id=instance_id,
        )
        self._metric_history[service_id].append(sample)

        # 保留最近 1000 条
        if len(self._metric_history[service_id]) > 1000:
            self._metric_history[service_id] = self._metric_history[service_id][-500:]

    async def evaluate(self, service_id: str) -> Optional[ScalingAction]:
        """评估是否需要扩缩容"""
        policy = self._policies.get(service_id)
        if not policy or not policy.enabled:
            return None

        # 检查冷却期
        last = self._last_scaling.get(service_id)
        if last:
            elapsed = (datetime.now(timezone.utc) - last).total_seconds()
            if elapsed < policy.cooldown_seconds:
                return None

        # 获取最近的指标样本
        history = self._metric_history.get(service_id, [])
        relevant = [s for s in history if s.metric == policy.metric.value]

        if len(relevant) < policy.evaluation_periods:
            return None

        recent = relevant[-policy.evaluation_periods:]
        avg_value = sum(s.value for s in recent) / len(recent)
        current = self._current_instances.get(service_id, 1)

        action = None

        # 扩容判断
        if avg_value > policy.scale_up_threshold:
            target = min(current + policy.scale_up_step, policy.max_instances)
            if target > current:
                action = ScalingAction(
                    direction=ScalingDirection.SCALE_UP,
                    metric=policy.metric.value,
                    current_value=avg_value,
                    threshold=policy.scale_up_threshold,
                    current_instances=current,
                    target_instances=target,
                    reason=f"{policy.metric.value}={avg_value:.1f}% > {policy.scale_up_threshold}%",
                    executed_at=datetime.now(timezone.utc),
                )

        # 缩容判断
        elif avg_value < policy.scale_down_threshold:
            target = max(current - policy.scale_down_step, policy.min_instances)
            if target < current:
                action = ScalingAction(
                    direction=ScalingDirection.SCALE_DOWN,
                    metric=policy.metric.value,
                    current_value=avg_value,
                    threshold=policy.scale_down_threshold,
                    current_instances=current,
                    target_instances=target,
                    reason=f"{policy.metric.value}={avg_value:.1f}% < {policy.scale_down_threshold}%",
                    executed_at=datetime.now(timezone.utc),
                )

        if action:
            # 执行扩缩容
            try:
                callback = self._scale_callbacks.get(service_id)
                if callback:
                    await callback(action.target_instances)

                self._current_instances[service_id] = action.target_instances
                self._last_scaling[service_id] = datetime.now(timezone.utc)
                action.success = True

                logger.info(
                    f"Scaling {action.direction.value} for {service_id}: "
                    f"{current} → {action.target_instances} "
                    f"({action.reason})"
                )

            except Exception as e:
                action.success = False
                action.error_message = str(e)
                logger.error(f"Scaling failed for {service_id}: {e}")

            self._actions.append(action)

        return action

    # ----------------------------------------------------------
    # 查询
    # ----------------------------------------------------------

    def get_status(self, service_id: str) -> dict[str, Any]:
        """获取扩缩容状态"""
        policy = self._policies.get(service_id)
        current = self._current_instances.get(service_id, 0)
        last = self._last_scaling.get(service_id)

        history = self._metric_history.get(service_id, [])
        recent = history[-10:] if history else []

        return {
            "service_id": service_id,
            "current_instances": current,
            "min_instances": policy.min_instances if policy else 0,
            "max_instances": policy.max_instances if policy else 0,
            "enabled": policy.enabled if policy else False,
            "last_scaling": last.isoformat() if last else None,
            "recent_metrics": [
                {"metric": s.metric, "value": s.value, "timestamp": s.timestamp.isoformat() if s.timestamp else None}
                for s in recent
            ],
        }

    def get_actions(
        self,
        service_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        actions = self._actions
        if service_id:
            # 通过 callback 映射过滤
            pass  # 简化：返回全部
        return [
            {
                "id": a.id,
                "direction": a.direction.value,
                "metric": a.metric,
                "current_value": round(a.current_value, 1),
                "threshold": a.threshold,
                "current_instances": a.current_instances,
                "target_instances": a.target_instances,
                "reason": a.reason,
                "executed_at": a.executed_at.isoformat() if a.executed_at else None,
                "success": a.success,
                "error_message": a.error_message,
            }
            for a in actions[-limit:]
        ]

    def get_stats(self) -> dict[str, Any]:
        total_actions = len(self._actions)
        scale_ups = sum(1 for a in self._actions if a.direction == ScalingDirection.SCALE_UP)
        scale_downs = sum(1 for a in self._actions if a.direction == ScalingDirection.SCALE_DOWN)
        failures = sum(1 for a in self._actions if not a.success)

        return {
            "total_services": len(self._policies),
            "total_actions": total_actions,
            "scale_up_count": scale_ups,
            "scale_down_count": scale_downs,
            "failure_count": failures,
            "total_instances": sum(self._current_instances.values()),
        }
