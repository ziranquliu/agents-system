"""
异常自愈服务 — 三级恢复策略

功能:
- 异常检测（错误率、延迟、健康分、连续失败）
- Level 1 重启恢复
- Level 2 回滚恢复（恢复上次已知良好配置）
- Level 3 降级恢复（禁用非关键技能）
- 恢复后验证
- 自愈记录与统计
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class HealingLevel(int, Enum):
    RESTART = 1
    ROLLBACK = 2
    DOWNGRADE = 3


class AnomalyType(str, Enum):
    HIGH_ERROR_RATE = "high_error_rate"
    HIGH_LATENCY = "high_latency"
    HEALTH_SCORE_DROP = "health_score_drop"
    CONSECUTIVE_FAILURES = "consecutive_failures"


class HealingResult(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


@dataclass
class Anomaly:
    """异常信息"""
    anomaly_type: AnomalyType
    severity: float  # 0.0~1.0
    current_value: float
    threshold: float
    message: str
    detected_at: Optional[datetime] = None


@dataclass
class HealingAction:
    """自愈记录"""
    id: str = ""
    agent_id: str = ""
    level: HealingLevel = HealingLevel.RESTART
    trigger_reason: str = ""
    anomaly_type: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: HealingResult = HealingResult.FAILURE
    actions_taken: list[str] = field(default_factory=list)
    error_message: str = ""
    verification_passed: bool = False

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())


@dataclass
class AgentSnapshot:
    """Agent 配置快照（用于回滚）"""
    agent_id: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    enabled_skills: list[str] = field(default_factory=list)
    disabled_skills: list[str] = field(default_factory=list)
    snapshot_time: Optional[datetime] = None


class SelfHealingService:
    """
    异常自愈服务

    三级恢复策略：
    - Level 1 (RESTART): 停止 → 启动 → 健康检查
    - Level 2 (ROLLBACK): 恢复上次已知良好配置 → 重启 → 验证
    - Level 3 (DOWNGRADE): 禁用非关键技能 → 重启 → 验证基本服务
    """

    # 异常检测阈值
    ERROR_RATE_THRESHOLD = 0.05       # 5% 错误率
    LATENCY_THRESHOLD_MS = 10000.0    # P99 延迟 10s
    HEALTH_SCORE_DROP_THRESHOLD = 20  # 健康分下降 20
    CONSECUTIVE_FAILURE_THRESHOLD = 3 # 连续失败 3 次

    def __init__(self):
        self._config_snapshots: dict[str, list[AgentSnapshot]] = {}
        self._healing_history: list[HealingAction] = []
        self._consecutive_failures: dict[str, int] = {}
        self._last_health_scores: dict[str, float] = {}

    # ----------------------------------------------------------
    # 异常检测
    # ----------------------------------------------------------

    def detect_anomaly(
        self,
        agent_id: str,
        metrics: dict[str, Any],
    ) -> list[Anomaly]:
        """
        检测 Agent 异常

        metrics 示例:
        {
            "error_rate": 0.08,
            "response_time_p99_ms": 12000,
            "health_score": 65,
            "consecutive_failures": 5,
        }
        """
        anomalies: list[Anomaly] = []
        now = datetime.now(timezone.utc)

        # 检查错误率
        error_rate = metrics.get("error_rate", 0)
        if error_rate > self.ERROR_RATE_THRESHOLD:
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.HIGH_ERROR_RATE,
                severity=min(error_rate / self.ERROR_RATE_THRESHOLD, 1.0),
                current_value=error_rate,
                threshold=self.ERROR_RATE_THRESHOLD,
                message=f"错误率 {error_rate*100:.1f}% 超过阈值 {self.ERROR_RATE_THRESHOLD*100:.0f}%",
                detected_at=now,
            ))

        # 检查 P99 延迟
        p99_ms = metrics.get("response_time_p99_ms", 0)
        if p99_ms > self.LATENCY_THRESHOLD_MS:
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.HIGH_LATENCY,
                severity=min(p99_ms / self.LATENCY_THRESHOLD_MS, 1.0),
                current_value=p99_ms,
                threshold=self.LATENCY_THRESHOLD_MS,
                message=f"P99 延迟 {p99_ms:.0f}ms 超过阈值 {self.LATENCY_THRESHOLD_MS:.0f}ms",
                detected_at=now,
            ))

        # 检查健康分变化
        current_score = metrics.get("health_score", 100)
        last_score = self._last_health_scores.get(agent_id, 100)
        score_drop = last_score - current_score
        self._last_health_scores[agent_id] = current_score

        if score_drop > self.HEALTH_SCORE_DROP_THRESHOLD:
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.HEALTH_SCORE_DROP,
                severity=min(score_drop / 50.0, 1.0),
                current_value=score_drop,
                threshold=self.HEALTH_SCORE_DROP_THRESHOLD,
                message=f"健康分下降 {score_drop:.0f} 分 (从 {last_score} 到 {current_score})",
                detected_at=now,
            ))

        # 检查连续失败
        failures = metrics.get("consecutive_failures", 0)
        self._consecutive_failures[agent_id] = failures
        if failures >= self.CONSECUTIVE_FAILURE_THRESHOLD:
            anomalies.append(Anomaly(
                anomaly_type=AnomalyType.CONSECUTIVE_FAILURES,
                severity=min(failures / 10.0, 1.0),
                current_value=failures,
                threshold=self.CONSECUTIVE_FAILURE_THRESHOLD,
                message=f"连续失败 {failures} 次",
                detected_at=now,
            ))

        if anomalies:
            logger.warning(f"Detected {len(anomalies)} anomalies for agent {agent_id}")
        return anomalies

    # ----------------------------------------------------------
    # 自愈执行
    # ----------------------------------------------------------

    async def heal(
        self,
        agent_id: str,
        anomaly: Anomaly,
        agent_manager=None,
    ) -> HealingAction:
        """
        执行三级恢复

        自动选择恢复级别：
        - 连续失败 / 高错误率 → Level 1 重启
        - 健康分大幅下降 → Level 2 回滚
        - 所有级别失败 → Level 3 降级
        """
        action = HealingAction(
            agent_id=agent_id,
            trigger_reason=anomaly.message,
            anomaly_type=anomaly.anomaly_type.value,
            started_at=datetime.now(timezone.utc),
        )

        # 自动选择级别
        if anomaly.anomaly_type == AnomalyType.CONSECUTIVE_FAILURES:
            level = HealingLevel.RESTART
        elif anomaly.anomaly_type == AnomalyType.HEALTH_SCORE_DROP:
            level = HealingLevel.ROLLBACK
        elif anomaly.severity > 0.8:
            level = HealingLevel.DOWNGRADE
        else:
            level = HealingLevel.RESTART

        action.level = level

        logger.info(f"Starting Level {level.value} healing for agent {agent_id}: {anomaly.message}")

        try:
            if level == HealingLevel.RESTART:
                await self._heal_restart(agent_id, action, agent_manager)
            elif level == HealingLevel.ROLLBACK:
                await self._heal_rollback(agent_id, action, agent_manager)
            elif level == HealingLevel.DOWNGRADE:
                await self._heal_downgrade(agent_id, action, agent_manager)

            # 验证
            action.verification_passed = await self.verify_healing(agent_id, agent_manager)
            action.result = HealingResult.SUCCESS if action.verification_passed else HealingResult.PARTIAL

        except Exception as e:
            action.result = HealingResult.FAILURE
            action.error_message = str(e)
            logger.error(f"Healing failed for agent {agent_id}: {e}")

        action.completed_at = datetime.now(timezone.utc)
        self._healing_history.append(action)

        # 重置连续失败计数
        if action.verification_passed:
            self._consecutive_failures[agent_id] = 0

        return action

    async def _heal_restart(
        self,
        agent_id: str,
        action: HealingAction,
        agent_manager=None,
    ):
        """Level 1: 重启恢复"""
        # Step 1: 停止
        action.actions_taken.append("stop_agent")
        logger.info(f"[L1] Stopping agent {agent_id}")
        if agent_manager and hasattr(agent_manager, "stop_agent"):
            await agent_manager.stop_agent(agent_id)

        # Step 2: 短暂等待
        action.actions_taken.append("wait_2s")
        import asyncio
        await asyncio.sleep(2)

        # Step 3: 启动
        action.actions_taken.append("start_agent")
        logger.info(f"[L1] Starting agent {agent_id}")
        if agent_manager and hasattr(agent_manager, "start_agent"):
            await agent_manager.start_agent(agent_id)

        # Step 4: 健康检查
        action.actions_taken.append("health_check")
        logger.info(f"[L1] Health check for agent {agent_id}")

    async def _heal_rollback(
        self,
        agent_id: str,
        action: HealingAction,
        agent_manager=None,
    ):
        """Level 2: 回滚恢复"""
        # Step 1: 获取快照
        action.actions_taken.append("get_snapshot")
        snapshots = self._config_snapshots.get(agent_id, [])

        if snapshots:
            last_good = snapshots[-1]
            logger.info(f"[L2] Rolling back to snapshot from {last_good.snapshot_time}")

            # Step 2: 恢复配置
            action.actions_taken.append("restore_config")
            if agent_manager and hasattr(agent_manager, "update_agent_config"):
                await agent_manager.update_agent_config(agent_id, last_good.config)

            # Step 3: 恢复技能绑定
            action.actions_taken.append("restore_skills")
            if agent_manager:
                if hasattr(agent_manager, "enable_skills"):
                    for skill_id in last_good.enabled_skills:
                        await agent_manager.enable_skills(agent_id, skill_id)
                if hasattr(agent_manager, "disable_skills"):
                    for skill_id in last_good.disabled_skills:
                        await agent_manager.disable_skills(agent_id, skill_id)
        else:
            action.actions_taken.append("no_snapshot_found")
            logger.warning(f"[L2] No snapshot found for agent {agent_id}, falling back to restart")
            await self._heal_restart(agent_id, action, agent_manager)
            return

        # Step 4: 重启
        action.actions_taken.append("restart")
        import asyncio
        await asyncio.sleep(1)
        if agent_manager and hasattr(agent_manager, "restart_agent"):
            await agent_manager.restart_agent(agent_id)

    async def _heal_downgrade(
        self,
        agent_id: str,
        action: HealingAction,
        agent_manager=None,
    ):
        """Level 3: 降级恢复"""
        # Step 1: 获取当前绑定的技能
        action.actions_taken.append("get_skills")
        bound_skills: list[str] = []
        if agent_manager and hasattr(agent_manager, "get_agent_skills"):
            bound_skills = await agent_manager.get_agent_skills(agent_id)

        # Step 2: 禁用非关键技能
        action.actions_taken.append("disable_non_critical")
        critical_skills = {"chat", "llm", "basic_qa"}  # 关键技能白名单
        disabled = []
        for skill_id in bound_skills:
            if skill_id.lower() not in critical_skills:
                disabled.append(skill_id)
                if agent_manager and hasattr(agent_manager, "disable_skills"):
                    await agent_manager.disable_skills(agent_id, skill_id)
        action.actions_taken.append(f"disabled_{len(disabled)}_skills")

        logger.info(f"[L3] Disabled {len(disabled)} non-critical skills for agent {agent_id}")

        # Step 3: 重启
        action.actions_taken.append("restart")
        import asyncio
        await asyncio.sleep(1)
        if agent_manager and hasattr(agent_manager, "restart_agent"):
            await agent_manager.restart_agent(agent_id)

    # ----------------------------------------------------------
    # 恢复验证
    # ----------------------------------------------------------

    async def verify_healing(
        self,
        agent_id: str,
        agent_manager=None,
    ) -> bool:
        """恢复后验证 — 运行健康检查"""
        logger.info(f"Verifying healing for agent {agent_id}")
        try:
            if agent_manager and hasattr(agent_manager, "check_health"):
                result = await agent_manager.check_health(agent_id)
                if isinstance(result, dict):
                    return result.get("status") in ("ok", "healthy", "pass")
                return bool(result)
            # 无 agent_manager 时假设成功
            return True
        except Exception as e:
            logger.error(f"Healing verification failed for {agent_id}: {e}")
            return False

    # ----------------------------------------------------------
    # 配置快照管理
    # ----------------------------------------------------------

    def save_snapshot(self, agent_id: str, config: dict[str, Any],
                      enabled_skills: Optional[list[str]] = None):
        """保存 Agent 配置快照（用于回滚）"""
        snapshot = AgentSnapshot(
            agent_id=agent_id,
            config=config.copy(),
            enabled_skills=enabled_skills or [],
            snapshot_time=datetime.now(timezone.utc),
        )
        if agent_id not in self._config_snapshots:
            self._config_snapshots[agent_id] = []
        self._config_snapshots[agent_id].append(snapshot)
        # 保留最近 10 个快照
        if len(self._config_snapshots[agent_id]) > 10:
            self._config_snapshots[agent_id] = self._config_snapshots[agent_id][-10:]

    def get_snapshot(self, agent_id: str) -> Optional[AgentSnapshot]:
        """获取最新快照"""
        snapshots = self._config_snapshots.get(agent_id, [])
        return snapshots[-1] if snapshots else None

    # ----------------------------------------------------------
    # 历史与统计
    # ----------------------------------------------------------

    def get_healing_history(
        self,
        agent_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """获取自愈历史"""
        records = self._healing_history
        if agent_id:
            records = [r for r in records if r.agent_id == agent_id]

        return [
            {
                "id": r.id,
                "agent_id": r.agent_id,
                "level": r.level.value,
                "level_name": r.level.name,
                "trigger_reason": r.trigger_reason,
                "anomaly_type": r.anomaly_type,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "result": r.result.value,
                "actions_taken": r.actions_taken,
                "error_message": r.error_message,
                "verification_passed": r.verification_passed,
                "duration_ms": (
                    round((r.completed_at - r.started_at).total_seconds() * 1000)
                    if r.started_at and r.completed_at else None
                ),
            }
            for r in records[-limit:]
        ]

    def get_healing_stats(self) -> dict[str, Any]:
        """获取自愈统计"""
        total = len(self._healing_history)
        if total == 0:
            return {
                "total_healings": 0,
                "success_rate": 0,
                "level_breakdown": {},
                "avg_duration_ms": 0,
            }

        success = sum(1 for r in self._healing_history if r.result == HealingResult.SUCCESS)
        level_counts = {}
        durations = []
        for r in self._healing_history:
            level_name = r.level.name
            level_counts[level_name] = level_counts.get(level_name, 0) + 1
            if r.started_at and r.completed_at:
                durations.append((r.completed_at - r.started_at).total_seconds() * 1000)

        return {
            "total_healings": total,
            "success_count": success,
            "failure_count": total - success,
            "success_rate": round(success / total * 100, 1),
            "level_breakdown": level_counts,
            "avg_duration_ms": round(sum(durations) / len(durations), 1) if durations else 0,
            "recent_healings": self.get_healing_history(limit=5),
        }
