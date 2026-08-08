"""
Tests for ops_service.py — DeploymentService, AutoScalingService, LogService, MaintenanceService
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.models.ops import (
    AgentDeployment, AgentDeploymentStatus,
    ScalingPolicy, ScalingEvent, ScalingDirection, ScalingMetricType,
    LogEntry, LogCollectionConfig, LogLevel, LogSourceType,
    MaintenanceTask, MaintenanceExecution, MaintenanceType,
    SelfHealRecord, HealRule, HealLevel, HealStatus,
    OpsReport, ReportType,
)


# ─────────────────────────────────────────────────────────
# Enum 验证
# ─────────────────────────────────────────────────────────
class TestOpsModels:
    def test_deployment_status_values(self):
        assert AgentDeploymentStatus.PENDING == "pending"
        assert AgentDeploymentStatus.HEALTHY == "healthy"
        assert AgentDeploymentStatus.FAILED == "failed"

    def test_scaling_direction(self):
        assert ScalingDirection.SCALE_OUT == "scale_out"
        assert ScalingDirection.SCALE_IN == "scale_in"

    def test_scaling_metric(self):
        assert ScalingMetricType.CPU_USAGE == "cpu_usage"
        assert ScalingMetricType.MEMORY_USAGE == "memory_usage"

    def test_log_level(self):
        assert LogLevel.DEBUG == "DEBUG"
        assert LogLevel.ERROR == "ERROR"

    def test_maintenance_type(self):
        assert MaintenanceType.SESSION_CLEANUP == "session_cleanup"
        assert MaintenanceType.INDEX_REBUILD == "index_rebuild"

    def test_heal_level(self):
        assert HealLevel.LEVEL_1_RESTART == "restart"
        assert HealLevel.LEVEL_3_DEGRADE == "degrade"

    def test_heal_status(self):
        assert HealStatus.DETECTED == "detected"
        assert HealStatus.SUCCESS == "success"

    def test_report_type(self):
        assert ReportType.DAILY == "daily"


# ─────────────────────────────────────────────────────────
# DeploymentService (mocked session)
# ─────────────────────────────────────────────────────────
class TestDeploymentService:
    @pytest.mark.asyncio
    async def test_create_deployment(self):
        from app.services.ops_service import DeploymentService
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        dep = await DeploymentService.create_deployment(
            session,
            agent_name="test-agent",
            template_yaml="apiVersion: v1\nkind: Pod",
            version="1.0.0",
            parameters={"replicas": 2},
        )
        assert dep.agent_name == "test-agent"
        assert dep.version == "1.0.0"
        assert dep.status == AgentDeploymentStatus.PENDING
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_deployment_not_found(self):
        from app.services.ops_service import DeploymentService
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await DeploymentService.get_deployment(session, "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_rollback_deployment(self):
        from app.services.ops_service import DeploymentService
        session = AsyncMock()
        dep = MagicMock()
        dep.status = AgentDeploymentStatus.HEALTHY
        dep.rolled_back_at = None
        dep.updated_at = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = dep
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()

        result = await DeploymentService.rollback_deployment(session, "d1")
        assert result.status == AgentDeploymentStatus.ROLLED_BACK

    @pytest.mark.asyncio
    async def test_delete_deployment(self):
        from app.services.ops_service import DeploymentService
        session = AsyncMock()
        dep = MagicMock()
        dep.is_active = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = dep
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()

        result = await DeploymentService.delete_deployment(session, "d1")
        assert result is True
        assert dep.is_active is False

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self):
        from app.services.ops_service import DeploymentService
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await DeploymentService.delete_deployment(session, "nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_update_status_healthy_sets_deployed_at(self):
        from app.services.ops_service import DeploymentService
        session = AsyncMock()
        dep = MagicMock()
        dep.status = AgentDeploymentStatus.PENDING
        dep.deployed_at = None
        dep.updated_at = None
        dep.error_message = None
        dep.health_score = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = dep
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()

        result = await DeploymentService.update_status(
            session, "d1", AgentDeploymentStatus.HEALTHY, health_score=95.0
        )
        assert result.deployed_at is not None
        assert result.health_score == 95.0

    @pytest.mark.asyncio
    async def test_list_deployments_empty(self):
        from app.services.ops_service import DeploymentService
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_count = MagicMock()
        mock_count.scalar.return_value = 0
        session.execute = AsyncMock(side_effect=[mock_result, mock_count])

        deps, count = await DeploymentService.list_deployments(session)
        assert deps == []
        assert count == 0


# ─────────────────────────────────────────────────────────
# LogService
# ─────────────────────────────────────────────────────────
class TestLogService:
    @pytest.mark.asyncio
    async def test_write_log(self):
        from app.services.ops_service import LogService
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        entry = await LogService.ingest_log(
            session,
            level=LogLevel.INFO,
            logger_name="test",
            message="Test log message",
            source_type=LogSourceType.AGENT,
            source_id="agent-1",
        )
        assert entry.source_id == "agent-1"
        assert entry.level == LogLevel.INFO
        assert entry.message == "Test log message"
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_logs_empty(self):
        from app.services.ops_service import LogService
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_count = MagicMock()
        mock_count.scalar.return_value = 0
        session.execute = AsyncMock(side_effect=[mock_result, mock_count])

        entries, total = await LogService.search_logs(session, agent_id="agent-1")
        assert entries == []
        assert total == 0


# ─────────────────────────────────────────────────────────
# MaintenanceService
# ─────────────────────────────────────────────────────────
class TestMaintenanceService:
    @pytest.mark.asyncio
    async def test_create_task(self):
        from app.services.ops_service import MaintenanceService
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        task = await MaintenanceService.create_task(
            session,
            name="Daily Cleanup",
            task_type=MaintenanceType.SESSION_CLEANUP,
            cron_expression="0 2 * * *",
        )
        assert task.name == "Daily Cleanup"
        assert task.task_type == MaintenanceType.SESSION_CLEANUP
        assert task.cron_expression == "0 2 * * *"
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_tasks_empty(self):
        from app.services.ops_service import MaintenanceService
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_count = MagicMock()
        mock_count.scalar.return_value = 0
        session.execute = AsyncMock(side_effect=[mock_result, mock_count])

        tasks, count = await MaintenanceService.list_tasks(session)
        assert tasks == []
        assert count == 0


# ─────────────────────────────────────────────────────────
# AutoScalingService
# ─────────────────────────────────────────────────────────
class TestAutoScalingService:
    @pytest.mark.asyncio
    async def test_get_policy_not_found(self):
        from app.services.ops_service import AutoScalingService
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await AutoScalingService.get_policy(session, "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_create_policy(self):
        from app.services.ops_service import AutoScalingService
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        # upsert_policy expects no existing → creates new
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        policy = await AutoScalingService.upsert_policy(
            session,
            agent_id="agent-1",
            agent_name="test-agent",
            metric_type=ScalingMetricType.CPU_USAGE,
            scale_out_threshold=80.0,
            scale_in_threshold=30.0,
        )
        assert policy.agent_id == "agent-1"
        assert policy.metric_type == ScalingMetricType.CPU_USAGE
        assert policy.scale_out_threshold == 80.0
        session.add.assert_called_once()


# ─────────────────────────────────────────────────────────
# HealRuleService
# ─────────────────────────────────────────────────────────
class TestHealRuleService:
    @pytest.mark.asyncio
    async def test_create_rule(self):
        from app.services.ops_service import SelfHealService
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        rule = await SelfHealService.create_rule(
            session,
            agent_id="agent-1",
            anomaly_type="high_error_rate",
            heal_level=HealLevel.LEVEL_1_RESTART,
            error_rate_threshold=0.05,
        )
        assert rule.agent_id == "agent-1"
        assert rule.anomaly_type == "high_error_rate"
        assert rule.heal_level == HealLevel.LEVEL_1_RESTART
        assert rule.error_rate_threshold == 0.05
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_rules_empty(self):
        from app.services.ops_service import SelfHealService
        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_count = MagicMock()
        mock_count.scalar.return_value = 0
        session.execute = AsyncMock(side_effect=[mock_result, mock_count])

        rules, count = await SelfHealService.list_rules(session, agent_id="agent-1")
        assert rules == []
        assert count == 0
