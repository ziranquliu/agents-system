"""
Agent SDK — Agent 端自动上报

功能:
- Agent 启动/停止事件上报
- 心跳上报（周期性）
- 调用指标上报（请求量/延迟/Token/错误）
- 健康状态上报
- 日志上报（批量缓冲）
- 自动重连（断线重连）
- 批量上报（减少网络开销）
"""

import asyncio
import json
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ReportEventType(str, Enum):
    AGENT_START = "agent.start"
    AGENT_STOP = "agent.stop"
    HEARTBEAT = "agent.heartbeat"
    METRICS = "agent.metrics"
    HEALTH = "agent.health"
    LOG = "agent.log"
    ERROR = "agent.error"
    TOOL_CALL = "agent.tool_call"
    LLM_CALL = "agent.llm_call"


class AgentStatus(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class AgentConfig:
    """Agent 配置"""
    agent_id: str = ""
    agent_name: str = ""
    server_url: str = ""        # 上报目标 URL
    api_key: str = ""           # 认证密钥
    heartbeat_interval: int = 30  # 心跳间隔（秒）
    batch_size: int = 50         # 批量上报大小
    flush_interval: int = 10     # 刷新间隔（秒）
    max_retries: int = 3         # 最大重试次数
    retry_delay: float = 1.0     # 重试延迟（秒）
    enable_auto_report: bool = True
    workspace_id: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class MetricsData:
    """指标数据"""
    request_count: int = 0
    success_count: int = 0
    error_count: int = 0
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_duration_ms: float = 0
    avg_duration_ms: float = 0
    p99_duration_ms: float = 0
    last_request_time: Optional[datetime] = None


@dataclass
class ReportEvent:
    """上报事件"""
    id: str = ""
    event_type: str = ""
    agent_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[datetime] = None
    retry_count: int = 0

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "agent_id": self.agent_id,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class AgentSDK:
    """
    Agent SDK — 自动上报客户端

    使用方式:
    ```python
    sdk = AgentSDK(config)
    await sdk.start()

    # 自动上报调用指标
    sdk.record_llm_call(model="gpt-4o", tokens=500, duration_ms=1200)

    # 手动上报
    await sdk.report_event(ReportEventType.HEALTH, {"score": 85})

    await sdk.stop()
    ```
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self._status = AgentStatus.STOPPED
        self._buffer: deque[ReportEvent] = deque(maxlen=10000)
        self._metrics = MetricsData()
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._flush_task: Optional[asyncio.Task] = None
        self._heartbeat_count = 0
        self._start_time: Optional[float] = None

    async def start(self):
        """启动 SDK"""
        if self._status == AgentStatus.RUNNING:
            return

        self._status = AgentStatus.STARTING
        self._start_time = time.time()

        # 上报启动事件
        await self.report_event(ReportEventType.AGENT_START, {
            "agent_name": self.config.agent_name,
            "workspace_id": self.config.workspace_id,
            "tags": self.config.tags,
        })

        # 启动后台任务
        if self.config.enable_auto_report:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self._flush_task = asyncio.create_task(self._flush_loop())

        self._status = AgentStatus.RUNNING
        logger.info(f"Agent SDK started: {self.config.agent_id}")

    async def stop(self):
        """停止 SDK"""
        if self._status == AgentStatus.STOPPED:
            return

        self._status = AgentStatus.STOPPING

        # 取消后台任务
        for task in [self._heartbeat_task, self._flush_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # 上报停止事件
        await self.report_event(ReportEventType.AGENT_STOP, {
            "uptime_seconds": time.time() - self._start_time if self._start_time else 0,
            "total_heartbeats": self._heartbeat_count,
        })

        # 最后一次刷新缓冲区
        await self._flush_buffer()

        self._status = AgentStatus.STOPPED
        logger.info(f"Agent SDK stopped: {self.config.agent_id}")

    # ----------------------------------------------------------
    # 指标记录
    # ----------------------------------------------------------

    def record_llm_call(
        self,
        model: str = "",
        provider: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        duration_ms: float = 0,
        success: bool = True,
        error: str = "",
    ):
        """记录 LLM 调用"""
        self._metrics.request_count += 1
        self._metrics.total_tokens += input_tokens + output_tokens
        self._metrics.input_tokens += input_tokens
        self._metrics.output_tokens += output_tokens
        self._metrics.total_duration_ms += duration_ms
        self._metrics.last_request_time = datetime.now(timezone.utc)

        if success:
            self._metrics.success_count += 1
        else:
            self._metrics.error_count += 1

        # 更新平均延迟
        n = self._metrics.request_count
        self._metrics.avg_duration_ms = self._metrics.total_duration_ms / n if n > 0 else 0

        # 异步上报（不阻塞调用者）
        event = ReportEvent(
            event_type=ReportEventType.LLM_CALL.value,
            agent_id=self.config.agent_id,
            payload={
                "model": model,
                "provider": provider,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "duration_ms": duration_ms,
                "success": success,
                "error": error,
            },
        )
        self._buffer.append(event)

    def record_tool_call(
        self,
        tool_name: str,
        duration_ms: float = 0,
        success: bool = True,
        error: str = "",
    ):
        """记录工具调用"""
        event = ReportEvent(
            event_type=ReportEventType.TOOL_CALL.value,
            agent_id=self.config.agent_id,
            payload={
                "tool_name": tool_name,
                "duration_ms": duration_ms,
                "success": success,
                "error": error,
            },
        )
        self._buffer.append(event)

    def record_error(self, error_type: str, message: str, stack: str = ""):
        """记录错误"""
        self._metrics.error_count += 1
        event = ReportEvent(
            event_type=ReportEventType.ERROR.value,
            agent_id=self.config.agent_id,
            payload={
                "error_type": error_type,
                "message": message,
                "stack": stack,
            },
        )
        self._buffer.append(event)

    async def report_event(
        self,
        event_type: ReportEventType,
        payload: dict[str, Any],
    ):
        """手动上报事件"""
        event = ReportEvent(
            event_type=event_type.value,
            agent_id=self.config.agent_id,
            payload=payload,
        )
        self._buffer.append(event)

        # 高优先级事件立即发送
        if event_type in (ReportEventType.AGENT_START, ReportEventType.AGENT_STOP, ReportEventType.ERROR):
            await self._flush_buffer()

    # ----------------------------------------------------------
    # 后台任务
    # ----------------------------------------------------------

    async def _heartbeat_loop(self):
        """心跳上报循环"""
        try:
            while self._status == AgentStatus.RUNNING:
                await asyncio.sleep(self.config.heartbeat_interval)
                self._heartbeat_count += 1

                uptime = time.time() - self._start_time if self._start_time else 0

                event = ReportEvent(
                    event_type=ReportEventType.HEARTBEAT.value,
                    agent_id=self.config.agent_id,
                    payload={
                        "heartbeat_count": self._heartbeat_count,
                        "uptime_seconds": uptime,
                        "status": self._status.value,
                        "buffer_size": len(self._buffer),
                        "metrics_summary": {
                            "request_count": self._metrics.request_count,
                            "error_count": self._metrics.error_count,
                            "total_tokens": self._metrics.total_tokens,
                        },
                    },
                )
                self._buffer.append(event)

        except asyncio.CancelledError:
            pass

    async def _flush_loop(self):
        """缓冲区刷新循环"""
        try:
            while self._status == AgentStatus.RUNNING:
                await asyncio.sleep(self.config.flush_interval)
                await self._flush_buffer()
        except asyncio.CancelledError:
            pass

    async def _flush_buffer(self):
        """刷新缓冲区（批量上报）"""
        if not self._buffer:
            return

        # 取出批次
        batch = []
        while self._buffer and len(batch) < self.config.batch_size:
            batch.append(self._buffer.popleft())

        if not batch:
            return

        # 构建上报数据
        payload = {
            "agent_id": self.config.agent_id,
            "events": [e.to_dict() for e in batch],
            "batch_size": len(batch),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 发送（重试机制）
        for attempt in range(self.config.max_retries):
            try:
                await self._send(payload)
                logger.debug(f"Flushed {len(batch)} events")
                return
            except Exception as e:
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Failed to flush {len(batch)} events after {self.config.max_retries} retries: {e}")
                    # 放回缓冲区
                    for event in reversed(batch):
                        self._buffer.appendleft(event)

    async def _send(self, payload: dict[str, Any]):
        """发送数据到服务器"""
        if not self.config.server_url:
            # 无服务器配置，仅日志输出
            logger.debug(f"SDK report (no server): {len(payload.get('events', []))} events")
            return

        import httpx
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{self.config.server_url}/api/v1/sdk/report",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()

    # ----------------------------------------------------------
    # 查询
    # ----------------------------------------------------------

    def get_metrics(self) -> dict[str, Any]:
        """获取当前指标"""
        return {
            "agent_id": self.config.agent_id,
            "status": self._status.value,
            "uptime_seconds": time.time() - self._start_time if self._start_time else 0,
            "heartbeat_count": self._heartbeat_count,
            "buffer_size": len(self._buffer),
            "metrics": {
                "request_count": self._metrics.request_count,
                "success_count": self._metrics.success_count,
                "error_count": self._metrics.error_count,
                "total_tokens": self._metrics.total_tokens,
                "input_tokens": self._metrics.input_tokens,
                "output_tokens": self._metrics.output_tokens,
                "avg_duration_ms": round(self._metrics.avg_duration_ms, 1),
            },
        }

    def get_status(self) -> str:
        return self._status.value
