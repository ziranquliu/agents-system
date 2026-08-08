"""
多 Agent 会话路由 + 消息序列化服务

功能:
- 多 Agent 会话路由 (轮询/最短队列/最亲和/自定义)
- 消息序列化 (全局有序 + 并发安全)
- 会话迁移 (跨 Agent 无缝切换)
- 消息队列 (优先级 + 死信)
- 路由策略热更新
"""

import asyncio
import logging
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 数据结构
# ============================================================

class RoutingStrategy(str, Enum):
    """路由策略"""
    ROUND_ROBIN = "round_robin"
    LEAST_QUEUE = "least_queue"
    MOST_IDLE = "most_idle"
    AFFINITY = "affinity"        # 用户-Agent 亲和
    CAPABILITY = "capability"     # 能力匹配
    CUSTOM = "custom"


class MessagePriority(int, Enum):
    """消息优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


class MessageState(str, Enum):
    """消息状态"""
    PENDING = "pending"
    QUEUED = "queued"
    ROUTING = "routing"
    DELIVERED = "delivered"
    PROCESSED = "processed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


@dataclass
class AgentEndpoint:
    """Agent 端点"""
    agent_id: str = ""
    name: str = ""
    capabilities: list[str] = field(default_factory=list)  # 能力标签
    max_concurrent: int = 10
    current_load: int = 0
    queue_depth: int = 0
    avg_response_time: float = 0
    is_healthy: bool = True
    last_heartbeat: float = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MessageEnvelope:
    """消息信封 (全局有序)"""
    id: str = ""
    sequence: int = 0           # 全局递增序号
    source_session: str = ""
    target_session: str = ""
    source_agent: str = ""
    target_agent: str = ""
    content: dict[str, Any] = field(default_factory=dict)
    priority: int = 1
    state: str = "pending"
    created_at: float = 0
    delivered_at: float = 0
    processed_at: float = 0
    retry_count: int = 0
    max_retries: int = 3
    correlation_id: str = ""    # 请求-响应关联
    ttl_seconds: int = 300      # 消息存活时间
    error: str = ""


@dataclass
class RoutingRule:
    """路由规则"""
    id: str = ""
    source_pattern: str = ""     # 源 session/agent 匹配模式
    target_agent: str = ""       # 固定目标
    strategy: str = "round_robin"
    capability_required: str = ""  # 需要的能力标签
    priority: int = 0            # 规则优先级 (越大越先)
    is_active: bool = True


@dataclass
class SessionMigrationRecord:
    """会话迁移记录"""
    id: str = ""
    session_id: str = ""
    from_agent: str = ""
    to_agent: str = ""
    reason: str = ""
    messages_migrated: int = 0
    timestamp: float = 0
    status: str = "completed"


@dataclass
class AffinityEntry:
    """亲和力条目"""
    user_id: str = ""
    agent_id: str = ""
    score: float = 1.0
    last_used: float = 0
    interaction_count: int = 0


# ============================================================
# 消息序列化器
# ============================================================

class MessageSerializer:
    """消息序列化器 - 全局有序 + 并发安全"""

    def __init__(self):
        self._sequence = 0
        self._lock = asyncio.Lock()
        self._pending: dict[str, MessageEnvelope] = {}
        self._delivered: deque[MessageEnvelope] = deque(maxlen=10000)

    async def create_envelope(
        self,
        source_session: str,
        target_session: str,
        content: dict[str, Any],
        source_agent: str = "",
        target_agent: str = "",
        priority: int = 1,
        correlation_id: str = "",
        ttl_seconds: int = 300,
    ) -> MessageEnvelope:
        """创建消息信封 (原子递增序号)"""
        async with self._lock:
            self._sequence += 1
            seq = self._sequence

        envelope = MessageEnvelope(
            id=f"msg_{uuid.uuid4().hex[:12]}",
            sequence=seq,
            source_session=source_session,
            target_session=target_session,
            source_agent=source_agent,
            target_agent=target_agent,
            content=content,
            priority=priority,
            state=MessageState.PENDING.value,
            created_at=time.time(),
            correlation_id=correlation_id,
            ttl_seconds=ttl_seconds,
        )

        self._pending[envelope.id] = envelope
        return envelope

    async def deliver(self, envelope_id: str, agent_id: str) -> bool:
        """标记消息已送达"""
        env = self._pending.get(envelope_id)
        if not env:
            return False
        env.state = MessageState.DELIVERED.value
        env.target_agent = agent_id
        env.delivered_at = time.time()
        self._delivered.append(env)
        self._pending.pop(envelope_id, None)
        return True

    async def process(self, envelope_id: str) -> bool:
        """标记消息已处理"""
        env = self._pending.get(envelope_id) or next(
            (e for e in self._delivered if e.id == envelope_id), None
        )
        if not env:
            return False
        env.state = MessageState.PROCESSED.value
        env.processed_at = time.time()
        return True

    async def fail(self, envelope_id: str, error: str) -> bool:
        """标记消息失败"""
        env = self._pending.get(envelope_id)
        if not env:
            return False
        env.retry_count += 1
        if env.retry_count >= env.max_retries:
            env.state = MessageState.DEAD_LETTER.value
            env.error = error
        else:
            env.state = MessageState.FAILED.value
            env.error = error
        return True

    def get_pending(self, limit: int = 100) -> list[dict]:
        """获取待处理消息"""
        pending = sorted(
            self._pending.values(),
            key=lambda e: (-e.priority, e.sequence),
        )[:limit]
        return [self._envelope_to_dict(e) for e in pending]

    def get_sequence(self) -> int:
        return self._sequence

    def _envelope_to_dict(self, e: MessageEnvelope) -> dict:
        return {
            "id": e.id,
            "sequence": e.sequence,
            "source_session": e.source_session,
            "target_session": e.target_session,
            "source_agent": e.source_agent,
            "target_agent": e.target_agent,
            "priority": e.priority,
            "state": e.state,
            "created_at": e.created_at,
            "delivered_at": e.delivered_at,
            "retry_count": e.retry_count,
            "correlation_id": e.correlation_id,
            "error": e.error,
        }


# ============================================================
# 主服务: 多 Agent 路由 + 序列化
# ============================================================

class MultiAgentRoutingService:
    """
    多 Agent 会话路由 + 消息序列化

    - 5 种路由策略: round_robin / least_queue / most_idle / affinity / capability
    - 消息全局序号: 单调递增, 并发安全
    - 会话迁移: 跨 Agent 无缝切换, 消息跟随
    - 亲和力: 用户-Agent 映射学习
    - 路由规则: 可热更新
    - 死信队列: 超过重试上限的消息
    """

    def __init__(self):
        self._agents: dict[str, AgentEndpoint] = {}
        self._serializer = MessageSerializer()
        self._routing_rules: list[RoutingRule] = []
        self._affinity: dict[str, AffinityEntry] = {}  # user_id -> AffinityEntry
        self._session_agents: dict[str, str] = {}  # session_id -> agent_id
        self._migrations: list[SessionMigrationRecord] = []
        self._dead_letters: list[MessageEnvelope] = []
        self._round_robin_idx = 0
        self._stats = defaultdict(int)

    # ----------------------------------------------------------
    # Agent 管理
    # ----------------------------------------------------------

    def register_agent(self, agent_id: str, name: str = "", capabilities: list[str] = None, max_concurrent: int = 10) -> dict:
        """注册 Agent 端点"""
        agent = AgentEndpoint(
            agent_id=agent_id,
            name=name or agent_id,
            capabilities=capabilities or [],
            max_concurrent=max_concurrent,
            last_heartbeat=time.time(),
        )
        self._agents[agent_id] = agent
        return {"agent_id": agent_id, "registered": True}

    def unregister_agent(self, agent_id: str) -> dict:
        if agent_id in self._agents:
            del self._agents[agent_id]
            return {"unregistered": True}
        return {"error": "Agent 不存在"}

    def update_agent_status(
        self, agent_id: str, current_load: int = 0,
        queue_depth: int = 0, avg_response_time: float = 0,
        is_healthy: bool = True,
    ) -> dict:
        agent = self._agents.get(agent_id)
        if not agent:
            return {"error": "Agent 不存在"}
        agent.current_load = current_load
        agent.queue_depth = queue_depth
        agent.avg_response_time = avg_response_time
        agent.is_healthy = is_healthy
        agent.last_heartbeat = time.time()
        return {"updated": True}

    def list_agents(self) -> list[dict]:
        return [
            {
                "agent_id": a.agent_id,
                "name": a.name,
                "capabilities": a.capabilities,
                "current_load": a.current_load,
                "max_concurrent": a.max_concurrent,
                "queue_depth": a.queue_depth,
                "avg_response_time": a.avg_response_time,
                "is_healthy": a.is_healthy,
            }
            for a in self._agents.values()
        ]

    # ----------------------------------------------------------
    # 路由规则
    # ----------------------------------------------------------

    def add_routing_rule(self, rule: dict) -> dict:
        r = RoutingRule(**rule)
        self._routing_rules.append(r)
        self._routing_rules.sort(key=lambda x: x.priority, reverse=True)
        return {"rule_id": r.id, "added": True}

    def remove_routing_rule(self, rule_id: str) -> dict:
        before = len(self._routing_rules)
        self._routing_rules = [r for r in self._routing_rules if r.id != rule_id]
        return {"removed": len(self._routing_rules) < before}

    def list_routing_rules(self) -> list[dict]:
        return [
            {"id": r.id, "source_pattern": r.source_pattern, "target_agent": r.target_agent,
             "strategy": r.strategy, "capability_required": r.capability_required, "is_active": r.is_active}
            for r in self._routing_rules
        ]

    # ----------------------------------------------------------
    # 路由决策
    # ----------------------------------------------------------

    def route_message(
        self,
        session_id: str,
        content: dict[str, Any],
        user_id: str = "",
        strategy: str = "",
        capability_required: str = "",
        priority: int = 1,
    ) -> dict:
        """路由消息到最优 Agent"""
        healthy_agents = [a for a in self._agents.values() if a.is_healthy]
        if not healthy_agents:
            return {"error": "无可用 Agent"}

        # 1. 检查亲和力
        if user_id and user_id in self._affinity:
            aff = self._affinity[user_id]
            target = self._agents.get(aff.agent_id)
            if target and target.is_healthy:
                target.queue_depth += 1
                self._update_affinity(user_id, aff.agent_id)
                return self._deliver_to_agent(session_id, content, target.agent_id, priority)

        # 2. 匹配路由规则
        for rule in self._routing_rules:
            if not rule.is_active:
                continue
            if rule.target_agent and rule.target_agent in self._agents:
                target = self._agents[rule.target_agent]
                if target.is_healthy:
                    if not rule.capability_required or rule.capability_required in target.capabilities:
                        return self._deliver_to_agent(session_id, content, target.agent_id, priority)

        # 3. 按策略选择
        effective_strategy = strategy or RoutingStrategy.ROUND_ROBIN.value

        if effective_strategy == RoutingStrategy.LEAST_QUEUE.value:
            agent = min(healthy_agents, key=lambda a: a.queue_depth)
        elif effective_strategy == RoutingStrategy.MOST_IDLE.value:
            agent = min(healthy_agents, key=lambda a: a.current_load)
        elif effective_strategy == RoutingStrategy.CAPABILITY.value:
            capable = [a for a in healthy_agents if capability_required in a.capabilities]
            agent = capable[0] if capable else min(healthy_agents, key=lambda a: a.queue_depth)
        else:  # round_robin
            idx = self._round_robin_idx % len(healthy_agents)
            agent = healthy_agents[idx]
            self._round_robin_idx += 1

        return self._deliver_to_agent(session_id, content, agent.agent_id, priority)

    def _deliver_to_agent(
        self, session_id: str, content: dict, agent_id: str, priority: int
    ) -> dict:
        """投递到指定 Agent"""
        agent = self._agents.get(agent_id)
        if agent:
            agent.queue_depth += 1
        self._session_agents[session_id] = agent_id
        self._stats["routed"] += 1

        return {
            "routed": True,
            "agent_id": agent_id,
            "session_id": session_id,
            "queue_depth": agent.queue_depth if agent else 0,
        }

    def _update_affinity(self, user_id: str, agent_id: str):
        """更新亲和力"""
        key = f"{user_id}:{agent_id}"
        if key in self._affinity:
            aff = self._affinity[key]
            aff.score = min(10, aff.score + 0.1)
            aff.last_used = time.time()
            aff.interaction_count += 1
        else:
            self._affinity[key] = AffinityEntry(
                user_id=user_id,
                agent_id=agent_id,
                score=1.0,
                last_used=time.time(),
                interaction_count=1,
            )

    # ----------------------------------------------------------
    # 消息序列化
    # ----------------------------------------------------------

    async def send_message(
        self,
        source_session: str,
        target_session: str,
        content: dict[str, Any],
        priority: int = 1,
        correlation_id: str = "",
    ) -> dict:
        """发送消息 (全局有序序列化)"""
        source_agent = self._session_agents.get(source_session, "")
        target_agent = self._session_agents.get(target_session, "")

        envelope = await self._serializer.create_envelope(
            source_session=source_session,
            target_session=target_session,
            content=content,
            source_agent=source_agent,
            target_agent=target_agent,
            priority=priority,
            correlation_id=correlation_id,
        )

        return {
            "message_id": envelope.id,
            "sequence": envelope.sequence,
            "state": envelope.state,
            "correlation_id": envelope.correlation_id,
        }

    async def process_message(self, message_id: str) -> dict:
        """确认消息已处理"""
        ok = await self._serializer.process(message_id)
        return {"processed": ok, "message_id": message_id}

    async def fail_message(self, message_id: str, error: str) -> dict:
        """标记消息失败"""
        ok = await self._serializer.fail(message_id, error)
        if ok:
            self._stats["failed"] += 1
        return {"failed": ok, "message_id": message_id}

    def get_pending_messages(self, limit: int = 50) -> list[dict]:
        return self._serializer.get_pending(limit)

    def get_sequence_number(self) -> int:
        return self._serializer.get_sequence()

    # ----------------------------------------------------------
    # 会话迁移
    # ----------------------------------------------------------

    async def migrate_session(
        self,
        session_id: str,
        to_agent: str,
        reason: str = "",
    ) -> dict:
        """跨 Agent 会话迁移"""
        from_agent = self._session_agents.get(session_id, "")
        if not from_agent:
            return {"error": "会话未绑定 Agent"}

        if to_agent not in self._agents:
            return {"error": f"目标 Agent {to_agent} 不存在"}

        target = self._agents[to_agent]
        if not target.is_healthy:
            return {"error": f"目标 Agent {to_agent} 不健康"}

        # 更新路由
        self._session_agents[session_id] = to_agent

        # 更新亲和力
        # 从内容推断 user_id (简化: 使用 session_id)
        if session_id in self._affinity:
            old_aff = self._affinity[session_id]
            new_key = f"{old_aff.user_id}:{to_agent}"
            self._affinity[new_key] = AffinityEntry(
                user_id=old_aff.user_id,
                agent_id=to_agent,
                score=old_aff.score,
                last_used=time.time(),
                interaction_count=old_aff.interaction_count,
            )

        # 记录迁移
        record = SessionMigrationRecord(
            id=f"mig_{uuid.uuid4().hex[:8]}",
            session_id=session_id,
            from_agent=from_agent,
            to_agent=to_agent,
            reason=reason,
            timestamp=time.time(),
        )
        self._migrations.append(record)
        self._stats["migrations"] += 1

        logger.info("会话 %s 已从 %s 迁移到 %s", session_id, from_agent, to_agent)

        return {
            "migrated": True,
            "session_id": session_id,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "migration_id": record.id,
        }

    def get_migration_history(self, limit: int = 20) -> list[dict]:
        return [
            {
                "id": r.id,
                "session_id": r.session_id,
                "from_agent": r.from_agent,
                "to_agent": r.to_agent,
                "reason": r.reason,
                "timestamp": r.timestamp,
            }
            for r in self._migrations[-limit:]
        ]

    # ----------------------------------------------------------
    # 统计
    # ----------------------------------------------------------

    def get_statistics(self) -> dict:
        return {
            "agents_registered": len(self._agents),
            "agents_healthy": sum(1 for a in self._agents.values() if a.is_healthy),
            "routing_rules": len(self._routing_rules),
            "affinity_entries": len(self._affinity),
            "active_sessions": len(self._session_agents),
            "total_routed": self._stats["routed"],
            "total_failed": self._stats["failed"],
            "total_migrations": self._stats["migrations"],
            "current_sequence": self._serializer.get_sequence(),
            "pending_messages": len(self._serializer._pending),
            "dead_letters": len(self._dead_letters),
        }

    def get_session_agent(self, session_id: str) -> Optional[str]:
        """获取会话绑定的 Agent"""
        return self._session_agents.get(session_id)

    def get_agent_sessions(self, agent_id: str) -> list[str]:
        """获取 Agent 下的所有会话"""
        return [sid for sid, aid in self._session_agents.items() if aid == agent_id]


# 全局实例
_multi_agent_routing_service: Optional[MultiAgentRoutingService] = None


def get_multi_agent_routing_service() -> MultiAgentRoutingService:
    global _multi_agent_routing_service
    if _multi_agent_routing_service is None:
        _multi_agent_routing_service = MultiAgentRoutingService()
    return _multi_agent_routing_service
