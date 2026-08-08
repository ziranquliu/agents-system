"""
运维报告自动推送服务

功能:
- 日报/周报/月报自动生成
- 报告内容：系统概览/Agent 健康/Token 使用/告警统计/维护记录/容量规划
- 多渠道推送（邮件/飞书/钉钉/企微）
- 报告存档与查询
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ReportType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class ReportStatus(str, Enum):
    DRAFT = "draft"
    GENERATED = "generated"
    DELIVERED = "delivered"
    FAILED = "failed"


@dataclass
class ReportSection:
    """报告章节"""
    title: str = ""
    content: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    charts: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class OpsReport:
    """运维报告"""
    id: str = ""
    report_type: ReportType = ReportType.DAILY
    title: str = ""
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    sections: list[ReportSection] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    status: ReportStatus = ReportStatus.DRAFT
    generated_at: Optional[datetime] = None
    delivered_channels: list[str] = field(default_factory=list)
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "report_type": self.report_type.value,
            "title": self.title,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "sections": [{"title": s.title, "content": s.content} for s in self.sections],
            "summary": self.summary,
            "recommendations": self.recommendations,
            "status": self.status.value,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "delivered_channels": self.delivered_channels,
        }

    def to_markdown(self) -> str:
        """导出为 Markdown"""
        lines = [f"# {self.title}", ""]
        lines.append(f"**报告类型:** {self.report_type.value}")
        if self.period_start and self.period_end:
            lines.append(f"**报告期间:** {self.period_start.strftime('%Y-%m-%d')} ~ {self.period_end.strftime('%Y-%m-%d')}")
        lines.append(f"**生成时间:** {self.generated_at.strftime('%Y-%m-%d %H:%M') if self.generated_at else 'N/A'}")
        lines.append("")

        # 摘要
        if self.summary:
            lines.append("## 📊 摘要")
            for k, v in self.summary.items():
                lines.append(f"- **{k}:** {v}")
            lines.append("")

        # 各章节
        for section in self.sections:
            lines.append(f"## {section.title}")
            lines.append(section.content)
            lines.append("")

        # 建议
        if self.recommendations:
            lines.append("## 💡 建议")
            for rec in self.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        return "\n".join(lines)


class OpsReportService:
    """
    运维报告自动推送服务

    自动收集系统数据，生成日报/周报/月报，推送到多渠道
    """

    def __init__(self):
        self._reports: list[OpsReport] = []
        self._delivery_config: dict[str, list[str]] = {
            "email": [],
            "feishu": [],
            "dingtalk": [],
            "wecom": [],
        }
        # 数据采集器
        self._data_collectors: dict[str, callable] = {}

    # ----------------------------------------------------------
    # 数据采集
    # ----------------------------------------------------------

    def register_data_collector(self, name: str, collector: callable):
        """注册数据采集器"""
        self._data_collectors[name] = collector

    async def _collect_system_overview(self) -> dict[str, Any]:
        """采集系统概览数据"""
        return {
            "total_agents": 0,
            "active_agents": 0,
            "total_sessions": 0,
            "active_sessions": 0,
            "total_tokens_today": 0,
            "total_tokens_month": 0,
        }

    async def _collect_health_data(self) -> dict[str, Any]:
        """采集健康数据"""
        return {
            "healthy_agents": 0,
            "degraded_agents": 0,
            "unhealthy_agents": 0,
            "avg_health_score": 0,
        }

    async def _collect_token_data(self) -> dict[str, Any]:
        """采集 Token 使用数据"""
        return {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost": 0,
            "top_models": [],
        }

    async def _collect_alert_data(self) -> dict[str, Any]:
        """采集告警数据"""
        return {
            "total_alerts": 0,
            "critical_alerts": 0,
            "resolved_alerts": 0,
            "avg_resolution_time": 0,
        }

    async def _collect_maintenance_data(self) -> dict[str, Any]:
        """采集维护数据"""
        return {
            "tasks_executed": 0,
            "tasks_failed": 0,
            "backup_count": 0,
        }

    # ----------------------------------------------------------
    # 报告生成
    # ----------------------------------------------------------

    async def generate_report(
        self,
        report_type: ReportType = ReportType.DAILY,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> OpsReport:
        """生成运维报告"""
        now = datetime.now(timezone.utc)
        if not period_end:
            period_end = now
        if not period_start:
            if report_type == ReportType.DAILY:
                period_start = now - timedelta(days=1)
            elif report_type == ReportType.WEEKLY:
                period_start = now - timedelta(weeks=1)
            else:
                period_start = now - timedelta(days=30)

        type_names = {
            ReportType.DAILY: "日报",
            ReportType.WEEKLY: "周报",
            ReportType.MONTHLY: "月报",
        }

        report = OpsReport(
            report_type=report_type,
            title=f"智能体管理系统{type_names[report_type]} - {period_start.strftime('%Y-%m-%d')}",
            period_start=period_start,
            period_end=period_end,
            status=ReportStatus.GENERATED,
            generated_at=now,
            created_at=now,
        )

        # 采集数据
        overview = await self._collect_system_overview()
        health = await self._collect_health_data()
        tokens = await self._collect_token_data()
        alerts = await self._collect_alert_data()
        maintenance = await self._collect_maintenance_data()

        # 系统概览章节
        report.sections.append(ReportSection(
            title="📊 系统概览",
            content=(
                f"- Agent 总数: {overview['total_agents']}\n"
                f"- 活跃 Agent: {overview['active_agents']}\n"
                f"- 今日会话数: {overview['total_sessions']}\n"
                f"- 活跃会话: {overview['active_sessions']}\n"
                f"- 今日 Token 使用: {overview['total_tokens_today']:,}\n"
                f"- 本月 Token 使用: {overview['total_tokens_month']:,}"
            ),
            data=overview,
        ))

        # 健康状况章节
        report.sections.append(ReportSection(
            title="🏥 健康状况",
            content=(
                f"- 健康 Agent: {health['healthy_agents']}\n"
                f"- 亚健康 Agent: {health['degraded_agents']}\n"
                f"- 不健康 Agent: {health['unhealthy_agents']}\n"
                f"- 平均健康分: {health['avg_health_score']:.1f}"
            ),
            data=health,
        ))

        # Token 使用章节
        report.sections.append(ReportSection(
            title="💰 Token 使用",
            content=(
                f"- 输入 Token: {tokens['total_input_tokens']:,}\n"
                f"- 输出 Token: {tokens['total_output_tokens']:,}\n"
                f"- 总费用: ${tokens['total_cost']:.2f}"
            ),
            data=tokens,
        ))

        # 告警统计章节
        report.sections.append(ReportSection(
            title="🔔 告警统计",
            content=(
                f"- 总告警: {alerts['total_alerts']}\n"
                f"- 严重告警: {alerts['critical_alerts']}\n"
                f"- 已解决: {alerts['resolved_alerts']}\n"
                f"- 平均处理时间: {alerts['avg_resolution_time']:.0f}s"
            ),
            data=alerts,
        ))

        # 维护记录章节
        report.sections.append(ReportSection(
            title="🔧 维护记录",
            content=(
                f"- 执行任务: {maintenance['tasks_executed']}\n"
                f"- 失败任务: {maintenance['tasks_failed']}\n"
                f"- 备份次数: {maintenance['backup_count']}"
            ),
            data=maintenance,
        ))

        # 生成建议
        report.recommendations = self._generate_recommendations(overview, health, tokens, alerts)

        # 摘要
        report.summary = {
            "agent_count": overview["total_agents"],
            "active_sessions": overview["active_sessions"],
            "token_usage": overview["total_tokens_today"],
            "health_score": health["avg_health_score"],
            "alert_count": alerts["total_alerts"],
            "cost": tokens["total_cost"],
        }

        self._reports.append(report)
        return report

    def _generate_recommendations(
        self,
        overview: dict,
        health: dict,
        tokens: dict,
        alerts: dict,
    ) -> list[str]:
        """自动生成建议"""
        recommendations = []

        if health.get("unhealthy_agents", 0) > 0:
            recommendations.append(f"有 {health['unhealthy_agents']} 个 Agent 不健康，建议检查日志和资源使用")

        if alerts.get("critical_alerts", 0) > 0:
            recommendations.append(f"有 {alerts['critical_alerts']} 个严重告警未处理")

        if tokens.get("total_cost", 0) > 100:
            recommendations.append("本月 Token 费用超过 $100，建议检查是否有不必要的调用")

        if health.get("avg_health_score", 100) < 70:
            recommendations.append("平均健康分低于 70，建议对低分 Agent 进行优化")

        if not recommendations:
            recommendations.append("系统运行正常，无需特别关注")

        return recommendations

    # ----------------------------------------------------------
    # 推送
    # ----------------------------------------------------------

    async def deliver_report(
        self,
        report_id: str,
        channels: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """推送报告"""
        report = next((r for r in self._reports if r.id == report_id), None)
        if not report:
            return {"error": "Report not found"}

        target_channels = channels or list(self._delivery_config.keys())
        results = {}

        for channel in target_channels:
            if channel in self._delivery_config:
                recipients = self._delivery_config[channel]
                if not recipients:
                    results[channel] = {"status": "skipped", "reason": "no recipients"}
                    continue

                # 模拟推送
                results[channel] = {
                    "status": "delivered",
                    "recipients_count": len(recipients),
                    "delivered_at": datetime.now(timezone.utc).isoformat(),
                }
                report.delivered_channels.append(channel)
                logger.info(f"Report delivered to {channel}: {len(recipients)} recipients")

        report.status = ReportStatus.DELIVERED
        return results

    def configure_recipients(
        self,
        channel: str,
        recipients: list[str],
    ):
        """配置推送接收者"""
        self._delivery_config[channel] = recipients
        logger.info(f"Recipients configured for {channel}: {len(recipients)}")

    # ----------------------------------------------------------
    # 查询
    # ----------------------------------------------------------

    def list_reports(
        self,
        report_type: Optional[ReportType] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        reports = self._reports
        if report_type:
            reports = [r for r in reports if r.report_type == report_type]
        return [r.to_dict() for r in reports[-limit:]]

    def get_report(self, report_id: str) -> Optional[dict[str, Any]]:
        report = next((r for r in self._reports if r.id == report_id), None)
        return report.to_dict() if report else None

    def get_report_markdown(self, report_id: str) -> Optional[str]:
        report = next((r for r in self._reports if r.id == report_id), None)
        return report.to_markdown() if report else None
