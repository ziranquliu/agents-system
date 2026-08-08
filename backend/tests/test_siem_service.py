"""
SIEMService 测试 — Syslog格式化、消息缓冲、CEF/LEEF/JSON格式
"""
import json
import pytest
from datetime import datetime, timezone

from app.services.siem_service import (
    SIEMService,
    SIEMConfig,
    SIEMEvent,
    SyslogProtocol,
    OutputFormat,
)


# ============================================================
# 枚举测试
# ============================================================

class TestSyslogProtocol:
    def test_all_protocols(self):
        values = {p.value for p in SyslogProtocol}
        assert values == {"udp", "tcp"}


class TestOutputFormat:
    def test_all_formats(self):
        values = {f.value for f in OutputFormat}
        assert "syslog_rfc5424" in values
        assert "cef" in values
        assert "leef" in values
        assert "json" in values


# ============================================================
# SIEMConfig 测试
# ============================================================

class TestSIEMConfig:
    def test_default_config(self):
        config = SIEMConfig()
        assert config.host == "localhost"
        assert config.port == 514
        assert config.protocol == SyslogProtocol.UDP
        assert config.format == OutputFormat.JSON
        assert config.batch_size == 10
        assert config.enabled is False
        assert config.tls_enabled is False


class TestSIEMEvent:
    def test_default_event(self):
        event = SIEMEvent()
        assert event.hostname == "agent-system"
        assert event.facility == 16
        assert event.severity == 5
        assert event.details == {}


# ============================================================
# 消息格式化测试
# ============================================================

class TestSIEMFormatting:
    def setup_method(self):
        self.service = SIEMService()
        self.event = SIEMEvent(
            timestamp="2026-01-01T00:00:00Z",
            facility=16,
            severity=5,
            hostname="test-host",
            app_name="test-app",
            event_id="evt_001",
            event_type="login",
            operator_id="user1",
            action_type="authenticate",
            target_id="t1",
            result="success",
            details={"ip": "127.0.0.1"},
        )

    def test_format_json(self):
        config = SIEMConfig(format=OutputFormat.JSON)
        self.service._config = config
        msg = self.service._format_message(self.event)
        parsed = json.loads(msg)
        assert "event" in parsed
        assert parsed["event"]["eventId"] == "evt_001"
        assert parsed["event"]["eventType"] == "login"

    def test_format_cef(self):
        config = SIEMConfig(format=OutputFormat.CEF)
        self.service._config = config
        msg = self.service._format_message(self.event)
        assert msg.startswith("CEF:")
        assert "evt_001" in msg

    def test_format_leef(self):
        config = SIEMConfig(format=OutputFormat.LEEF)
        self.service._config = config
        msg = self.service._format_message(self.event)
        assert msg.startswith("LEEF:")
        assert "evt_001" in msg

    def test_format_rfc5424(self):
        config = SIEMConfig(format=OutputFormat.SYSLOG_RFC5424)
        self.service._config = config
        msg = self.service._format_message(self.event)
        assert "<133>" in msg
        assert "2026-01-01T00:00:00Z" in msg


# ============================================================
# 缓冲与发送测试
# ============================================================

class TestSIEMBuffering:
    def setup_method(self):
        self.service = SIEMService()

    def test_buffer_initial_empty(self):
        assert len(self.service._buffer) == 0

    def test_stats_initial(self):
        stats = self.service._stats
        assert stats["total_sent"] == 0
        assert stats["total_errors"] == 0


# ============================================================
# 初始化/关闭测试
# ============================================================

class TestSIEMLifecycle:
    @pytest.mark.asyncio
    async def test_initialize_disabled(self):
        service = SIEMService()
        config = SIEMConfig(enabled=False)
        await service.initialize(config)
        assert service._config == config
        assert service._running is False

    @pytest.mark.asyncio
    async def test_shutdown(self):
        service = SIEMService()
        config = SIEMConfig(enabled=False)
        await service.initialize(config)
        await service.shutdown()
        assert service._running is False

    @pytest.mark.asyncio
    async def test_send_event_disabled(self):
        service = SIEMService()
        config = SIEMConfig(enabled=False)
        await service.initialize(config)
        event = SIEMEvent(event_id="e1")
        await service.send_event(event)
        assert len(service._buffer) == 0  # disabled, not buffered

    @pytest.mark.asyncio
    async def test_send_audit_record_disabled(self):
        service = SIEMService()
        config = SIEMConfig(enabled=False)
        await service.initialize(config)
        await service.send_audit_record({"id": "r1", "action_type": "login"})
        assert len(service._buffer) == 0


# ============================================================
# Severity 映射测试
# ============================================================

class TestSeverityMapping:
    def setup_method(self):
        self.service = SIEMService()

    def test_success_severity(self):
        sev = self.service._severity_from_result("success")
        assert sev in range(0, 8)

    def test_failure_severity(self):
        sev = self.service._severity_from_result("failure")
        assert sev in range(0, 8)

    def test_unknown_severity(self):
        sev = self.service._severity_from_result("unknown")
        assert sev in range(0, 8)


# ============================================================
# 边界情况
# ============================================================

class TestSIEMEdgeCases:
    def test_format_with_no_details(self):
        service = SIEMService()
        event = SIEMEvent(event_id="e1", details={})
        config = SIEMConfig(format=OutputFormat.JSON)
        service._config = config
        msg = service._format_message(event)
        parsed = json.loads(msg)
        assert "event" in parsed

    def test_format_cef_with_long_name(self):
        service = SIEMService()
        event = SIEMEvent(event_id="e" * 200, details={})
        config = SIEMConfig(format=OutputFormat.CEF)
        service._config = config
        msg = service._format_message(event)
        assert "e" * 200 in msg
