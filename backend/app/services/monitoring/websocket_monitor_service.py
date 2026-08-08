"""
WebSocket 实时监控服务

功能:
- 实时指标推送 (CPU/内存/请求/错误)
- 通道订阅 (agent/session/system/custom)
- 心跳保活
- 连接管理 (max 2000 clients)
- 历史数据缓冲 (最近 5 分钟)
"""

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class MonitorChannel(str, Enum):
    AGENT = "agent"
    SESSION = "session"
    SYSTEM = "system"
    METRICS = "metrics"
    ALERT = "alert"
    CUSTOM = "custom"


@dataclass
class MonitorClient:
    """监控客户端"""
    client_id: str = ""
    channels: set = field(default_factory=set)
    connected_at: float = 0
    last_heartbeat: float = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricsSnapshot:
    """指标快照"""
    timestamp: float = 0
    cpu_percent: float = 0
    memory_percent: float = 0
    request_rate: float = 0
    error_rate: float = 0
    active_sessions: int = 0
    queue_depth: int = 0
    latency_p99: float = 0
    custom: dict[str, Any] = field(default_factory=dict)


@dataclass
class MonitorEvent:
    """监控事件"""
    channel: str = ""
    event_type: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0


class WebSocketMonitorService:
    """
    WebSocket 实时监控服务

    - 多通道订阅 (agent/session/system/metrics/alert/custom)
    - 心跳保活 (30s 间隔)
    - 历史数据缓冲 (5 分钟窗口, 10s 采样)
    - 自动清理断线客户端
    """

    MAX_CLIENTS = 2000
    HEARTBEAT_INTERVAL = 30
    HISTORY_DURATION = 300  # 5 分钟
    SAMPLE_INTERVAL = 10  # 10 秒采样

    def __init__(self):
        self._clients: dict[str, MonitorClient] = {}
        self._message_queue: dict[str, asyncio.Queue] = defaultdict(
            lambda: asyncio.Queue(maxsize=1000)
        )
        self._metrics_history: deque[MetricsSnapshot] = deque(
            maxlen=self.HISTORY_DURATION // self.SAMPLE_INTERVAL
        )
        self._event_history: deque[MonitorEvent] = deque(maxlen=500)
        self._custom_handlers: dict[str, Callable] = {}
        self._running = False
        self._tasks: list[asyncio.Task] = []

    # ----------------------------------------------------------
    # 连接管理
    # ----------------------------------------------------------

    async def connect(
        self, client_id: str, channels: list[str], metadata: Optional[dict] = None
    ) -> dict[str, Any]:
        """注册客户端"""
        if len(self._clients) >= self.MAX_CLIENTS:
            raise RuntimeError("已达最大连接数限制")

        client = MonitorClient(
            client_id=client_id,
            channels=set(channels),
            connected_at=time.time(),
            last_heartbeat=time.time(),
            metadata=metadata or {},
        )
        self._clients[client_id] = client

        logger.info("客户端 %s 已连接, 订阅通道: %s", client_id, channels)
        return {
            "client_id": client_id,
            "channels": channels,
            "heartbeat_interval": self.HEARTBEAT_INTERVAL,
            "connected_at": client.connected_at,
        }

    async def disconnect(self, client_id: str):
        """断开客户端"""
        if client_id in self._clients:
            del self._clients[client_id]
            logger.info("客户端 %s 已断开", client_id)

    async def heartbeat(self, client_id: str) -> bool:
        """心跳"""
        client = self._clients.get(client_id)
        if client:
            client.last_heartbeat = time.time()
            return True
        return False

    def get_client_count(self) -> int:
        return len(self._clients)

    def get_clients_by_channel(self, channel: str) -> list[str]:
        return [
            cid for cid, c in self._clients.items()
            if channel in c.channels
        ]

    # ----------------------------------------------------------
    # 事件推送
    # ----------------------------------------------------------

    async def publish(self, channel: str, event_type: str, data: dict[str, Any]):
        """发布事件到通道"""
        event = MonitorEvent(
            channel=channel,
            event_type=event_type,
            data=data,
            timestamp=time.time(),
        )
        self._event_history.append(event)

        target_clients = self.get_clients_by_channel(channel)
        target_clients += self.get_clients_by_channel("custom")

        for client_id in target_clients:
            queue = self._message_queue[client_id]
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("客户端 %s 消息队列已满, 丢弃事件", client_id)

    async def subscribe(self, client_id: str, channels: list[str]):
        """动态订阅通道"""
        client = self._clients.get(client_id)
        if client:
            client.channels.update(channels)

    async def unsubscribe(self, client_id: str, channels: list[str]):
        """取消订阅"""
        client = self._clients.get(client_id)
        if client:
            client.channels -= set(channels)

    # ----------------------------------------------------------
    # 消费者
    # ----------------------------------------------------------

    async def consume(self, client_id: str, timeout: float = 30) -> Optional[MonitorEvent]:
        """获取下一条事件"""
        queue = self._message_queue.get(client_id)
        if not queue:
            return None
        try:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def consume_all(self, client_id: str) -> list[MonitorEvent]:
        """获取所有待处理事件"""
        queue = self._message_queue.get(client_id)
        if not queue:
            return []
        events = []
        while not queue.empty():
            try:
                events.append(queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return events

    # ----------------------------------------------------------
    # 指标收集
    # ----------------------------------------------------------

    async def record_metrics(self, snapshot: MetricsSnapshot):
        """记录指标快照"""
        self._metrics_history.append(snapshot)

    async def get_metrics_history(
        self, duration_seconds: int = 300, channel: str = ""
    ) -> list[dict]:
        """获取历史指标"""
        cutoff = time.time() - duration_seconds
        history = [
            s for s in self._metrics_history if s.timestamp >= cutoff
        ]
        return [
            {
                "timestamp": s.timestamp,
                "cpu_percent": s.cpu_percent,
                "memory_percent": s.memory_percent,
                "request_rate": s.request_rate,
                "error_rate": s.error_rate,
                "active_sessions": s.active_sessions,
                "queue_depth": s.queue_depth,
                "latency_p99": s.latency_p99,
                "custom": s.custom,
            }
            for s in history
        ]

    async def get_current_metrics(self) -> Optional[dict]:
        """获取最新指标"""
        if not self._metrics_history:
            return None
        latest = self._metrics_history[-1]
        return {
            "timestamp": latest.timestamp,
            "cpu_percent": latest.cpu_percent,
            "memory_percent": latest.memory_percent,
            "request_rate": latest.request_rate,
            "error_rate": latest.error_rate,
            "active_sessions": latest.active_sessions,
            "queue_depth": latest.queue_depth,
            "latency_p99": latest.latency_p99,
        }

    # ----------------------------------------------------------
    # 事件历史
    # ----------------------------------------------------------

    def get_event_history(
        self, channel: str = "", event_type: str = "", limit: int = 100
    ) -> list[dict]:
        """查询事件历史"""
        events = list(self._event_history)
        if channel:
            events = [e for e in events if e.channel == channel]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return [
            {
                "channel": e.channel,
                "event_type": e.event_type,
                "data": e.data,
                "timestamp": e.timestamp,
            }
            for e in events[-limit:]
        ]

    # ----------------------------------------------------------
    # 后台任务
    # ----------------------------------------------------------

    async def start(self):
        """启动后台任务"""
        if self._running:
            return
        self._running = True
        self._tasks.append(asyncio.create_task(self._cleanup_loop()))
        self._tasks.append(asyncio.create_task(self._heartbeat_check_loop()))
        logger.info("WebSocket 监控服务已启动")

    async def stop(self):
        """停止后台任务"""
        self._running = False
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()
        logger.info("WebSocket 监控服务已停止")

    async def _cleanup_loop(self):
        """清理断线客户端"""
        while self._running:
            await asyncio.sleep(60)
            now = time.time()
            stale = [
                cid for cid, c in self._clients.items()
                if now - c.last_heartbeat > self.HEARTBEAT_INTERVAL * 3
            ]
            for cid in stale:
                await self.disconnect(cid)
                logger.info("清理超时客户端: %s", cid)

    async def _heartbeat_check_loop(self):
        """心跳检查"""
        while self._running:
            await asyncio.sleep(self.HEARTBEAT_INTERVAL)
            now = time.time()
            stale = [
                cid for cid, c in self._clients.items()
                if now - c.last_heartbeat > self.HEARTBEAT_INTERVAL * 2
            ]
            for cid in stale:
                await self.disconnect(cid)
                logger.info("心跳超时, 断开客户端: %s", cid)


# 全局实例
_ws_monitor_service: Optional[WebSocketMonitorService] = None


def get_ws_monitor_service() -> WebSocketMonitorService:
    global _ws_monitor_service
    if _ws_monitor_service is None:
        _ws_monitor_service = WebSocketMonitorService()
    return _ws_monitor_service
