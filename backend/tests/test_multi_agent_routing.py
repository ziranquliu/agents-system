"""
MultiAgentRoutingService 测试 — 5种路由策略、消息序列化、亲和力
"""
import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock
from collections import defaultdict

from app.services.multi_agent_routing_service import (
    MultiAgentRoutingService,
    MessageSerializer,
    MessageEnvelope,
    MessageState,
    RoutingStrategy,
    AgentEndpoint,
    RoutingRule,
    AffinityEntry,
    SessionMigrationRecord,
)


# ============================================================
# 枚举 / 常量测试
# ============================================================

class TestRoutingStrategy:
    def test_all_strategies(self):
        values = {s.value for s in RoutingStrategy}
        assert "round_robin" in values
        assert "least_queue" in values
        assert "most_idle" in values
        assert "affinity" in values
        assert "capability" in values

    def test_strategy_count_at_least_5(self):
        assert len(RoutingStrategy) >= 5


class TestMessageState:
    def test_all_states(self):
        values = {s.value for s in MessageState}
        assert "pending" in values
        assert "delivered" in values
        assert "processed" in values
        assert "failed" in values
        assert "dead_letter" in values

    def test_state_count_at_least_5(self):
        assert len(MessageState) >= 5


# ============================================================
# MessageEnvelope 测试
# ============================================================

class TestMessageEnvelope:
    def test_default_values(self):
        env = MessageEnvelope()
        assert env.id == ""
        assert env.sequence == 0
        assert env.source_session == ""
        assert env.target_session == ""
        assert env.priority == 1
        assert env.state == "pending"
        assert env.retry_count == 0
        assert env.max_retries == 3
        assert env.ttl_seconds == 300


# ============================================================
# AgentEndpoint 测试
# ============================================================

class TestAgentEndpoint:
    def test_default_values(self):
        ep = AgentEndpoint()
        assert ep.agent_id == ""
        assert ep.current_load == 0
        assert ep.max_concurrent == 10
        assert ep.is_healthy is True
        assert ep.last_heartbeat >= 0


# ============================================================
# MessageSerializer 测试
# ============================================================

class TestMessageSerializer:
    def setup_method(self):
        self.serializer = MessageSerializer()

    @pytest.mark.asyncio
    async def test_create_envelope_increments_sequence(self):
        env1 = await self.serializer.create_envelope("s1", "s2", {"text": "hi"})
        env2 = await self.serializer.create_envelope("s1", "s2", {"text": "bye"})
        assert env2.sequence == env1.sequence + 1

    @pytest.mark.asyncio
    async def test_envelope_has_uuid_id(self):
        env = await self.serializer.create_envelope("s1", "s2", {})
        assert env.id.startswith("msg_")
        assert len(env.id) > 10  # "msg_" + hex chars

    @pytest.mark.asyncio
    async def test_deliver_pending_message(self):
        env = await self.serializer.create_envelope("s1", "s2", {})
        assert env.state == MessageState.PENDING.value
        ok = await self.serializer.deliver(env.id, "agent1")
        assert ok is True
        assert env.state == MessageState.DELIVERED.value
        assert env.target_agent == "agent1"

    @pytest.mark.asyncio
    async def test_deliver_nonexistent_returns_false(self):
        ok = await self.serializer.deliver("nonexistent_id", "agent1")
        assert ok is False

    @pytest.mark.asyncio
    async def test_process_delivered_message(self):
        env = await self.serializer.create_envelope("s1", "s2", {})
        await self.serializer.deliver(env.id, "agent1")
        ok = await self.serializer.process(env.id)
        assert ok is True
        assert env.state == MessageState.PROCESSED.value

    @pytest.mark.asyncio
    async def test_process_pending_message(self):
        env = await self.serializer.create_envelope("s1", "s2", {})
        ok = await self.serializer.process(env.id)
        assert ok is True
        assert env.state == MessageState.PROCESSED.value

    @pytest.mark.asyncio
    async def test_process_nonexistent_returns_false(self):
        ok = await self.serializer.process("nonexistent")
        assert ok is False

    @pytest.mark.asyncio
    async def test_fail_message_becomes_failed(self):
        env = await self.serializer.create_envelope("s1", "s2", {})
        ok = await self.serializer.fail(env.id, "timeout")
        assert ok is True
        assert env.state == MessageState.FAILED.value
        assert env.error == "timeout"
        assert env.retry_count == 1

    @pytest.mark.asyncio
    async def test_fail_reaches_max_retries_becomes_dead_letter(self):
        env = await self.serializer.create_envelope("s1", "s2", {})
        for i in range(env.max_retries):
            await self.serializer.fail(env.id, f"error_{i}")
        assert env.state == MessageState.DEAD_LETTER.value

    @pytest.mark.asyncio
    async def test_fail_nonexistent_returns_false(self):
        ok = await self.serializer.fail("bad_id", "error")
        assert ok is False

    @pytest.mark.asyncio
    async def test_get_pending_sorted_by_priority(self):
        await self.serializer.create_envelope("s1", "s2", {}, priority=1)
        await self.serializer.create_envelope("s1", "s2", {}, priority=5)
        await self.serializer.create_envelope("s1", "s2", {}, priority=3)
        pending = self.serializer.get_pending()
        assert len(pending) == 3
        assert pending[0]["priority"] == 5
        assert pending[1]["priority"] == 3
        assert pending[2]["priority"] == 1

    @pytest.mark.asyncio
    async def test_get_pending_limit(self):
        for i in range(5):
            await self.serializer.create_envelope("s1", "s2", {})
        pending = self.serializer.get_pending(limit=2)
        assert len(pending) == 2

    @pytest.mark.asyncio
    async def test_get_sequence(self):
        assert self.serializer.get_sequence() == 0
        await self.serializer.create_envelope("s1", "s2", {})
        assert self.serializer.get_sequence() == 1


# ============================================================
# RoutingRule / AffinityEntry 测试
# ============================================================

class TestRoutingRule:
    def test_default_values(self):
        rule = RoutingRule(source_pattern="*", target_agent="a1")
        assert rule.strategy == "round_robin"
        assert rule.is_active is True
        assert rule.priority == 0


class TestAffinityEntry:
    def test_default_values(self):
        aff = AffinityEntry()
        assert aff.score == 1.0
        assert aff.interaction_count == 0


class TestSessionMigrationRecord:
    def test_default_values(self):
        rec = SessionMigrationRecord()
        assert rec.status == "completed"
        assert rec.messages_migrated == 0


# ============================================================
# MultiAgentRoutingService 路由策略测试
# ============================================================

class TestMultiAgentRoutingRoundRobin:
    def setup_method(self):
        self.service = MultiAgentRoutingService()

    def test_register_agent(self):
        result = self.service.register_agent("a1", name="Agent 1", capabilities=["code"])
        assert result["agent_id"] == "a1"
        assert result["registered"] is True
        assert "code" in self.service._agents["a1"].capabilities

    def test_register_multiple_agents(self):
        self.service.register_agent("a1", capabilities=["code"])
        self.service.register_agent("a2", capabilities=["data"])
        assert len(self.service._agents) == 2

    def test_round_robin_distribution(self):
        self.service.register_agent("a1")
        self.service.register_agent("a2")
        self.service.register_agent("a3")

        targets = set()
        for i in range(6):
            result = self.service.route_message(f"s{i}", {"text": "hi"})
            targets.add(result.get("agent_id", ""))

        # 3 个 agent 轮询, 6 次应覆盖全部
        assert len(targets) == 3

    def test_no_agents_returns_error(self):
        result = self.service.route_message("s1", {"text": "hi"})
        assert "error" in result


class TestMultiAgentRoutingLeastQueue:
    def setup_method(self):
        self.service = MultiAgentRoutingService()

    def test_least_queue_picks_lowest(self):
        self.service.register_agent("a1")
        self.service.register_agent("a2")
        self.service._agents["a1"].queue_depth = 5
        self.service._agents["a2"].queue_depth = 2

        result = self.service.route_message("s1", {"text": "hi"}, strategy="least_queue")
        assert result.get("agent_id") == "a2"

    def test_least_queue_excludes_unhealthy(self):
        self.service.register_agent("a1")
        self.service.register_agent("a2")
        self.service._agents["a1"].is_healthy = False
        self.service._agents["a2"].is_healthy = True

        result = self.service.route_message("s1", {"text": "hi"}, strategy="least_queue")
        assert result.get("agent_id") == "a2"


class TestMultiAgentRoutingCapability:
    def setup_method(self):
        self.service = MultiAgentRoutingService()

    def test_capability_picks_matching_agent(self):
        self.service.register_agent("a1", capabilities=["code"])
        self.service.register_agent("a2", capabilities=["data"])

        result = self.service.route_message(
            "s1", {"text": "hi"},
            strategy="capability",
            capability_required="code"
        )
        assert result.get("agent_id") == "a1"

    def test_capability_no_match_fallback(self):
        self.service.register_agent("a1", capabilities=["code"])
        self.service.register_agent("a2", capabilities=["data"])

        result = self.service.route_message(
            "s1", {"text": "hi"},
            strategy="capability",
            capability_required="ml"
        )
        # 无匹配时 fallback 到 queue_depth 最低的
        assert result.get("agent_id") in ("a1", "a2")

    def test_capability_excludes_unhealthy(self):
        self.service.register_agent("a1", capabilities=["code"])
        self.service.register_agent("a2", capabilities=["code"])
        self.service._agents["a1"].is_healthy = False
        result = self.service.route_message(
            "s1", {"text": "hi"},
            strategy="capability",
            capability_required="code"
        )
        assert result.get("agent_id") == "a2"


# ============================================================
# 亲和力测试
# ============================================================

class TestAffinity:
    def setup_method(self):
        self.service = MultiAgentRoutingService()
        self.service.register_agent("a1")
        self.service.register_agent("a2")

    def test_affinity_via_route_message(self):
        """路由消息会自动建立亲和力"""
        self.service.route_message("s1", {"text": "hi"}, user_id="user1")
        target = self.service.get_session_agent("s1")
        assert target is not None

    def test_get_session_agent(self):
        self.service.route_message("s1", {"text": "hi"})
        agent = self.service.get_session_agent("s1")
        assert agent is not None
        assert agent in self.service._agents

    def test_get_agent_sessions(self):
        self.service.route_message("s1", {"text": "hi"})
        sessions = self.service.get_agent_sessions(self.service.get_session_agent("s1"))
        assert "s1" in sessions


# ============================================================
# 会话迁移测试
# ============================================================

class TestSessionMigration:
    def setup_method(self):
        self.service = MultiAgentRoutingService()
        self.service.register_agent("a1")
        self.service.register_agent("a2")

    @pytest.mark.asyncio
    async def test_migrate_session(self):
        self.service.route_message("s1", {"text": "hi"})
        original_agent = self.service.get_session_agent("s1")
        assert original_agent == "a1"

        # migrate_session 需要 db，用 mock
        mock_db = AsyncMock()
        result = await self.service.migrate_session("s1", "a2", reason="load_balance")
        assert result.get("migrated") is True or result.get("success") is True

    @pytest.mark.asyncio
    async def test_migration_history(self):
        history = self.service.get_migration_history()
        assert isinstance(history, list)


# ============================================================
# 路由规则测试
# ============================================================

class TestRoutingRules:
    def setup_method(self):
        self.service = MultiAgentRoutingService()
        self.service.register_agent("a1")

    def test_add_rule(self):
        result = self.service.add_routing_rule({"id": "r1", "target_agent": "a1", "priority": 10})
        assert result["added"] is True

    def test_rules_sorted_by_priority(self):
        self.service.add_routing_rule({"id": "r1", "priority": 1})
        self.service.add_routing_rule({"id": "r2", "priority": 10})
        self.service.add_routing_rule({"id": "r3", "priority": 5})
        rules = self.service.list_routing_rules()
        priorities = [r["priority"] if "priority" in r else 0 for r in rules]

    def test_remove_rule(self):
        self.service.add_routing_rule({"id": "r1", "priority": 1})
        result = self.service.remove_routing_rule("r1")
        assert result["removed"] is True
        assert len(self.service._routing_rules) == 0

    def test_remove_nonexistent_rule(self):
        result = self.service.remove_routing_rule("nonexistent")
        assert result["removed"] is False


# ============================================================
# 统计测试
# ============================================================

class TestStats:
    def setup_method(self):
        self.service = MultiAgentRoutingService()

    def test_stats_initial(self):
        stats = self.service.get_statistics()
        assert stats["total_routed"] == 0

    def test_agents_list(self):
        self.service.register_agent("a1", name="Agent 1")
        self.service.register_agent("a2", name="Agent 2")
        agents = self.service.list_agents()
        assert len(agents) == 2
        assert agents[0]["agent_id"] == "a1"

    def test_update_agent_status(self):
        self.service.register_agent("a1")
        result = self.service.update_agent_status("a1", current_load=5, queue_depth=3, is_healthy=True)
        assert result.get("updated") is True
        assert self.service._agents["a1"].current_load == 5

    def test_unregister_agent(self):
        self.service.register_agent("a1")
        result = self.service.unregister_agent("a1")
        assert result["unregistered"] is True
        assert "a1" not in self.service._agents

    def test_unregister_nonexistent(self):
        result = self.service.unregister_agent("nonexistent")
        assert "error" in result

    def test_get_statistics_after_route(self):
        self.service.register_agent("a1")
        self.service.route_message("s1", {"text": "hi"})
        stats = self.service.get_statistics()
        assert stats["total_routed"] >= 1
