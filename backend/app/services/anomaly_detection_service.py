"""
异常行为检测规则引擎

功能:
- 规则引擎（声明式规则定义）
- 4 大检测规则：异常时间段/高频失败/权限越界/批量删除
- 滑动窗口计数器
- 告警生成与去重
- 规则热更新
"""

import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class RuleType(str, Enum):
    UNUSUAL_TIME = "unusual_time"         # 异常时间段操作
    HIGH_FREQ_FAILURE = "high_freq_failure"  # 高频失败
    PERMISSION_DENIED = "permission_denied"  # 权限越界
    BATCH_DELETE = "batch_delete"         # 批量删除
    CUSTOM = "custom"                     # 自定义规则


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DetectionRule:
    """检测规则"""
    id: str = ""
    name: str = ""
    rule_type: RuleType = RuleType.CUSTOM
    enabled: bool = True
    severity: Severity = Severity.MEDIUM
    # 规则参数
    params: dict[str, Any] = field(default_factory=dict)
    # 异常时间段: {"start_hour": 0, "end_hour": 6}
    # 高频失败: {"window_seconds": 60, "threshold": 5, "operator_id": ""}
    # 权限越界: {"allowed_actions": [], "denied_actions": ["delete", "admin"]}
    # 批量删除: {"window_seconds": 300, "threshold": 10}
    description: str = ""
    cooldown_seconds: int = 300  # 告警冷却期
    last_triggered: Optional[datetime] = None

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())


@dataclass
class AnomalyAlert:
    """异常告警"""
    id: str = ""
    rule_id: str = ""
    rule_name: str = ""
    rule_type: str = ""
    severity: str = ""
    operator_id: str = ""
    target_id: str = ""
    description: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    detected_at: Optional[datetime] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())


class AnomalyDetectionService:
    """
    异常行为检测规则引擎

    内置规则:
    1. 异常时间段操作 (0:00-6:00)
    2. 高频失败 (N次/分钟)
    3. 权限越界尝试
    4. 批量删除检测
    """

    def __init__(self):
        self._rules: dict[str, DetectionRule] = {}
        self._sliding_windows: dict[str, deque] = defaultdict(lambda: deque())
        self._alerts: list[AnomalyAlert] = []
        self._stats: dict[str, int] = defaultdict(int)
        self._setup_default_rules()

    def _setup_default_rules(self):
        """设置默认规则"""
        rules = [
            DetectionRule(
                name="异常时间段操作",
                rule_type=RuleType.UNUSUAL_TIME,
                severity=Severity.HIGH,
                params={"start_hour": 0, "end_hour": 6},
                description="在凌晨 0:00-6:00 执行敏感操作",
            ),
            DetectionRule(
                name="高频失败检测",
                rule_type=RuleType.HIGH_FREQ_FAILURE,
                severity=Severity.MEDIUM,
                params={"window_seconds": 60, "threshold": 5},
                description="同一操作者在60秒内失败超过5次",
            ),
            DetectionRule(
                name="权限越界检测",
                rule_type=RuleType.PERMISSION_DENIED,
                severity=Severity.CRITICAL,
                params={
                    "denied_actions": [
                        "delete_agent", "delete_skill", "delete_mcp",
                        "admin_config", "force_logout", "system_reset",
                    ],
                },
                description="尝试执行未授权的高危操作",
            ),
            DetectionRule(
                name="批量删除检测",
                rule_type=RuleType.BATCH_DELETE,
                severity=Severity.HIGH,
                params={"window_seconds": 300, "threshold": 10},
                description="在5分钟内批量删除超过10条记录",
            ),
        ]
        for rule in rules:
            self._rules[rule.id] = rule

    # ----------------------------------------------------------
    # 规则管理
    # ----------------------------------------------------------

    def add_rule(self, rule: DetectionRule) -> str:
        self._rules[rule.id] = rule
        return rule.id

    def update_rule(self, rule_id: str, **kwargs) -> bool:
        rule = self._rules.get(rule_id)
        if not rule:
            return False
        for k, v in kwargs.items():
            if hasattr(rule, k):
                setattr(rule, k, v)
        return True

    def remove_rule(self, rule_id: str) -> bool:
        return self._rules.pop(rule_id, None) is not None

    def enable_rule(self, rule_id: str) -> bool:
        rule = self._rules.get(rule_id)
        if rule:
            rule.enabled = True
            return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        rule = self._rules.get(rule_id)
        if rule:
            rule.enabled = False
            return True
        return False

    def list_rules(self) -> list[dict[str, Any]]:
        return [
            {
                "id": r.id, "name": r.name, "type": r.rule_type.value,
                "severity": r.severity.value, "enabled": r.enabled,
                "description": r.description, "params": r.params,
            }
            for r in self._rules.values()
        ]

    # ----------------------------------------------------------
    # 事件检测
    # ----------------------------------------------------------

    def ingest_event(self, event: dict[str, Any]) -> list[AnomalyAlert]:
        """
        摄入审计事件并检测异常

        event 格式:
        {
            "operator_id": "user_123",
            "action_type": "delete_agent",
            "target_id": "agent_456",
            "timestamp": "2025-01-15T03:30:00Z",
            "result": "failure",
            "operator_ip": "192.168.1.100",
        }
        """
        alerts = []
        for rule in self._rules.values():
            if not rule.enabled:
                continue

            # 冷却期检查
            if rule.last_triggered:
                elapsed = (datetime.now(timezone.utc) - rule.last_triggered).total_seconds()
                if elapsed < rule.cooldown_seconds:
                    continue

            alert = None
            if rule.rule_type == RuleType.UNUSUAL_TIME:
                alert = self._check_unusual_time(rule, event)
            elif rule.rule_type == RuleType.HIGH_FREQ_FAILURE:
                alert = self._check_high_freq_failure(rule, event)
            elif rule.rule_type == RuleType.PERMISSION_DENIED:
                alert = self._check_permission_denied(rule, event)
            elif rule.rule_type == RuleType.BATCH_DELETE:
                alert = self._check_batch_delete(rule, event)

            if alert:
                alerts.append(alert)
                self._alerts.append(alert)
                rule.last_triggered = datetime.now(timezone.utc)
                self._stats[rule.rule_type.value] += 1
                logger.warning(
                    f"Anomaly detected: {rule.name} | "
                    f"Operator: {event.get('operator_id')} | "
                    f"Severity: {rule.severity.value}"
                )

        return alerts

    def _check_unusual_time(self, rule: DetectionRule, event: dict) -> Optional[AnomalyAlert]:
        """检测异常时间段操作"""
        ts_str = event.get("timestamp", "")
        if not ts_str:
            return None
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            hour = ts.hour
            start = rule.params.get("start_hour", 0)
            end = rule.params.get("end_hour", 6)

            if start <= hour < end:
                return AnomalyAlert(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    rule_type=rule.rule_type.value,
                    severity=rule.severity.value,
                    operator_id=event.get("operator_id", ""),
                    target_id=event.get("target_id", ""),
                    description=f"在异常时间段 ({start}:00-{end}:00) 执行操作: {event.get('action_type')}",
                    evidence={"hour": hour, "action": event.get("action_type")},
                    detected_at=datetime.now(timezone.utc),
                )
        except (ValueError, TypeError):
            pass
        return None

    def _check_high_freq_failure(self, rule: DetectionRule, event: dict) -> Optional[AnomalyAlert]:
        """检测高频失败"""
        if event.get("result") != "failure":
            return None

        operator = event.get("operator_id", "")
        window = rule.params.get("window_seconds", 60)
        threshold = rule.params.get("threshold", 5)

        key = f"failure:{operator}"
        now = time.time()

        self._sliding_windows[key].append(now)
        # 清除过期记录
        while self._sliding_windows[key] and self._sliding_windows[key][0] < now - window:
            self._sliding_windows[key].popleft()

        count = len(self._sliding_windows[key])
        if count >= threshold:
            self._sliding_windows[key].clear()
            return AnomalyAlert(
                rule_id=rule.id,
                rule_name=rule.name,
                rule_type=rule.rule_type.value,
                severity=rule.severity.value,
                operator_id=operator,
                target_id=event.get("target_id", ""),
                description=f"{window}秒内失败 {count} 次 (阈值: {threshold})",
                evidence={
                    "failure_count": count,
                    "window_seconds": window,
                    "action": event.get("action_type"),
                },
                detected_at=datetime.now(timezone.utc),
            )
        return None

    def _check_permission_denied(self, rule: DetectionRule, event: dict) -> Optional[AnomalyAlert]:
        """检测权限越界"""
        action = event.get("action_type", "")
        denied = rule.params.get("denied_actions", [])

        if action in denied:
            return AnomalyAlert(
                rule_id=rule.id,
                rule_name=rule.name,
                rule_type=rule.rule_type.value,
                severity=rule.severity.value,
                operator_id=event.get("operator_id", ""),
                target_id=event.get("target_id", ""),
                description=f"尝试执行高危操作: {action}",
                evidence={"action": action, "denied_actions": denied},
                detected_at=datetime.now(timezone.utc),
            )
        return None

    def _check_batch_delete(self, rule: DetectionRule, event: dict) -> Optional[AnomalyAlert]:
        """检测批量删除"""
        action = event.get("action_type", "")
        if "delete" not in action.lower():
            return None

        operator = event.get("operator_id", "")
        window = rule.params.get("window_seconds", 300)
        threshold = rule.params.get("threshold", 10)

        key = f"delete:{operator}"
        now = time.time()

        self._sliding_windows[key].append(now)
        while self._sliding_windows[key] and self._sliding_windows[key][0] < now - window:
            self._sliding_windows[key].popleft()

        count = len(self._sliding_windows[key])
        if count >= threshold:
            self._sliding_windows[key].clear()
            return AnomalyAlert(
                rule_id=rule.id,
                rule_name=rule.name,
                rule_type=rule.rule_type.value,
                severity=rule.severity.value,
                operator_id=operator,
                target_id=event.get("target_id", ""),
                description=f"{window}秒内批量删除 {count} 次 (阈值: {threshold})",
                evidence={"delete_count": count, "window_seconds": window},
                detected_at=datetime.now(timezone.utc),
            )
        return None

    # ----------------------------------------------------------
    # 查询
    # ----------------------------------------------------------

    def get_alerts(
        self,
        severity: Optional[str] = None,
        rule_type: Optional[str] = None,
        operator_id: Optional[str] = None,
        resolved: Optional[bool] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        alerts = self._alerts
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        if rule_type:
            alerts = [a for a in alerts if a.rule_type == rule_type]
        if operator_id:
            alerts = [a for a in alerts if a.operator_id == operator_id]
        if resolved is not None:
            alerts = [a for a in alerts if a.resolved == resolved]
        return [
            {
                "id": a.id, "rule_name": a.rule_name, "rule_type": a.rule_type,
                "severity": a.severity, "operator_id": a.operator_id,
                "target_id": a.target_id, "description": a.description,
                "evidence": a.evidence,
                "detected_at": a.detected_at.isoformat() if a.detected_at else None,
                "resolved": a.resolved,
            }
            for a in alerts[-limit:]
        ]

    def resolve_alert(self, alert_id: str) -> bool:
        for a in self._alerts:
            if a.id == alert_id:
                a.resolved = True
                a.resolved_at = datetime.now(timezone.utc)
                return True
        return False

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_rules": len(self._rules),
            "enabled_rules": sum(1 for r in self._rules.values() if r.enabled),
            "total_alerts": len(self._alerts),
            "unresolved_alerts": sum(1 for a in self._alerts if not a.resolved),
            "rule_type_stats": dict(self._stats),
        }
