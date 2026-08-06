"""
测试 - 剩余服务: 模型热切换、跨Agent恢复、会话沙箱、Agent下钻、WS监控
"""

import time
import pytest


class TestModelHotswap:
    """模型热切换"""

    def _make_service(self):
        from app.services.model_hotswap_service import ModelHotswapService
        return ModelHotswapService()

    def test_register_model(self):
        svc = self._make_service()
        result = svc.register_model({
            "model_id": "gpt-4o", "provider": "openai",
            "endpoint": "https://api.openai.com", "max_tokens": 4096,
        })
        assert result["registered"] is True

    def test_switch_model(self):
        svc = self._make_service()
        svc.register_model({"model_id": "gpt-4o", "provider": "openai"})
        svc.register_model({"model_id": "claude-3", "provider": "anthropic"})
        result = svc.switch("claude-3", reason="test", triggered_by="manual")
        assert result["from_model"] == "gpt-4o"
        assert result["to_model"] == "claude-3"

    def test_rollback(self):
        svc = self._make_service()
        svc.register_model({"model_id": "gpt-4o"})
        svc.register_model({"model_id": "gpt-4o-mini"})
        svc.switch("gpt-4o-mini", reason="降级")
        result = svc.rollback()
        assert result["to_model"] == "gpt-4o"

    def test_canary_release(self):
        svc = self._make_service()
        svc.register_model({"model_id": "gpt-4o"})
        svc.register_model({"model_id": "gpt-5"})
        result = svc.switch("gpt-5", reason="灰度", traffic_percent=20)
        assert result["traffic_percent"] == 20
        assert result["status"] == "canary"

    def test_history(self):
        svc = self._make_service()
        svc.register_model({"model_id": "a"})
        svc.register_model({"model_id": "b"})
        svc.switch("b")
        history = svc.get_history()
        assert len(history) == 1

    def test_get_current(self):
        svc = self._make_service()
        svc.register_model({"model_id": "m1"})
        assert svc.get_current_model() == "m1"

    def test_stats(self):
        svc = self._make_service()
        svc.register_model({"model_id": "a"})
        stats = svc.get_stats()
        assert stats["models_registered"] == 1


class TestCrossAgentRestore:
    """跨Agent恢复"""

    def _make_service(self):
        from app.services.cross_agent_restore_service import CrossAgentRestoreService
        return CrossAgentRestoreService()

    def test_register_and_plan(self):
        svc = self._make_service()
        svc.register_backup("b1", "agent_old", {"config": {"key": "val"}})
        svc.register_agent("agent_new", {"config": {}})
        result = svc.create_restore_plan("b1", "agent_new")
        assert "plan_id" in result
        assert result["conflicts_found"] == 0

    def test_execute_restore(self):
        import asyncio
        svc = self._make_service()
        svc.register_backup("b1", "agent_old", {"config": {"key": "val"}})
        svc.register_agent("agent_new", {"config": {}})
        plan = svc.create_restore_plan("b1", "agent_new")
        result = asyncio.run(svc.execute_restore(plan["plan_id"]))
        assert result["status"] in ("completed", "partial")

    def test_verify(self):
        svc = self._make_service()
        svc.register_backup("b1", "a1", {"config": {"x": 1}})
        svc.register_agent("a2", {"config": {"x": 1}})
        plan = svc.create_restore_plan("b1", "a2")
        result = svc.verify_restore(plan["plan_id"])
        assert result["verified"] is True

    def test_history(self):
        svc = self._make_service()
        svc.register_backup("b1", "a1", {"config": {}})
        svc.register_agent("a2", {"config": {}})
        plan = svc.create_restore_plan("b1", "a2")
        import asyncio
        asyncio.run(svc.execute_restore(plan["plan_id"]))
        history = svc.get_history()
        assert len(history) == 1


class TestConversationSandbox:
    """会话沙箱"""

    def _make_service(self):
        from app.services.conversation_sandbox_service import ConversationSandboxService
        return ConversationSandboxService()

    def test_create_test_case(self):
        svc = self._make_service()
        result = svc.create_test_case({
            "name": "基础测试", "agent_id": "a1",
            "messages": [{"role": "user", "content": "你好"}],
            "assertions": [{"type": "contains", "expected": "你好"}],
        })
        assert result["created"] is True

    def test_list_test_cases(self):
        svc = self._make_service()
        svc.create_test_case({"name": "T1", "agent_id": "a1"})
        svc.create_test_case({"name": "T2", "agent_id": "a2"})
        cases = svc.list_test_cases(agent_id="a1")
        assert len(cases) == 1

    def test_create_session(self):
        svc = self._make_service()
        result = svc.create_session("a1")
        assert "session_id" in result

    def test_statistics(self):
        svc = self._make_service()
        stats = svc.get_statistics()
        assert stats["total_cases"] == 0


class TestAgentDrilldown:
    """Agent下钻分析"""

    def _make_service(self):
        from app.services.agent_drilldown_service import AgentDrilldownService
        return AgentDrilldownService()

    def test_record_and_drilldown(self):
        svc = self._make_service()
        for i in range(20):
            svc.record_request(
                "a1", response_time=0.5 + i * 0.1,
                tokens_used=100 + i * 10, cost_usd=0.001 * (i + 1),
                success=i < 18, user_satisfaction=3.5 + (i % 2),
            )
        result = svc.drilldown("a1")
        assert "metrics" in result
        assert result["metrics"]["total_requests"] == 20
        assert "bottlenecks" in result
        assert "recommendations" in result

    def test_no_data(self):
        svc = self._make_service()
        result = svc.drilldown("nonexistent")
        assert result.get("status") == "no_data"

    def test_health_score(self):
        svc = self._make_service()
        for i in range(10):
            svc.record_request("a1", 0.5, 100, 0.001, True, 4.0)
        result = svc.drilldown("a1")
        assert result["overall_health_score"] > 50


class TestWebSocketMonitor:
    """WebSocket实时监控"""

    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self):
        from app.services.websocket_monitor_service import WebSocketMonitorService
        svc = WebSocketMonitorService()
        result = await svc.connect("c1", ["system", "metrics"])
        assert result["client_id"] == "c1"
        assert svc.get_client_count() == 1

        await svc.disconnect("c1")
        assert svc.get_client_count() == 0

    @pytest.mark.asyncio
    async def test_publish_and_consume(self):
        from app.services.websocket_monitor_service import WebSocketMonitorService
        svc = WebSocketMonitorService()
        await svc.connect("c1", ["alert"])
        await svc.publish("alert", "test_event", {"msg": "hello"})
        events = await svc.consume_all("c1")
        assert len(events) == 1
        assert events[0].event_type == "test_event"

    @pytest.mark.asyncio
    async def test_heartbeat(self):
        from app.services.websocket_monitor_service import WebSocketMonitorService
        svc = WebSocketMonitorService()
        await svc.connect("c1", ["system"])
        ok = await svc.heartbeat("c1")
        assert ok is True

    @pytest.mark.asyncio
    async def test_metrics_history(self):
        from app.services.websocket_monitor_service import WebSocketMonitorService, MetricsSnapshot
        svc = WebSocketMonitorService()
        await svc.record_metrics(MetricsSnapshot(
            timestamp=time.time(), cpu_percent=50.0, memory_percent=60.0,
            request_rate=100, error_rate=0.01,
        ))
        history = await svc.get_metrics_history(60)
        assert len(history) == 1

    @pytest.mark.asyncio
    async def test_subscribe_unsubscribe(self):
        from app.services.websocket_monitor_service import WebSocketMonitorService
        svc = WebSocketMonitorService()
        await svc.connect("c1", ["system"])
        await svc.subscribe("c1", ["alert"])
        clients = svc.get_clients_by_channel("alert")
        assert "c1" in clients
        await svc.unsubscribe("c1", ["alert"])
        clients = svc.get_clients_by_channel("alert")
        assert "c1" not in clients
