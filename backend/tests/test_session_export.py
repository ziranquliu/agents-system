"""
SessionExportService 测试 — Markdown/JSON/CSV/PDF导出、历史记录
"""
import json
import pytest
from unittest.mock import AsyncMock

from app.services.session_export_service import (
    SessionExportService,
    ExportRequest,
    ExportResult,
    ExportFormat,
    ExportStatus,
)


# ============================================================
# 枚举测试
# ============================================================

class TestExportFormat:
    def test_all_formats(self):
        values = {f.value for f in ExportFormat}
        assert values == {"markdown", "json", "pdf", "csv"}


class TestExportStatus:
    def test_all_statuses(self):
        values = {s.value for s in ExportStatus}
        assert values == {"pending", "processing", "completed", "failed"}


# ============================================================
# ExportRequest 测试
# ============================================================

class TestExportRequest:
    def test_default_request(self):
        req = ExportRequest()
        assert req.id != ""
        assert req.format == ExportFormat.MARKDOWN
        assert req.include_metadata is True

    def test_custom_request(self):
        req = ExportRequest(
            session_ids=["s1", "s2"],
            format=ExportFormat.JSON,
            user_id="u1",
        )
        assert len(req.session_ids) == 2
        assert req.format == ExportFormat.JSON


# ============================================================
# ExportResult 测试
# ============================================================

class TestExportResult:
    def test_default_result(self):
        result = ExportResult()
        assert result.status == ExportStatus.PENDING
        assert result.file_size == 0

    def test_to_dict(self):
        result = ExportResult(
            id="r1", request_id="req1",
            status=ExportStatus.COMPLETED,
            format=ExportFormat.MARKDOWN,
            file_name="export.md", file_size=1024,
            session_count=2, message_count=10,
        )
        d = result.to_dict()
        assert d["status"] == "completed"
        assert d["format"] == "markdown"
        assert d["file_size"] == 1024


# ============================================================
# 导出格式测试
# ============================================================

class TestSessionExportMarkdown:
    def setup_method(self):
        self.service = SessionExportService()

    @pytest.mark.asyncio
    async def test_export_markdown_basic(self):
        sessions = [{
            "id": "s1",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ],
            "metadata": {"agent_id": "a1"},
        }]
        result = await self.service.export_sessions(
            ["s1"], ExportFormat.MARKDOWN, sessions_data=sessions
        )
        assert result.status == ExportStatus.COMPLETED
        assert "# 对话导出" in result.file_content
        assert "会话 s1" in result.file_content
        assert "Hello" in result.file_content
        assert result.file_name.endswith(".md")
        assert result.file_size > 0

    @pytest.mark.asyncio
    async def test_export_markdown_no_metadata(self):
        sessions = [{
            "id": "s1",
            "messages": [{"role": "user", "content": "Q"}],
            "metadata": {"agent_id": "a1"},
        }]
        result = await self.service.export_sessions(
            ["s1"], ExportFormat.MARKDOWN,
            sessions_data=sessions, include_metadata=False
        )
        assert "agent_id" not in result.file_content

    @pytest.mark.asyncio
    async def test_export_markdown_empty_session(self):
        sessions = [{"id": "s1", "messages": [], "metadata": {}}]
        result = await self.service.export_sessions(["s1"], ExportFormat.MARKDOWN, sessions_data=sessions)
        assert result.status == ExportStatus.COMPLETED
        assert result.message_count == 0


class TestSessionExportJSON:
    def setup_method(self):
        self.service = SessionExportService()

    @pytest.mark.asyncio
    async def test_export_json_basic(self):
        sessions = [{
            "id": "s1",
            "messages": [{"role": "user", "content": "Q"}],
            "metadata": {},
        }]
        result = await self.service.export_sessions(
            ["s1"], ExportFormat.JSON, sessions_data=sessions
        )
        assert result.status == ExportStatus.COMPLETED
        assert result.file_name.endswith(".json")
        parsed = json.loads(result.file_content)
        assert "sessions" in parsed
        assert len(parsed["sessions"]) == 1

    @pytest.mark.asyncio
    async def test_export_json_structure(self):
        sessions = [{"id": "s1", "messages": [], "metadata": {"key": "val"}}]
        result = await self.service.export_sessions(["s1"], ExportFormat.JSON, sessions_data=sessions)
        parsed = json.loads(result.file_content)
        assert "export_time" in parsed
        assert "session_count" in parsed


class TestSessionExportCSV:
    def setup_method(self):
        self.service = SessionExportService()

    @pytest.mark.asyncio
    async def test_export_csv_basic(self):
        sessions = [{
            "id": "s1",
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"},
            ],
            "metadata": {},
        }]
        result = await self.service.export_sessions(
            ["s1"], ExportFormat.CSV, sessions_data=sessions
        )
        assert result.status == ExportStatus.COMPLETED
        assert result.file_name.endswith(".csv")
        assert "session_id" in result.file_content
        assert "role" in result.file_content

    @pytest.mark.asyncio
    async def test_export_csv_multiple_sessions(self):
        sessions = [
            {"id": "s1", "messages": [{"role": "user", "content": "Q1"}], "metadata": {}},
            {"id": "s2", "messages": [{"role": "user", "content": "Q2"}], "metadata": {}},
        ]
        result = await self.service.export_sessions(
            ["s1", "s2"], ExportFormat.CSV, sessions_data=sessions
        )
        assert result.session_count == 2


class TestSessionExportPDF:
    def setup_method(self):
        self.service = SessionExportService()

    @pytest.mark.asyncio
    async def test_export_pdf_placeholder(self):
        sessions = [{"id": "s1", "messages": [], "metadata": {}}]
        result = await self.service.export_sessions(
            ["s1"], ExportFormat.PDF, sessions_data=sessions
        )
        assert result.status == ExportStatus.COMPLETED
        assert result.file_name.endswith(".pdf")


# ============================================================
# 无数据占位导出测试
# ============================================================

class TestSessionExportPlaceholder:
    def setup_method(self):
        self.service = SessionExportService()

    @pytest.mark.asyncio
    async def test_export_no_data_generates_placeholder(self):
        result = await self.service.export_sessions(
            ["s1", "s2"], ExportFormat.MARKDOWN
        )
        assert result.status == ExportStatus.COMPLETED
        assert result.session_count == 2


# ============================================================
# 历史记录测试
# ============================================================

class TestExportHistory:
    def setup_method(self):
        self.service = SessionExportService()

    @pytest.mark.asyncio
    async def test_history_recorded(self):
        await self.service.export_sessions(["s1"], ExportFormat.MARKDOWN)
        await self.service.export_sessions(["s2"], ExportFormat.JSON)
        assert len(self.service._history) == 2

    @pytest.mark.asyncio
    async def test_history_contains_result(self):
        await self.service.export_sessions(["s1"], ExportFormat.MARKDOWN)
        assert "status" in self.service._history[0]
        assert "format" in self.service._history[0]


# ============================================================
# 边界情况
# ============================================================

class TestExportEdgeCases:
    def setup_method(self):
        self.service = SessionExportService()

    @pytest.mark.asyncio
    async def test_export_empty_sessions_list(self):
        result = await self.service.export_sessions([], ExportFormat.MARKDOWN)
        assert result.status == ExportStatus.COMPLETED
        assert result.session_count == 0

    @pytest.mark.asyncio
    async def test_export_many_sessions(self):
        sessions = [
            {"id": f"s{i}", "messages": [{"role": "user", "content": f"Q{i}"}], "metadata": {}}
            for i in range(50)
        ]
        result = await self.service.export_sessions(
            [f"s{i}" for i in range(50)],
            ExportFormat.MARKDOWN,
            sessions_data=sessions,
        )
        assert result.status == ExportStatus.COMPLETED
        assert result.session_count == 50
