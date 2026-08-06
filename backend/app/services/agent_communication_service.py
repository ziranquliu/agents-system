"""
Agent 间通信协议 — JSON-RPC / Event / Shared Blackboard

功能:
- JSON-RPC: 请求/响应式同步通信
- Event Bus: 异步事件驱动通信
- Shared Blackboard: 共享黑板（共享数据空间）
- 消息队列（FIFO）
- 通信审计
"""

import json
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)


class CommunicationProtocol(str, Enum):
    JSON_RPC = "json_rpc"
    EVENT = "event"
    BLACKBOARD = "blackboard"


class MessageStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    PROCESSED = "processed"
    FAILED = "failed"


@dataclass
class RPCRequest:
    """JSON-RPC 请求"""
    id: str = ""
    method: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    from_agent: str = ""
    to_agent: str = ""
    timeout_seconds: float = 30.0
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc)

    def to_jsonrpc(self) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": self.id,
            "method": self.method,
            "params": {**self.params, "_from": self.from_agent, "_to": self.to_agent},
        }


@dataclass
class RPCResponse:
    """JSON-RPC 响应"""
    id: str = ""
    result: Any = None
    error: Optional[dict[str, Any]] = None
    from_agent: str = ""
    to_agent: str = ""
    duration_ms: float = 0
    timestamp: Optional[datetime] = None

    def to_jsonrpc(self) -> dict[str, Any]:
        resp = {"jsonrpc": "2.0", "id": self.id}
        if self.error:
            resp["error"] = self.error
        else:
            resp["result"] = self.result
        return resp


@dataclass
class BlackboardEntry:
    """黑板条目"""
    key: str = ""
    value: Any = None
    agent_id: str = ""
    version: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CommunicationRecord:
    """通信记录"""
    id: str = ""
    protocol: str = ""
    from_agent: str = ""
    to_agent: str = ""
    method: str = ""
    status: str = ""
    duration_ms: float = 0
    timestamp: Optional[datetime] = None
    error_message: str = ""


class AgentCommunicationService:
    """
    Agent 间通信协议

    三种通信方式:
    1. JSON-RPC: 同步请求/响应
    2. Event: 异步事件驱动
    3. Blackboard: 共享数据空间
    """

    def __init__(self):
        # JSON-RPC handlers
        self._rpc_handlers: dict[str, dict[str, Callable]] = defaultdict(dict)  # agent_id → method → handler
        self._pending_rpcs: dict[str, RPCRequest] = {}

        # Event subscriptions
        self._event_handlers: dict[str, list[Callable]] = defaultdict(list)

        # Blackboard
        self._blackboard: dict[str, BlackboardEntry] = {}
        self._blackboard_watchers: dict[str, list[str]] = defaultdict(list)  # key → [agent_ids]

        # 通信记录
        self._records: list[CommunicationRecord] = []

    # ----------------------------------------------------------
    # JSON-RPC 通信
    # ----------------------------------------------------------

    def register_rpc_handler(
        self,
        agent_id: str,
        method: str,
        handler: Callable,
    ):
        """注册 RPC 方法处理器"""
        self._rpc_handlers[agent_id][method] = handler
        logger.debug(f"RPC handler registered: {agent_id}.{method}")

    async def rpc_call(
        self,
        from_agent: str,
        to_agent: str,
        method: str,
        params: Optional[dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> RPCResponse:
        """
        发送 JSON-RPC 调用

        同步等待响应
        """
        request = RPCRequest(
            method=method,
            params=params or {},
            from_agent=from_agent,
            to_agent=to_agent,
            timeout_seconds=timeout,
        )

        record = CommunicationRecord(
            id=request.id,
            protocol=CommunicationProtocol.JSON_RPC.value,
            from_agent=from_agent,
            to_agent=to_agent,
            method=method,
            status="pending",
            timestamp=datetime.now(timezone.utc),
        )

        start_time = datetime.now(timezone.utc)

        try:
            handler = self._rpc_handlers.get(to_agent, {}).get(method)
            if not handler:
                error_resp = RPCResponse(
                    id=request.id,
                    error={"code": -32601, "message": f"Method not found: {method}"},
                    from_agent=to_agent,
                    to_agent=from_agent,
                )
                record.status = "failed"
                record.error_message = f"Method not found: {method}"
                self._records.append(record)
                return error_resp

            # 执行 handler
            result = await handler(params or {})
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            response = RPCResponse(
                id=request.id,
                result=result,
                from_agent=to_agent,
                to_agent=from_agent,
                duration_ms=elapsed,
            )
            record.status = "processed"
            record.duration_ms = elapsed

        except Exception as e:
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            response = RPCResponse(
                id=request.id,
                error={"code": -32000, "message": str(e)},
                from_agent=to_agent,
                to_agent=from_agent,
                duration_ms=elapsed,
            )
            record.status = "failed"
            record.error_message = str(e)

        self._records.append(record)
        return response

    # ----------------------------------------------------------
    # Event 通信
    # ----------------------------------------------------------

    def subscribe_event(self, agent_id: str, event_type: str, handler: Callable):
        """订阅事件"""
        key = f"{event_type}"
        self._event_handlers[key].append(handler)
        logger.debug(f"Event subscribed: {agent_id} → {event_type}")

    async def publish_event(
        self,
        from_agent: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> int:
        """发布事件"""
        handler_count = 0
        for handler in self._event_handlers.get(event_type, []):
            try:
                await handler({
                    "event_type": event_type,
                    "from_agent": from_agent,
                    "payload": payload,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                handler_count += 1
            except Exception as e:
                logger.error(f"Event handler error: {e}")

        record = CommunicationRecord(
            id=str(uuid.uuid4()),
            protocol=CommunicationProtocol.EVENT.value,
            from_agent=from_agent,
            to_agent="*",
            method=event_type,
            status="processed" if handler_count > 0 else "no_handlers",
            timestamp=datetime.now(timezone.utc),
        )
        self._records.append(record)
        return handler_count

    # ----------------------------------------------------------
    # Shared Blackboard
    # ----------------------------------------------------------

    def blackboard_write(
        self,
        agent_id: str,
        key: str,
        value: Any,
        metadata: Optional[dict[str, Any]] = None,
    ) -> BlackboardEntry:
        """写入黑板"""
        existing = self._blackboard.get(key)
        version = (existing.version + 1) if existing else 1

        entry = BlackboardEntry(
            key=key,
            value=value,
            agent_id=agent_id,
            version=version,
            created_at=existing.created_at if existing else datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
        self._blackboard[key] = entry

        # 通知 watchers
        watchers = self._blackboard_watchers.get(key, [])
        logger.debug(f"Blackboard write: {key} by {agent_id} (v{version}), {len(watchers)} watchers")

        record = CommunicationRecord(
            id=str(uuid.uuid4()),
            protocol=CommunicationProtocol.BLACKBOARD.value,
            from_agent=agent_id,
            to_agent="blackboard",
            method=f"write:{key}",
            status="processed",
            timestamp=datetime.now(timezone.utc),
        )
        self._records.append(record)

        return entry

    def blackboard_read(self, key: str) -> Optional[BlackboardEntry]:
        """读取黑板"""
        return self._blackboard.get(key)

    def blackboard_read_all(self, prefix: str = "") -> dict[str, Any]:
        """读取所有黑板条目（可选前缀过滤）"""
        if prefix:
            return {
                k: {"value": v.value, "agent_id": v.agent_id, "version": v.version}
                for k, v in self._blackboard.items()
                if k.startswith(prefix)
            }
        return {
            k: {"value": v.value, "agent_id": v.agent_id, "version": v.version}
            for k, v in self._blackboard.items()
        }

    def blackboard_watch(self, agent_id: str, key: str):
        """关注黑板键"""
        if agent_id not in self._blackboard_watchers[key]:
            self._blackboard_watchers[key].append(agent_id)

    def blackboard_unwatch(self, agent_id: str, key: str):
        """取消关注"""
        if agent_id in self._blackboard_watchers[key]:
            self._blackboard_watchers[key].remove(agent_id)

    def blackboard_delete(self, key: str) -> bool:
        """删除黑板条目"""
        if key in self._blackboard:
            del self._blackboard[key]
            return True
        return False

    def blackboard_list_keys(self, prefix: str = "") -> list[str]:
        """列出黑板键"""
        keys = list(self._blackboard.keys())
        if prefix:
            keys = [k for k in keys if k.startswith(prefix)]
        return sorted(keys)

    # ----------------------------------------------------------
    # 查询与审计
    # ----------------------------------------------------------

    def get_communication_history(
        self,
        agent_id: Optional[str] = None,
        protocol: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        records = self._records
        if agent_id:
            records = [r for r in records if r.from_agent == agent_id or r.to_agent == agent_id]
        if protocol:
            records = [r for r in records if r.protocol == protocol]
        return [
            {
                "id": r.id, "protocol": r.protocol,
                "from_agent": r.from_agent, "to_agent": r.to_agent,
                "method": r.method, "status": r.status,
                "duration_ms": round(r.duration_ms, 1),
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "error_message": r.error_message,
            }
            for r in records[-limit:]
        ]

    def get_stats(self) -> dict[str, Any]:
        total = len(self._records)
        by_protocol = {}
        for r in self._records:
            by_protocol[r.protocol] = by_protocol.get(r.protocol, 0) + 1

        return {
            "total_communications": total,
            "by_protocol": by_protocol,
            "blackboard_keys": len(self._blackboard),
            "rpc_handlers": sum(len(h) for h in self._rpc_handlers.values()),
            "event_subscriptions": sum(len(h) for h in self._event_handlers.values()),
        }
