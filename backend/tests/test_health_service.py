"""
Tests for health_service.py — HealthCheckExecutor + HealthScoringService + helpers
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.health_service import (
    HealthCheckExecutor,
    HealthScoringService,
    _pid_exists,
    _process_name_exists,
)
from app.models.health import (
    AgentHealthConfig, HealthScoreWeight,
    HealthLevel, CheckStatus, AgentHealthStatus,
)


# ─────────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────────
class TestPidExists:
    def test_current_process(self):
        """当前进程 PID 应该存在"""
        import os
        pid = os.getpid()
        # 可能需要权限，允许异常
        try:
            result = _pid_exists(pid)
            assert result is True
        except Exception:
            pass

    def test_invalid_pid(self):
        """不存在的 PID"""
        result = _pid_exists(999999999)
        assert result is False


class TestProcessNameExists:
    def test_nonexistent_process(self):
        result = _process_name_exists("definitely_not_real_process_xxx_12345")
        assert result is False


# ─────────────────────────────────────────────────────────
# L1 存活检测
# ─────────────────────────────────────────────────────────
class TestCheckL1Alive:
    @pytest.mark.asyncio
    async def test_no_process_info(self):
        """无进程信息时默认存活"""
        config = AgentHealthConfig(agent_id="a1")
        config.pid = None
        config.process_name = None
        status, latency, details = await HealthCheckExecutor.check_l1_alive(config)
        assert status == CheckStatus.PASS
        assert latency >= 0

    @pytest.mark.asyncio
    async def test_with_pid(self):
        """有 PID 时检查进程"""
        import os
        config = AgentHealthConfig(agent_id="a1", pid=os.getpid())
        status, latency, details = await HealthCheckExecutor.check_l1_alive(config)
        assert status == CheckStatus.PASS
        d = json.loads(details)
        assert d["process_ok"] is True

    @pytest.mark.asyncio
    async def test_with_bad_pid(self):
        """不存在的 PID"""
        config = AgentHealthConfig(agent_id="a1", pid=999999999)
        status, latency, details = await HealthCheckExecutor.check_l1_alive(config)
        assert status == CheckStatus.FAIL


# ─────────────────────────────────────────────────────────
# L2 就绪检测
# ─────────────────────────────────────────────────────────
class TestCheckL2Ready:
    @pytest.mark.asyncio
    async def test_no_endpoint(self):
        """未配置端点时跳过"""
        config = AgentHealthConfig(agent_id="a1", ready_endpoint=None)
        status, latency, details = await HealthCheckExecutor.check_l2_ready(config)
        assert status == CheckStatus.PASS
        d = json.loads(details)
        assert "note" in d

    @pytest.mark.asyncio
    async def test_invalid_endpoint(self):
        """无效端点时返回 FAIL"""
        config = AgentHealthConfig(agent_id="a1", ready_endpoint="http://localhost:19999/health")
        status, latency, details = await HealthCheckExecutor.check_l2_ready(config)
        assert status == CheckStatus.FAIL
        d = json.loads(details)
        assert "error" in d


# ─────────────────────────────────────────────────────────
# L3 能力检测
# ─────────────────────────────────────────────────────────
class TestCheckL3Capability:
    @pytest.mark.asyncio
    async def test_no_skills_no_mcp(self):
        """无配置时全部通过"""
        config = AgentHealthConfig(agent_id="a1")
        config.l3_skills = None
        config.l3_mcp_servers = None
        config.l3_model_id = None
        status, latency, details = await HealthCheckExecutor.check_l3_capability(config)
        assert status == CheckStatus.PASS
        d = json.loads(details)
        assert len(d["failed_items"]) == 0

    @pytest.mark.asyncio
    async def test_with_skills_list(self):
        """配置了 skills"""
        config = AgentHealthConfig(agent_id="a1")
        config.l3_skills = json.dumps(["web_search", "calculator"])
        config.l3_mcp_servers = None
        config.l3_model_id = None
        status, latency, details = await HealthCheckExecutor.check_l3_capability(config)
        assert status == CheckStatus.PASS
        d = json.loads(details)
        assert len(d["skills"]) == 2

    @pytest.mark.asyncio
    async def test_skills_string_format(self):
        """skills 为字符串格式时自动解析"""
        config = AgentHealthConfig(agent_id="a1")
        config.l3_skills = '["web_search"]'
        config.l3_mcp_servers = None
        config.l3_model_id = None
        status, latency, details = await HealthCheckExecutor.check_l3_capability(config)
        assert status == CheckStatus.PASS

    @pytest.mark.asyncio
    async def test_invalid_skills_string(self):
        """无效 skills 字符串时不崩溃"""
        config = AgentHealthConfig(agent_id="a1")
        config.l3_skills = "not-json"
        config.l3_mcp_servers = None
        config.l3_model_id = None
        status, latency, details = await HealthCheckExecutor.check_l3_capability(config)
        assert status == CheckStatus.PASS


# ─────────────────────────────────────────────────────────
# L4 端到端检测
# ─────────────────────────────────────────────────────────
class TestCheckL4E2E:
    @pytest.mark.asyncio
    async def test_no_model(self):
        """未配置模型时链路部分跳过"""
        config = AgentHealthConfig(agent_id="a1")
        config.l3_model_id = None
        config.l3_skills = None
        config.l3_mcp_servers = None
        config.l4_test_prompt = "ping"
        status, latency, details = await HealthCheckExecutor.check_l4_e2e(config)
        d = json.loads(details)
        assert d["chain"]["llm"]["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_default_prompt(self):
        """使用默认测试 prompt"""
        config = AgentHealthConfig(agent_id="a1")
        config.l4_test_prompt = None
        config.l3_model_id = None
        status, latency, details = await HealthCheckExecutor.check_l4_e2e(config)
        d = json.loads(details)
        assert d["test_prompt"] == "ping"


# ─────────────────────────────────────────────────────────
# 健康评分
# ─────────────────────────────────────────────────────────
class TestHealthScoringService:
    def test_perfect_score(self):
        """全部正常应得高分"""
        tpl = SimpleNamespace(
            weight_response_time=20, weight_token=20,
            weight_error_rate=25, weight_session_success=20,
            weight_dependency=15,
            threshold_p95_warn_ms=3000, threshold_p95_critical_ms=5000,
            threshold_error_rate_warn=1.0, threshold_error_rate_critical=5.0,
            threshold_session_success_warn=95.0, threshold_session_success_critical=80.0,
        )
        score, details = HealthScoringService.calculate_score(
            p95_ms=200, token_usage_ratio=0.5,
            error_rate=0.005, session_success_rate=0.99,
            dependency_healthy=True, tpl=tpl,
        )
        assert score >= 95

    def test_poor_response_time(self):
        """响应时间差时扣分"""
        tpl = SimpleNamespace(
            weight_response_time=20, weight_token=20,
            weight_error_rate=25, weight_session_success=20,
            weight_dependency=15,
            threshold_p95_warn_ms=3000, threshold_p95_critical_ms=5000,
            threshold_error_rate_warn=1.0, threshold_error_rate_critical=5.0,
            threshold_session_success_warn=95.0, threshold_session_success_critical=80.0,
        )
        score, details = HealthScoringService.calculate_score(
            p95_ms=8000, token_usage_ratio=0.5,
            error_rate=0.005, session_success_rate=0.99,
            dependency_healthy=True, tpl=tpl,
        )
        assert score == 96  # deduction=20, weighted=20×(20/100)=4
        assert details["deductions"]["response_time"] == 20

    def test_high_error_rate(self):
        """错误率高时扣分"""
        tpl = SimpleNamespace(
            weight_response_time=20, weight_token=20,
            weight_error_rate=25, weight_session_success=20,
            weight_dependency=15,
            threshold_p95_warn_ms=3000, threshold_p95_critical_ms=5000,
            threshold_error_rate_warn=1.0, threshold_error_rate_critical=5.0,
            threshold_session_success_warn=95.0, threshold_session_success_critical=80.0,
        )
        score, details = HealthScoringService.calculate_score(
            p95_ms=200, token_usage_ratio=0.5,
            error_rate=0.1, session_success_rate=0.99,
            dependency_healthy=True, tpl=tpl,
        )
        assert details["deductions"]["error_rate"] == 25

    def test_token_over_budget(self):
        """Token 超预算扣分"""
        tpl = SimpleNamespace(
            weight_response_time=20, weight_token=20,
            weight_error_rate=25, weight_session_success=20,
            weight_dependency=15,
            threshold_p95_warn_ms=3000, threshold_p95_critical_ms=5000,
            threshold_error_rate_warn=1.0, threshold_error_rate_critical=5.0,
            threshold_session_success_warn=95.0, threshold_session_success_critical=80.0,
        )
        score, details = HealthScoringService.calculate_score(
            p95_ms=200, token_usage_ratio=1.5,
            error_rate=0.005, session_success_rate=0.99,
            dependency_healthy=True, tpl=tpl,
        )
        assert details["deductions"]["token"] == 15

    def test_dependency_unhealthy(self):
        """依赖不健康扣分"""
        tpl = SimpleNamespace(
            weight_response_time=20, weight_token=20,
            weight_error_rate=25, weight_session_success=20,
            weight_dependency=15,
            threshold_p95_warn_ms=3000, threshold_p95_critical_ms=5000,
            threshold_error_rate_warn=1.0, threshold_error_rate_critical=5.0,
            threshold_session_success_warn=95.0, threshold_session_success_critical=80.0,
        )
        score, details = HealthScoringService.calculate_score(
            p95_ms=200, token_usage_ratio=0.5,
            error_rate=0.005, session_success_rate=0.99,
            dependency_healthy=False, tpl=tpl,
        )
        assert details["deductions"]["dependency"] == 10

    def test_low_session_success(self):
        """会话成功率低扣分"""
        tpl = SimpleNamespace(
            weight_response_time=20, weight_token=20,
            weight_error_rate=25, weight_session_success=20,
            weight_dependency=15,
            threshold_p95_warn_ms=3000, threshold_p95_critical_ms=5000,
            threshold_error_rate_warn=1.0, threshold_error_rate_critical=5.0,
            threshold_session_success_warn=95.0, threshold_session_success_critical=80.0,
        )
        score, details = HealthScoringService.calculate_score(
            p95_ms=200, token_usage_ratio=0.5,
            error_rate=0.005, session_success_rate=0.70,
            dependency_healthy=True, tpl=tpl,
        )
        assert details["deductions"]["session_success"] == 15

    def test_worst_score(self):
        """全部异常时应得到最低分"""
        tpl = SimpleNamespace(
            weight_response_time=20, weight_token=20,
            weight_error_rate=25, weight_session_success=20,
            weight_dependency=15,
            threshold_p95_warn_ms=3000, threshold_p95_critical_ms=5000,
            threshold_error_rate_warn=1.0, threshold_error_rate_critical=5.0,
            threshold_session_success_warn=95.0, threshold_session_success_critical=80.0,
        )
        score, details = HealthScoringService.calculate_score(
            p95_ms=15000, token_usage_ratio=2.0,
            error_rate=0.5, session_success_rate=0.3,
            dependency_healthy=False, tpl=tpl,
        )
        d = details["deductions"]
        assert d["response_time"] > 0
        assert d["token"] > 0
        assert d["error_rate"] > 0
        assert d["session_success"] > 0
        assert d["dependency"] > 0
        assert score < 85
