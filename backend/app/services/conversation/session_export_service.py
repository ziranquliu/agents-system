"""
会话导出服务 — 多选导出（Markdown/JSON/PDF/CSV）

功能:
- 多选会话批量导出
- 4 种导出格式：Markdown / JSON / PDF / CSV
- 导出历史记录
- 大批量异步导出
"""

import csv
import io
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ExportFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"
    PDF = "pdf"
    CSV = "csv"


class ExportStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExportRequest:
    """导出请求"""
    id: str = ""
    session_ids: list[str] = field(default_factory=list)
    format: ExportFormat = ExportFormat.MARKDOWN
    user_id: str = ""
    include_metadata: bool = True
    date_from: Optional[str] = None  # YYYY-MM-DD
    date_to: Optional[str] = None
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())


@dataclass
class ExportResult:
    """导出结果"""
    id: str = ""
    request_id: str = ""
    status: ExportStatus = ExportStatus.PENDING
    format: ExportFormat = ExportFormat.MARKDOWN
    file_content: str = ""
    file_name: str = ""
    file_size: int = 0
    session_count: int = 0
    message_count: int = 0
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "status": self.status.value,
            "format": self.format.value,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "session_count": self.session_count,
            "message_count": self.message_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
        }


class SessionExportService:
    """
    会话导出服务

    支持 Markdown / JSON / PDF / CSV 四种格式
    """

    def __init__(self):
        self._results: dict[str, ExportResult] = {}
        self._history: list[dict[str, Any]] = []

    async def export_sessions(
        self,
        session_ids: list[str],
        format: ExportFormat = ExportFormat.MARKDOWN,
        user_id: str = "",
        sessions_data: Optional[list[dict[str, Any]]] = None,
        include_metadata: bool = True,
    ) -> ExportResult:
        """导出会话"""
        request = ExportRequest(
            session_ids=session_ids,
            format=format,
            user_id=user_id,
            include_metadata=include_metadata,
        )

        result = ExportResult(
            id=str(uuid.uuid4()),
            request_id=request.id,
            status=ExportStatus.PROCESSING,
            format=format,
            session_count=len(session_ids),
            created_at=datetime.now(timezone.utc),
        )
        self._results[result.id] = result

        try:
            # 如果未提供数据，生成占位数据
            if not sessions_data:
                sessions_data = [
                    {
                        "id": sid,
                        "messages": [],
                        "metadata": {},
                    }
                    for sid in session_ids
                ]

            total_messages = sum(len(s.get("messages", [])) for s in sessions_data)
            result.message_count = total_messages

            if format == ExportFormat.MARKDOWN:
                result.file_content = self._export_markdown(sessions_data, include_metadata)
                result.file_name = f"conversations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            elif format == ExportFormat.JSON:
                result.file_content = self._export_json(sessions_data, include_metadata)
                result.file_name = f"conversations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            elif format == ExportFormat.CSV:
                result.file_content = self._export_csv(sessions_data, include_metadata)
                result.file_name = f"conversations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            elif format == ExportFormat.PDF:
                result.file_content = self._export_pdf_placeholder(sessions_data)
                result.file_name = f"conversations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

            result.file_size = len(result.file_content.encode("utf-8"))
            result.status = ExportStatus.COMPLETED
            result.completed_at = datetime.now(timezone.utc)

        except Exception as e:
            result.status = ExportStatus.FAILED
            result.error_message = str(e)
            logger.error(f"Export failed: {e}")

        self._history.append(result.to_dict())
        return result

    # ----------------------------------------------------------
    # 格式化导出
    # ----------------------------------------------------------

    def _export_markdown(
        self,
        sessions: list[dict[str, Any]],
        include_metadata: bool,
    ) -> str:
        """导出为 Markdown"""
        lines = []
        lines.append(f"# 对话导出")
        lines.append(f"")
        lines.append(f"导出时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"会话数: {len(sessions)}")
        lines.append("")
        lines.append("---")
        lines.append("")

        for session in sessions:
            sid = session.get("id", "unknown")
            lines.append(f"## 会话 {sid}")
            lines.append("")

            if include_metadata:
                meta = session.get("metadata", {})
                if meta:
                    lines.append("**元数据:**")
                    for k, v in meta.items():
                        lines.append(f"- {k}: {v}")
                    lines.append("")

            messages = session.get("messages", [])
            for msg in messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                timestamp = msg.get("timestamp", "")
                icon = "👤" if role == "user" else "🤖" if role == "assistant" else "⚙️"
                lines.append(f"**{icon} {role}** {timestamp}")
                lines.append(f"> {content}")
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def _export_json(
        self,
        sessions: list[dict[str, Any]],
        include_metadata: bool,
    ) -> str:
        """导出为 JSON"""
        export_data = {
            "export_time": datetime.now(timezone.utc).isoformat(),
            "session_count": len(sessions),
            "sessions": [],
        }
        for session in sessions:
            item = {"id": session.get("id")}
            if include_metadata:
                item["metadata"] = session.get("metadata", {})
            item["messages"] = session.get("messages", [])
            export_data["sessions"].append(item)

        return json.dumps(export_data, ensure_ascii=False, indent=2, default=str)

    def _export_csv(
        self,
        sessions: list[dict[str, Any]],
        include_metadata: bool,
    ) -> str:
        """导出为 CSV"""
        output = io.StringIO()
        writer = csv.writer(output)

        headers = ["session_id", "message_index", "role", "content", "timestamp"]
        if include_metadata:
            headers.append("metadata")
        writer.writerow(headers)

        for session in sessions:
            sid = session.get("id", "")
            meta_str = json.dumps(session.get("metadata", {}), ensure_ascii=False) if include_metadata else ""
            for idx, msg in enumerate(session.get("messages", [])):
                row = [
                    sid,
                    idx,
                    msg.get("role", ""),
                    msg.get("content", ""),
                    msg.get("timestamp", ""),
                ]
                if include_metadata:
                    row.append(meta_str)
                writer.writerow(row)

        return output.getvalue()

    def _export_pdf_placeholder(self, sessions: list[dict[str, Any]]) -> str:
        """PDF 导出占位（实际使用 reportlab）"""
        try:
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib import colors
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            import tempfile
            import os

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
            styles = getSampleStyleSheet()
            elements = []

            elements.append(Paragraph("对话导出", styles["Title"]))
            elements.append(Spacer(1, 20))

            for session in sessions:
                sid = session.get("id", "unknown")
                elements.append(Paragraph(f"会话: {sid}", styles["Heading2"]))

                messages = session.get("messages", [])
                if messages:
                    table_data = [["角色", "内容", "时间"]]
                    for msg in messages:
                        table_data.append([
                            msg.get("role", ""),
                            msg.get("content", "")[:200],
                            msg.get("timestamp", ""),
                        ])
                    table = Table(table_data)
                    table.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ]))
                    elements.append(table)
                    elements.append(Spacer(1, 20))

            doc.build(elements)
            return buffer.getvalue().decode("latin-1")

        except ImportError:
            return f"PDF export requires reportlab. Sessions: {len(sessions)}"

    # ----------------------------------------------------------
    # 查询
    # ----------------------------------------------------------

    def get_export(self, export_id: str) -> Optional[dict[str, Any]]:
        result = self._results.get(export_id)
        return result.to_dict() if result else None

    def get_export_content(self, export_id: str) -> Optional[str]:
        result = self._results.get(export_id)
        return result.file_content if result else None

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._history[-limit:]
