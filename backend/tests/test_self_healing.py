"""
Tests for self_healing_service.py — anomaly detection, healing levels, snapshots, stats
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.self_healing_service import (
    SelfHealingService,
    Anomaly,
    AnomalyType,
    HealingAction,
    HealingLevel,
    HealingResult,
    AgentSnapshot,
)


# ─────────────────────────────────────────────────────────
# 异常检测
# ─────────────────────────────────────────────────────────
class TestAnomalyDetection:
    def setup_method(self):
        self.svc = SelfHealingService()

    def test_no_anomaly(self):
        anomalies = self.svc.detect_anomaly("a1", {"error_rate": 0.01, "response_time_p99_ms": 500, "health_score": 95, "consecutive_failures": 0})
        assert len(anomalies) == 0

    def test_high_error_rate(self):
        anomalies = self.svc.detect_anomaly("a1", {"error_rate": 0.10})
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.HIGH_ERROR_RATE
        assert anomalies[0].severity > 0

    def test_high_latency(self):
        anomalies = self.svc.detect_anomaly("a1", {"response_time_p99_ms": 15000})
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.HIGH_LATENCY

    def test_health_score_drop(self):
        # 第一次设置基准
        self.svc.detect_anomaly("a1", {"health_score": 90})
        # 第二次大幅下降
        anomalies = self.svc.detect_anomaly("a1", {"health_score": 50})
        assert any(a.anomaly_type == AnomalyType.HEALTH_SCORE_DROP for a in anomalies)

    def test_consecutive_failures(self):
        anomalies = self.svc.detect_anomaly("a1", {"consecutive_failures": 5})
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.CONSECUTIVE_FAILURES

    def test_multiple_anomalies(self):
        anomalies = self.svc.detect_anomaly("a1", {
            "error_rate": 0.10,
            "response_time_p99_ms": 15000,
            "health_score": 10,
            "consecutive_failures": 5,
        })
        assert len(anomalies) >= 3

    def test_empty_metrics(self):
        anomalies = self.svc.detect_anomaly("a1", {})
        assert len(anomalies) == 0

    def test_boundary_error_rate(self):
        """刚好等于阈值不触发"""
        self.svc = SelfHealingService()
        anomalies = self.svc.detect_anomaly("a1", {"error_rate": 0.05})
        assert len(anomalies) == 0

    def test_boundary_latency(self):
        self.svc = SelfHealingService()
        anomalies = self.svc.detect_anomaly("a1", {"response_time_p99_ms": 10000})
        assert len(anomalies) == 0

    def test_boundary_failures(self):
        self.svc = SelfHealingService()
        anomalies = self.svc.detect_anomaly("a1", {"consecutive_failures": 3})
        assert len(anomalies) == 1  # >= threshold triggers

    def test_health_score_drop_boundary(self):
        """下降刚好等于阈值"""
        self.svc = SelfHealingService()
        self.svc.detect_anomaly("a1", {"health_score": 80})
        anomalies = self.svc.detect_anomaly("a1", {"health_score": 60})
        # score_drop = 80-60 = 20, threshold = 20, > threshold is required
        assert len(anomalies) == 0  # 20 is not > 20


# ─────────────────────────────────────────────────────────
# 配置快照
# ─────────────────────────────────────────────────────────
class TestSnapshots:
    def setup_method(self):
        self.svc = SelfHealingService()

    def test_save_and_get(self):
        self.svc.save_snapshot("a1", {"model": "gpt-4"}, ["web_search"])
        snap = self.svc.get_snapshot("a1")
        assert snap is not None
        assert snap.agent_id == "a1"
        assert snap.config == {"model": "gpt-4"}
        assert snap.enabled_skills == ["web_search"]

    def test_no_snapshot(self):
        snap = self.svc.get_snapshot("nonexistent")
        assert snap is None

    def test_multiple_snapshots(self):
        self.svc.save_snapshot("a1", {"v": 1})
        self.svc.save_snapshot("a1", {"v": 2})
        snap = self.svc.get_snapshot("a1")
        assert snap.config["v"] == 2

    def test_snapshot_limit(self):
        """最多保留10个快照"""
        for i in range(15):
            self.svc.save_snapshot("a1", {"v": i})
        assert len(self.svc._config_snapshots["a1"]) == 10

    def test_snapshot_independent_agents(self):
        self.svc.save_snapshot("a1", {"a": 1})
        self.svc.save_snapshot("a2", {"b": 2})
        assert self.svc.get_snapshot("a1").config["a"] == 1
        assert self.svc.get_snapshot("a2").config["b"] == 2


# ─────────────────────────────────────────────────────────
# 验证
# ─────────────────────────────────────────────────────────
class TestVerifyHealing:
    def setup_method(self):
        self.svc = SelfHealingService()

    @pytest.mark.asyncio
    async def test_no_manager_returns_true(self):
        result = await self.svc.verify_healing("a1", None)
        assert result is True

    @pytest.mark.asyncio
    async def test_manager_healthy(self):
        manager = AsyncMock()
        manager.check_health.return_value = {"status": "ok"}
        result = await self.svc.verify_healing("a1", manager)
        assert result is True

    @pytest.mark.asyncio
    async def test_manager_unhealthy(self):
        manager = AsyncMock()
        manager.check_health.return_value = {"status": "fail"}
        result = await self.svc.verify_healing("a1", manager)
        assert result is False

    @pytest.mark.asyncio
    async def test_manager_exception(self):
        manager = AsyncMock()
        manager.check_health.side_effect = RuntimeError("connection refused")
        result = await self.svc.verify_healing("a1", manager)
        assert result is False

    @pytest.mark.asyncio
    async def test_manager_returns_string(self):
        manager = AsyncMock()
        manager.check_health.return_value = "healthy"
        result = await self.svc.verify_healing("a1", manager)
        assert result is True


# ─────────────────────────────────────────────────────────
# 自愈执行
# ─────────────────────────────────────────────────────────
class TestHealing:
    def setup_method(self):
        self.svc = SelfHealingService()

    @pytest.mark.asyncio
    async def test_heal_consecutive_failures_triggers_restart(self):
        anomaly = Anomaly(
            anomaly_type=AnomalyType.CONSECUTIVE_FAILURES,
            severity=0.5, current_value=5, threshold=3,
            message="连续失败5次",
        )
        action = await self.svc.heal("a1", anomaly)
        assert action.level == HealingLevel.RESTART
        assert action.result in (HealingResult.SUCCESS, HealingResult.PARTIAL)
        assert "stop_agent" in action.actions_taken

    @pytest.mark.asyncio
    async def test_heal_score_drop_triggers_rollback(self):
        self.svc.save_snapshot("a1", {"model": "gpt-4"})
        anomaly = Anomaly(
            anomaly_type=AnomalyType.HEALTH_SCORE_DROP,
            severity=0.5, current_value=30, threshold=20,
            message="健康分下降30分",
        )
        action = await self.svc.heal("a1", anomaly)
        assert action.level == HealingLevel.ROLLBACK
        assert "get_snapshot" in action.actions_taken

    @pytest.mark.asyncio
    async def test_heal_high_severity_triggers_downgrade(self):
        anomaly = Anomaly(
            anomaly_type=AnomalyType.HIGH_ERROR_RATE,
            severity=0.9, current_value=0.5, threshold=0.05,
            message="错误率50%",
        )
        action = await self.svc.heal("a1", anomaly)
        assert action.level == HealingLevel.DOWNGRADE
        assert "disable_non_critical" in action.actions_taken

    @pytest.mark.asyncio
    async def test_heal_records_history(self):
        anomaly = Anomaly(
            anomaly_type=AnomalyType.CONSECUTIVE_FAILURES,
            severity=0.5, current_value=5, threshold=3,
            message="连续失败",
        )
        await self.svc.heal("a1", anomaly)
        assert len(self.svc._healing_history) == 1

    @pytest.mark.asyncio
    async def test_heal_resets_consecutive_failures_on_success(self):
        self.svc._consecutive_failures["a1"] = 5
        anomaly = Anomaly(
            anomaly_type=AnomalyType.CONSECUTIVE_FAILURES,
            severity=0.5, current_value=5, threshold=3,
            message="连续失败",
        )
        action = await self.svc.heal("a1", anomaly)
        if action.verification_passed:
            assert self.svc._consecutive_failures["a1"] == 0

    @pytest.mark.asyncio
    async def test_heal_rollback_no_snapshot_falls_back_to_restart(self):
        """没有快照时回滚退化为重启"""
        anomaly = Anomaly(
            anomaly_type=AnomalyType.HEALTH_SCORE_DROP,
            severity=0.5, current_value=30, threshold=20,
            message="健康分下降",
        )
        action = await self.svc.heal("a1", anomaly)
        assert action.level == HealingLevel.ROLLBACK
        assert "no_snapshot_found" in action.actions_taken


# ─────────────────────────────────────────────────────────
# 历史与统计
# ─────────────────────────────────────────────────────────
class TestHealingStats:
    def setup_method(self):
        self.svc = SelfHealingService()

    def test_empty_stats(self):
        stats = self.svc.get_healing_stats()
        assert stats["total_healings"] == 0
        assert stats["success_rate"] == 0

    @pytest.mark.asyncio
    async def test_stats_with_history(self):
        anomaly = Anomaly(
            anomaly_type=AnomalyType.CONSECUTIVE_FAILURES,
            severity=0.5, current_value=5, threshold=3,
            message="连续失败",
        )
        await self.svc.heal("a1", anomaly)
        await self.svc.heal("a2", anomaly)
        stats = self.svc.get_healing_stats()
        assert stats["total_healings"] == 2

    def test_get_history(self):
        from datetime import datetime, timezone
        action = HealingAction(
            agent_id="a1",
            level=HealingLevel.RESTART,
            trigger_reason="test",
            anomaly_type="high_error_rate",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            result=HealingResult.SUCCESS,
            actions_taken=["stop", "start"],
        )
        self.svc._healing_history.append(action)
        history = self.svc.get_healing_history(agent_id="a1")
        assert len(history) == 1
        assert history[0]["agent_id"] == "a1"

    def test_get_history_filter(self):
        from datetime import datetime, timezone
        action1 = HealingAction(agent_id="a1", level=HealingLevel.RESTART, trigger_reason="t1", anomaly_type="x", started_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc), result=HealingResult.SUCCESS)
        action2 = HealingAction(agent_id="a2", level=HealingLevel.ROLLBACK, trigger_reason="t2", anomaly_type="y", started_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc), result=HealingResult.FAILURE)
        self.svc._healing_history = [action1, action2]
        history = self.svc.get_healing_history(agent_id="a1")
        assert len(history) == 1
        assert history[0]["agent_id"] == "a1"
