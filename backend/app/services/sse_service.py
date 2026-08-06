"""
SSE 实时推送服务

功能:
- Server-Sent Events 实时推送
- Token 使用量实时推送
- 告警实时推送
- 健康状态实时推送
- 客户端订阅管理
- 自动心跳保活
- 连接数限制
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Optional

logger = logging.getLogger(__name__)


@dataclass
class SSEClient:
    """SSE 客户端"""
    client_id: str = ""
    user_id: str = ""
    subscriptions: list[str] = field(default_factory=list)
    connected_at: Optional[datetime] = None
    last_heartbeat: float = 0
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)


class SSEService:
    """
    SSE 实时推送服务

    支持频道:
    - token: Token 使用量
    - alert: 告警通知
    - health: 健康状态
    - system: 系统事件
    - metrics: 性能指标
    """

    MAX_CLIENTS = 1000
    HEARTBEAT_INTERVAL = 30

    def __init__(self):
        self._clients: dict[str, SSEClient] = {}
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self):
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()

    # ----------------------------------------------------------
    # 客户端管理
    # ----------------------------------------------------------

    def connect(
        self,
        client_id: str,
        user_id: str = "",
        subscriptions: Optional[list[str]] = None,
    ) -> SSEClient:
        """注册 SSE 客户端"""
        if len(self._clients) >= self.MAX_CLIENTS:
            # 断开最旧连接
            oldest = min(self._clients.values(), key=lambda c: c.connected_at or datetime.max.replace(tzinfo=timezone.utc))
            self.disconnect(oldest.client_id)

        client = SSEClient(
            client_id=client_id,
            user_id=user_id,
            subscriptions=subscriptions or ["system"],
            connected_at=datetime.now(timezone.utc),
            last_heartbeat=time.time(),
        )
        self._clients[client_id] = client
        logger.debug(f"SSE client connected: {client_id}")
        return client

    def disconnect(self, client_id: str):
        """断开 SSE 客户端"""
        self._clients.pop(client_id, None)

    def subscribe(self, client_id: str, channels: list[str]):
        """订阅频道"""
        client = self._clients.get(client_id)
        if client:
            for ch in channels:
                if ch not in client.subscriptions:
                    client.subscriptions.append(ch)

    def unsubscribe(self, client_id: str, channels: list[str]):
        """取消订阅"""
        client = self._clients.get(client_id)
        if client:
            client.subscriptions = [ch for ch in client.subscriptions if ch not in channels]

    # ----------------------------------------------------------
    # 事件流
    # ----------------------------------------------------------

    async def event_stream(
        self,
        client_id: str,
    ) -> AsyncGenerator[str, None]:
        """生成 SSE 事件流"""
        client = self._clients.get(client_id)
        if not client:
            yield self._format_event("error", {"message": "Client not found"})
            return

        try:
            while True:
                try:
                    event_data = await asyncio.wait_for(
                        client.queue.get(), timeout=self.HEARTBEAT_INTERVAL
                    )
                    yield self._format_event(
                        event_data.get("type", "message"),
                        event_data.get("data", {}),
                    )
                except asyncio.TimeoutError:
                    # 心跳保活
                    yield self._format_event("heartbeat", {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "connected_clients": len(self._clients),
                    })
        except asyncio.CancelledError:
            pass
        except Exception as e:
            yield self._format_event("error", {"message": str(e)})

    # ----------------------------------------------------------
    # 推送
    # ----------------------------------------------------------

    async def publish(
        self,
        channel: str,
        event_type: str,
        data: dict[str, Any],
        user_id: Optional[str] = None,
    ):
        """发布事件到频道"""
        event = {
            "type": event_type,
            "data": {
                **data,
                "channel": channel,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

        sent = 0
        for client in self._clients.values():
            if channel not in client.subscriptions:
                continue
            if user_id and client.user_id != user_id:
                continue
            try:
                client.queue.put_nowait(event)
                sent += 1
            except asyncio.QueueFull:
                logger.warning(f"Queue full for client {client.client_id}")

        logger.debug(f"SSE published: {channel}/{event_type} → {sent} clients")

    async def publish_token_usage(self, data: dict[str, Any]):
        """推送 Token 使用量"""
        await self.publish("token", "usage_update", data)

    async def publish_alert(self, data: dict[str, Any]):
        """推送告警"""
        await self.publish("alert", "new_alert", data)

    async def publish_health(self, data: dict[str, Any]):
        """推送健康状态"""
        await self.publish("health", "health_update", data)

    async def publish_system_event(self, data: dict[str, Any]):
        """推送系统事件"""
        await self.publish("system", "system_event", data)

    async def publish_metrics(self, data: dict[str, Any]):
        """推送性能指标"""
        await self.publish("metrics", "metrics_update", data)

    # ----------------------------------------------------------
    # 心跳
    # ----------------------------------------------------------

    async def _heartbeat_loop(self):
        """心跳保活循环"""
        try:
            while self._running:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                now = time.time()
                disconnected = []
                for cid, client in self._clients.items():
                    if now - client.last_heartbeat > self.HEARTBEAT_INTERVAL * 3:
                        disconnected.append(cid)
                for cid in disconnected:
                    self.disconnect(cid)
                    logger.debug(f"SSE client timeout: {cid}")
        except asyncio.CancelledError:
            pass

    # ----------------------------------------------------------
    # 工具
    # ----------------------------------------------------------

    @staticmethod
    def _format_event(event_type: str, data: dict[str, Any]) -> str:
        """格式化 SSE 事件"""
        payload = json.dumps(data, ensure_ascii=False, default=str)
        return f"event: {event_type}\ndata: {payload}\n\n"

    def get_stats(self) -> dict[str, Any]:
        channel_counts = {}
        for client in self._clients.values():
            for ch in client.subscriptions:
                channel_counts[ch] = channel_counts.get(ch, 0) + 1
        return {
            "connected_clients": len(self._clients),
            "max_clients": self.MAX_CLIENTS,
            "channel_subscriptions": channel_counts,
        }
