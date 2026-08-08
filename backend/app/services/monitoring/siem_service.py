"""
SIEM 集成服务 — Syslog 输出

功能:
- Syslog UDP/TCP 输出（RFC 5424 格式）
- 审计日志自动转发到 SIEM 系统（Splunk/QRadar/ArcSight）
- 批量缓冲与异步发送
- 连接健康检查
- 消息格式化（CEF/LEEF/JSON）
"""

import asyncio
import json
import logging
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SyslogProtocol(str, Enum):
    UDP = "udp"
    TCP = "tcp"


class OutputFormat(str, Enum):
    SYSLOG_RFC5424 = "syslog_rfc5424"
    CEF = "cef"           # Common Event Format (ArcSight)
    LEEF = "leef"         # Log Event Extended Format (QRadar)
    JSON = "json"          # Splunk HEC


@dataclass
class SIEMConfig:
    """SIEM 连接配置"""
    host: str = "localhost"
    port: int = 514
    protocol: SyslogProtocol = SyslogProtocol.UDP
    format: OutputFormat = OutputFormat.JSON
    facility: int = 16       # local0
    severity: int = 5        # notice
    hostname: str = "agent-system"
    app_name: str = "agent-system"
    batch_size: int = 10
    flush_interval: float = 5.0
    enabled: bool = False
    tls_enabled: bool = False
    token: str = ""          # Splunk HEC token


@dataclass
class SIEMEvent:
    """SIEM 事件"""
    timestamp: str = ""
    facility: int = 16
    severity: int = 5
    hostname: str = "agent-system"
    app_name: str = "agent-system"
    event_id: str = ""
    event_type: str = ""
    operator_id: str = ""
    action_type: str = ""
    target_id: str = ""
    result: str = ""
    details: dict[str, Any] = field(default_factory=dict)


class SIEMService:
    """
    SIEM 集成服务

    - Syslog UDP/TCP 输出（RFC 5424）
    - CEF/LEEF/JSON 格式
    - 批量缓冲与异步发送
    """

    def __init__(self):
        self._config: Optional[SIEMConfig] = None
        self._buffer: list[SIEMEvent] = []
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False
        self._stats = {
            "total_sent": 0,
            "total_errors": 0,
            "last_send_time": None,
        }
        self._sock: Optional[socket.socket] = None

    async def initialize(self, config: SIEMConfig):
        """初始化 SIEM 连接"""
        self._config = config
        if config.enabled:
            self._running = True
            self._flush_task = asyncio.create_task(self._flush_loop())
            logger.info(f"SIEM initialized: {config.host}:{config.port} ({config.protocol.value})")

    async def shutdown(self):
        """关闭 SIEM 连接"""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass

    # ----------------------------------------------------------
    # 事件发送
    # ----------------------------------------------------------

    async def send_event(self, event: SIEMEvent):
        """发送单个事件到 SIEM"""
        if not self._config or not self._config.enabled:
            return

        self._buffer.append(event)
        if len(self._buffer) >= self._config.batch_size:
            await self._flush_buffer()

    async def send_audit_record(self, record: dict[str, Any]):
        """从审计记录创建并发送 SIEM 事件"""
        event = SIEMEvent(
            timestamp=record.get("timestamp", datetime.now(timezone.utc).isoformat()),
            facility=self._config.facility if self._config else 16,
            severity=self._severity_from_result(record.get("result", "")),
            hostname=self._config.hostname if self._config else "agent-system",
            event_id=record.get("id", ""),
            event_type=record.get("action_type", ""),
            operator_id=record.get("operator_id", ""),
            action_type=record.get("action_type", ""),
            target_id=record.get("target_id", ""),
            result=record.get("result", ""),
            details=record.get("details", {}),
        )
        await self.send_event(event)

    async def _flush_buffer(self):
        """刷新缓冲区"""
        if not self._buffer or not self._config:
            return

        events = self._buffer.copy()
        self._buffer.clear()

        try:
            for event in events:
                message = self._format_message(event)
                await self._send_syslog(message)
                self._stats["total_sent"] += 1
            self._stats["last_send_time"] = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            self._stats["total_errors"] += 1
            logger.error(f"SIEM send failed: {e}")

    async def _flush_loop(self):
        """定时刷新"""
        try:
            while self._running:
                await asyncio.sleep(self._config.flush_interval)
                await self._flush_buffer()
        except asyncio.CancelledError:
            pass

    # ----------------------------------------------------------
    # 消息格式化
    # ----------------------------------------------------------

    def _format_message(self, event: SIEMEvent) -> str:
        """格式化消息"""
        fmt = self._config.format if self._config else OutputFormat.JSON

        if fmt == OutputFormat.JSON:
            return self._format_json(event)
        elif fmt == OutputFormat.CEF:
            return self._format_cef(event)
        elif fmt == OutputFormat.LEEF:
            return self._format_leef(event)
        else:
            return self._format_rfc5424(event)

    def _format_rfc5424(self, event: SIEMEvent) -> str:
        """RFC 5424 Syslog 格式"""
        pri = event.facility * 8 + event.severity
        return (
            f"<{pri}>1 {event.timestamp} {event.hostname} "
            f"{event.app_name} - - - "
            f"{json.dumps(self._common_fields(event), ensure_ascii=False)}"
        )

    def _format_json(self, event: SIEMEvent) -> str:
        """JSON 格式（Splunk HEC）"""
        payload = {
            "time": event.timestamp,
            "host": event.hostname,
            "source": event.app_name,
            "sourcetype": "audit",
            "event": {
                **self._common_fields(event),
            },
        }
        if self._config and self._config.token:
            payload["token"] = self._config.token
        return json.dumps(payload, ensure_ascii=False, default=str)

    def _format_cef(self, event: SIEMEvent) -> str:
        """CEF (Common Event Format)"""
        fields = self._common_fields(event)
        kv = " ".join(f"{k}={v}" for k, v in fields.items())
        return (
            f"CEF:0|AgentSystem|AgentSystem|1.0|"
            f"{event.event_type}|{event.action_type}|{event.severity}|"
            f"{kv}"
        )

    def _format_leef(self, event: SIEMEvent) -> str:
        """LEEF (Log Event Extended Format)"""
        fields = self._common_fields(event)
        kv = "\t".join(f"{k}={v}" for k, v in fields.items())
        return f"LEEF:2.0|AgentSystem|AgentSystem|1.0|{event.event_type}|{kv}"

    @staticmethod
    def _common_fields(event: SIEMEvent) -> dict[str, Any]:
        return {
            "eventId": event.event_id,
            "eventType": event.event_type,
            "operatorId": event.operator_id,
            "action": event.action_type,
            "targetId": event.target_id,
            "result": event.result,
            "details": event.details,
        }

    @staticmethod
    def _severity_from_result(result: str) -> int:
        if result == "failure":
            return 3  # error
        elif result == "denied":
            return 1  # critical
        return 5  # notice

    # ----------------------------------------------------------
    # 网络发送
    # ----------------------------------------------------------

    async def _send_syslog(self, message: str):
        """发送 Syslog 消息"""
        if not self._config:
            return

        try:
            if self._config.protocol == SyslogProtocol.UDP:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.sendto(message.encode("utf-8"), (self._config.host, self._config.port))
                sock.close()
            else:
                # TCP
                reader, writer = await asyncio.open_connection(
                    self._config.host, self._config.port
                )
                writer.write(message.encode("utf-8") + b"\n")
                await writer.drain()
                writer.close()
                await writer.wait_closed()
        except Exception as e:
            logger.error(f"Syslog send error: {e}")
            raise

    # ----------------------------------------------------------
    # 健康检查
    # ----------------------------------------------------------

    async def health_check(self) -> dict[str, Any]:
        """检查 SIEM 连接健康状态"""
        if not self._config:
            return {"status": "not_configured"}

        try:
            if self._config.protocol == SyslogProtocol.UDP:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(3)
                sock.connect((self._config.host, self._config.port))
                sock.close()
                return {"status": "healthy", "protocol": "udp"}
            else:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self._config.host, self._config.port),
                    timeout=3,
                )
                writer.close()
                await writer.wait_closed()
                return {"status": "healthy", "protocol": "tcp"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def get_stats(self) -> dict[str, Any]:
        return {**self._stats, "buffer_size": len(self._buffer)}
