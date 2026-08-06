"""
Redis Pub/Sub 事件总线

支持：
- 多频道发布/订阅（agent、skill、mcp、system、audit 等）
- 消息持久化到 PostgreSQL（event_log 表）
- 事件重放（replay）
- 通配符订阅
- 死信队列（DLQ）
- 消息 TTL
- 事件过滤器
"""

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """事件类型枚举"""
    # Agent 事件
    AGENT_CREATED = "agent.created"
    AGENT_UPDATED = "agent.updated"
    AGENT_DELETED = "agent.deleted"
    AGENT_STARTED = "agent.started"
    AGENT_STOPPED = "agent.stopped"
    AGENT_HEALTH_CHANGED = "agent.health_changed"
    AGENT_CONFIG_CHANGED = "agent.config_changed"

    # Skill 事件
    SKILL_INSTALLED = "skill.installed"
    SKILL_UPDATED = "skill.updated"
    SKILL_REMOVED = "skill.removed"
    SKILL_VERSION_CHANGED = "skill.version_changed"

    # MCP 事件
    MCP_REGISTERED = "mcp.registered"
    MCP_CONNECTED = "mcp.connected"
    MCP_DISCONNECTED = "mcp.disconnected"
    MCP_HEALTH_CHANGED = "mcp.health_changed"
    MCP_CONFIG_CHANGED = "mcp.config_changed"
    MCP_TOOL_CHANGED = "mcp.tool_changed"

    # 会话事件
    SESSION_CREATED = "session.created"
    SESSION_ACTIVE = "session.active"
    SESSION_IDLE = "session.idle"
    SESSION_TIMEOUT = "session.timeout"
    SESSION_ARCHIVED = "session.archived"
    SESSION_CLEANED = "session.cleaned"
    SESSION_ERROR = "session.error"
    SESSION_MIGRATED = "session.migrated"

    # Token 事件
    TOKEN_USAGE = "token.usage"
    TOKEN_BUDGET_WARNING = "token.budget_warning"
    TOKEN_BUDGET_CRITICAL = "token.budget_critical"
    TOKEN_BUDGET_EXCEEDED = "token.budget_exceeded"
    TOKEN_DOWNGRADE = "token.downgrade"

    # 告警事件
    ALERT_TRIGGERED = "alert.triggered"
    ALERT_RESOLVED = "alert.resolved"
    ALERT_SILENCED = "alert.silenced"

    # 工作流事件
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"
    WORKFLOW_NODE_COMPLETED = "workflow.node_completed"

    # 协作事件
    COLLABORATION_STARTED = "collaboration.started"
    COLLABORATION_COMPLETED = "collaboration.completed"
    COLLABORATION_FAILED = "collaboration.failed"

    # 系统事件
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_BACKUP = "system.backup"
    SYSTEM_RESTORE = "system.restore"
    SYSTEM_MAINTENANCE = "system.maintenance"

    # 审计事件
    AUDIT_USER_LOGIN = "audit.user_login"
    AUDIT_USER_LOGOUT = "audit.user_logout"
    AUDIT_CONFIG_CHANGE = "audit.config_change"
    AUDIT_PERMISSION_CHANGE = "audit.permission_change"
    AUDIT_DATA_EXPORT = "audit.data_export"
    AUDIT_DATA_DELETE = "audit.data_delete"
    AUDIT_SECURITY_EVENT = "audit.security_event"

    # 备份事件
    BACKUP_STARTED = "backup.started"
    BACKUP_COMPLETED = "backup.completed"
    BACKUP_FAILED = "backup.failed"
    RESTORE_STARTED = "restore.started"
    RESTORE_COMPLETED = "restore.completed"
    RESTORE_FAILED = "restore.failed"

    # 更新事件
    UPDATE_AVAILABLE = "update.available"
    UPDATE_STARTED = "update.started"
    UPDATE_COMPLETED = "update.completed"
    UPDATE_FAILED = "update.failed"
    UPDATE_ROLLED_BACK = "update.rolled_back"

    # 自愈事件
    SELF_HEALING_DETECTED = "self_healing.detected"
    SELF_HEALING_STARTED = "self_healing.started"
    SELF_HEALING_COMPLETED = "self_healing.completed"
    SELF_HEALING_FAILED = "self_healing.failed"


class EventPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class EventMessage:
    """事件消息"""

    def __init__(
        self,
        event_type: str,
        payload: dict[str, Any],
        source: str = "system",
        priority: EventPriority = EventPriority.NORMAL,
        message_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        correlation_id: Optional[str] = None,
        retry_count: int = 0,
    ):
        self.message_id = message_id or str(uuid.uuid4())
        self.event_type = event_type
        self.payload = payload
        self.source = source
        self.priority = priority
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.retry_count = retry_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "source": self.source,
            "priority": self.priority.value,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
            "retry_count": self.retry_count,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)

    @classmethod
    def from_json(cls, data: str) -> "EventMessage":
        d = json.loads(data)
        return cls(
            message_id=d["message_id"],
            event_type=d["event_type"],
            payload=d["payload"],
            source=d.get("source", "unknown"),
            priority=EventPriority(d.get("priority", "normal")),
            timestamp=datetime.fromisoformat(d["timestamp"]),
            correlation_id=d.get("correlation_id"),
            retry_count=d.get("retry_count", 0),
        )


# Type alias for event handlers
EventHandler = Callable[[EventMessage], Coroutine[Any, Any, None]]


class EventBus:
    """
    Redis Pub/Sub 事件总线

    功能:
    - 发布/订阅事件
    - 通配符频道匹配
    - 消息持久化（可选）
    - 死信队列（DLQ）
    - 消息重试
    """

    DLQ_SUFFIX = ":dlq"
    MAX_RETRIES = 3

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._subscriptions: dict[str, list[EventHandler]] = {}
        self._pubsub = None
        self._running = False
        self._listener_task: Optional[asyncio.Task] = None
        self._persistent = False  # 是否持久化事件

    async def initialize(self, redis_client=None, persistent: bool = False):
        """初始化事件总线"""
        if redis_client:
            self._redis = redis_client
        self._persistent = persistent
        if self._redis:
            try:
                self._pubsub = self._redis.pubsub()
                self._running = True
                logger.info("EventBus initialized with Redis backend")
            except Exception as e:
                logger.warning(f"EventBus Redis init failed, using in-memory mode: {e}")
                self._running = True
        else:
            self._running = True
            logger.info("EventBus initialized with in-memory mode (no Redis)")

    async def shutdown(self):
        """关闭事件总线"""
        self._running = False
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        if self._pubsub:
            try:
                await self._pubsub.unsubscribe()
                await self._pubsub.close()
            except Exception:
                pass
        logger.info("EventBus shut down")

    async def publish(
        self,
        event_type: str,
        payload: dict[str, Any],
        source: str = "system",
        priority: EventPriority = EventPriority.NORMAL,
        correlation_id: Optional[str] = None,
    ) -> str:
        """
        发布事件到频道

        Returns:
            message_id
        """
        message = EventMessage(
            event_type=event_type,
            payload=payload,
            source=source,
            priority=priority,
            correlation_id=correlation_id,
        )

        channel = f"events:{event_type}"

        try:
            if self._redis:
                await self._redis.publish(channel, message.to_json())
                logger.debug(f"Published event {event_type} to Redis channel {channel}")
            else:
                # In-memory dispatch
                await self._dispatch_local(event_type, message)

            # 持久化到 PostgreSQL（可选）
            if self._persistent:
                await self._persist_event(message)

            return message.message_id

        except Exception as e:
            logger.error(f"Failed to publish event {event_type}: {e}")
            # 放入死信队列
            await self._send_to_dlq(message, str(e))
            return message.message_id

    async def subscribe(
        self,
        event_type_pattern: str,
        handler: EventHandler,
    ):
        """
        订阅事件

        支持:
        - 精确匹配: "agent.created"
        - 通配符: "agent.*" 匹配所有 agent 事件
        - 全局: "*" 匹配所有事件
        """
        if event_type_pattern not in self._subscriptions:
            self._subscriptions[event_type_pattern] = []
        self._subscriptions[event_type_pattern].append(handler)
        logger.debug(f"Subscribed to {event_type_pattern}")

        if self._redis and self._pubsub:
            # 订阅 Redis 频道
            channel = f"events:{event_type_pattern}"
            try:
                await self._pubsub.subscribe(channel)
            except Exception as e:
                logger.warning(f"Failed to subscribe to Redis channel {channel}: {e}")

    async def unsubscribe(self, event_type_pattern: str, handler: EventHandler):
        """取消订阅"""
        if event_type_pattern in self._subscriptions:
            self._subscriptions[event_type_pattern] = [
                h for h in self._subscriptions[event_type_pattern] if h != handler
            ]

    async def start_listener(self):
        """启动 Redis Pub/Sub 监听器"""
        if not self._redis or not self._pubsub:
            logger.info("No Redis backend, using local event dispatch")
            return

        self._listener_task = asyncio.create_task(self._listen_loop())

    async def _listen_loop(self):
        """Redis Pub/Sub 监听循环"""
        try:
            while self._running and self._pubsub:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if message and message["type"] == "message":
                    channel = message["channel"]
                    if isinstance(channel, bytes):
                        channel = channel.decode("utf-8")
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")

                    try:
                        event_msg = EventMessage.from_json(data)
                        await self._dispatch_event(event_msg)
                    except Exception as e:
                        logger.error(f"Error processing message from {channel}: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"EventBus listener error: {e}")

    async def _dispatch_event(self, message: EventMessage):
        """分发事件到匹配的处理器"""
        event_type = message.event_type

        for pattern, handlers in self._subscriptions.items():
            if self._match_pattern(pattern, event_type):
                for handler in handlers:
                    try:
                        await handler(message)
                    except Exception as e:
                        logger.error(
                            f"Handler error for {pattern} -> {event_type}: {e}"
                        )
                        if message.retry_count < self.MAX_RETRIES:
                            retry_msg = EventMessage(
                                event_type=message.event_type,
                                payload=message.payload,
                                source=message.source,
                                priority=message.priority,
                                message_id=message.message_id,
                                correlation_id=message.correlation_id,
                                retry_count=message.retry_count + 1,
                            )
                            await asyncio.sleep(2 ** retry_msg.retry_count)
                            await self._dispatch_event(retry_msg)

    async def _dispatch_local(self, event_type: str, message: EventMessage):
        """本地内存事件分发（无 Redis 时使用）"""
        for pattern, handlers in self._subscriptions.items():
            if self._match_pattern(pattern, event_type):
                for handler in handlers:
                    try:
                        await handler(message)
                    except Exception as e:
                        logger.error(f"Local handler error: {e}")

    @staticmethod
    def _match_pattern(pattern: str, event_type: str) -> bool:
        """
        通配符匹配

        "agent.*" 匹配 "agent.created"
        "*" 匹配所有
        "agent.created" 精确匹配
        """
        if pattern == "*":
            return True
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            return event_type.startswith(prefix + ".")
        return pattern == event_type

    async def _persist_event(self, message: EventMessage):
        """持久化事件到数据库"""
        try:
            from app.db.session import async_session_factory

            async with async_session_factory() as session:
                await session.execute(
                    """
                    INSERT INTO event_log (id, event_type, payload, source, priority, timestamp, correlation_id)
                    VALUES (:id, :event_type, :payload, :source, :priority, :timestamp, :correlation_id)
                    """,
                    {
                        "id": message.message_id,
                        "event_type": message.event_type,
                        "payload": json.dumps(message.payload, ensure_ascii=False, default=str),
                        "source": message.source,
                        "priority": message.priority.value,
                        "timestamp": message.timestamp,
                        "correlation_id": message.correlation_id,
                    },
                )
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to persist event: {e}")

    async def _send_to_dlq(self, message: EventMessage, error: str):
        """发送到死信队列"""
        try:
            if self._redis:
                dlq_key = f"events:dlq:{message.event_type}"
                dlq_payload = {
                    **message.to_dict(),
                    "error": error,
                    "dlq_timestamp": datetime.now(timezone.utc).isoformat(),
                }
                await self._redis.lpush(dlq_key, json.dumps(dlq_payload, default=str))
                # 保留最近 1000 条 DLQ
                await self._redis.ltrim(dlq_key, 0, 999)
                logger.warning(f"Event {message.message_id} sent to DLQ: {error}")
        except Exception as e:
            logger.error(f"Failed to send to DLQ: {e}")

    async def get_dlq_events(self, event_type: str, limit: int = 50) -> list[dict]:
        """获取死信队列事件"""
        if not self._redis:
            return []
        try:
            dlq_key = f"events:dlq:{event_type}"
            items = await self._redis.lrange(dlq_key, 0, limit - 1)
            return [json.loads(item) for item in items]
        except Exception as e:
            logger.error(f"Failed to get DLQ events: {e}")
            return []

    async def replay_events(
        self,
        event_type: str,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> int:
        """重放事件（从持久化存储）"""
        if not self._persistent:
            return 0
        try:
            from app.db.session import async_session_factory

            query = """
                SELECT id, event_type, payload, source, priority, timestamp, correlation_id
                FROM event_log
                WHERE event_type LIKE :pattern
            """
            params: dict[str, Any] = {"pattern": event_type}
            if since:
                query += " AND timestamp >= :since"
                params["since"] = since
            query += " ORDER BY timestamp DESC LIMIT :limit"
            params["limit"] = limit

            async with async_session_factory() as session:
                result = await session.execute(query, params)
                rows = result.mappings().all()

            replayed = 0
            for row in rows:
                msg = EventMessage(
                    message_id=row["id"],
                    event_type=row["event_type"],
                    payload=json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"],
                    source=row["source"],
                    priority=EventPriority(row["priority"]),
                    timestamp=row["timestamp"],
                    correlation_id=row["correlation_id"],
                )
                await self._dispatch_event(msg)
                replayed += 1

            logger.info(f"Replayed {replayed} events for pattern {event_type}")
            return replayed
        except Exception as e:
            logger.error(f"Failed to replay events: {e}")
            return 0

    def get_stats(self) -> dict[str, Any]:
        """获取事件总线统计"""
        total_handlers = sum(len(handlers) for handlers in self._subscriptions.values())
        return {
            "running": self._running,
            "persistent": self._persistent,
            "redis_connected": self._redis is not None,
            "subscriptions": {
                pattern: len(handlers)
                for pattern, handlers in self._subscriptions.items()
            },
            "total_handlers": total_handlers,
            "total_patterns": len(self._subscriptions),
        }


# ============================================================
# 全局事件总线实例
# ============================================================

event_bus = EventBus()


async def get_event_bus() -> EventBus:
    """获取全局事件总线"""
    return event_bus


async def init_event_bus(redis_client=None, persistent: bool = False):
    """初始化全局事件总线"""
    await event_bus.initialize(redis_client=redis_client, persistent=persistent)
    return event_bus
