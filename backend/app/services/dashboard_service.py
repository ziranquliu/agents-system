"""
自定义拖拽仪表盘服务

功能:
- 仪表盘 CRUD
- 组件 CRUD (图表/表格/指标卡/文本)
- 布局存储 (栅格系统)
- 共享与权限
- 预设模板
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class DashboardWidget:
    """仪表盘组件"""
    id: str = ""
    widget_type: str = "metric"  # metric / chart / table / text / gauge / heatmap
    title: str = ""
    data_source: str = ""  # agent_id / session_id / custom_query
    query: dict[str, Any] = field(default_factory=dict)
    position: dict[str, int] = field(default_factory=lambda: {"x": 0, "y": 0, "w": 4, "h": 3})
    config: dict[str, Any] = field(default_factory=dict)
    refresh_interval: int = 30  # 秒
    created_at: str = ""


@dataclass
class Dashboard:
    """仪表盘"""
    id: str = ""
    name: str = ""
    description: str = ""
    owner_id: str = ""
    widgets: list[dict] = field(default_factory=list)
    layout_cols: int = 12
    theme: str = "light"
    is_public: bool = False
    shared_with: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class DashboardService:
    """
    自定义拖拽仪表盘服务

    - 组件 CRUD + 栅格布局
    - 共享/权限
    - 预设模板
    """

    WIDGET_TYPES = {"metric", "chart", "table", "text", "gauge", "heatmap", "log", "alert_list"}

    def __init__(self):
        self._dashboards: dict[str, Dashboard] = {}
        self._templates: list[dict] = []
        self._setup_templates()

    def _setup_templates(self):
        """预设仪表盘模板"""
        self._templates = [
            {
                "id": "tpl_overview",
                "name": "系统概览",
                "description": "核心指标概览仪表盘",
                "widgets": [
                    {"widget_type": "metric", "title": "活跃 Agent 数", "position": {"x": 0, "y": 0, "w": 3, "h": 2}},
                    {"widget_type": "metric", "title": "在线会话数", "position": {"x": 3, "y": 0, "w": 3, "h": 2}},
                    {"widget_type": "metric", "title": "今日请求量", "position": {"x": 6, "y": 0, "w": 3, "h": 2}},
                    {"widget_type": "metric", "title": "今日成本", "position": {"x": 9, "y": 0, "w": 3, "h": 2}},
                    {"widget_type": "chart", "title": "请求趋势", "position": {"x": 0, "y": 2, "w": 6, "h": 4}},
                    {"widget_type": "chart", "title": "错误率趋势", "position": {"x": 6, "y": 2, "w": 6, "h": 4}},
                    {"widget_type": "table", "title": "Agent 列表", "position": {"x": 0, "y": 6, "w": 8, "h": 4}},
                    {"widget_type": "alert_list", "title": "最近告警", "position": {"x": 8, "y": 6, "w": 4, "h": 4}},
                ],
            },
            {
                "id": "tpl_agent_detail",
                "name": "Agent 详情",
                "description": "单 Agent 监控仪表盘",
                "widgets": [
                    {"widget_type": "gauge", "title": "健康评分", "position": {"x": 0, "y": 0, "w": 4, "h": 3}},
                    {"widget_type": "metric", "title": "响应时间 P99", "position": {"x": 4, "y": 0, "w": 4, "h": 3}},
                    {"widget_type": "metric", "title": "错误率", "position": {"x": 8, "y": 0, "w": 4, "h": 3}},
                    {"widget_type": "chart", "title": "性能趋势", "position": {"x": 0, "y": 3, "w": 8, "h": 4}},
                    {"widget_type": "log", "title": "最近日志", "position": {"x": 8, "y": 3, "w": 4, "h": 4}},
                ],
            },
            {
                "id": "tpl_cost_analysis",
                "name": "成本分析",
                "description": "成本分配和趋势分析",
                "widgets": [
                    {"widget_type": "metric", "title": "本月总成本", "position": {"x": 0, "y": 0, "w": 4, "h": 2}},
                    {"widget_type": "metric", "title": "日均成本", "position": {"x": 4, "y": 0, "w": 4, "h": 2}},
                    {"widget_type": "metric", "title": "预算使用率", "position": {"x": 8, "y": 0, "w": 4, "h": 2}},
                    {"widget_type": "chart", "title": "成本趋势", "position": {"x": 0, "y": 2, "w": 8, "h": 4}},
                    {"widget_type": "chart", "title": "按 Agent 分配", "position": {"x": 0, "y": 6, "w": 6, "h": 4}},
                    {"widget_type": "chart", "title": "按模型分配", "position": {"x": 6, "y": 6, "w": 6, "h": 4}},
                ],
            },
        ]

    # ----------------------------------------------------------
    # 仪表盘 CRUD
    # ----------------------------------------------------------

    def create_dashboard(
        self,
        name: str,
        owner_id: str,
        description: str = "",
        template_id: str = "",
        is_public: bool = False,
        tags: Optional[list[str]] = None,
    ) -> dict:
        """创建仪表盘"""
        now = datetime.now(timezone.utc).isoformat()
        dashboard = Dashboard(
            id=f"dash_{uuid.uuid4().hex[:12]}",
            name=name,
            description=description,
            owner_id=owner_id,
            is_public=is_public,
            tags=tags or [],
            created_at=now,
            updated_at=now,
        )

        # 从模板初始化
        if template_id:
            template = next((t for t in self._templates if t["id"] == template_id), None)
            if template:
                dashboard.widgets = [
                    {**w, "id": f"widget_{uuid.uuid4().hex[:8]}"}
                    for w in template["widgets"]
                ]

        self._dashboards[dashboard.id] = dashboard
        return {"id": dashboard.id, "name": dashboard.name, "created_at": now}

    def get_dashboard(self, dashboard_id: str) -> Optional[dict]:
        """获取仪表盘"""
        d = self._dashboards.get(dashboard_id)
        if not d:
            return None
        return {
            "id": d.id,
            "name": d.name,
            "description": d.description,
            "owner_id": d.owner_id,
            "widgets": d.widgets,
            "layout_cols": d.layout_cols,
            "theme": d.theme,
            "is_public": d.is_public,
            "shared_with": d.shared_with,
            "tags": d.tags,
            "created_at": d.created_at,
            "updated_at": d.updated_at,
        }

    def list_dashboards(self, owner_id: str = "", limit: int = 50) -> list[dict]:
        """列出仪表盘"""
        dashboards = list(self._dashboards.values())
        if owner_id:
            dashboards = [d for d in dashboards if d.owner_id == owner_id or d.is_public]
        return [
            {"id": d.id, "name": d.name, "owner_id": d.owner_id, "widget_count": len(d.widgets)}
            for d in dashboards[:limit]
        ]

    def update_dashboard(self, dashboard_id: str, updates: dict) -> dict:
        """更新仪表盘"""
        d = self._dashboards.get(dashboard_id)
        if not d:
            return {"error": "仪表盘不存在"}

        allowed_fields = {"name", "description", "theme", "is_public", "tags"}
        for k, v in updates.items():
            if k in allowed_fields:
                setattr(d, k, v)
        d.updated_at = datetime.now(timezone.utc).isoformat()
        return {"updated": True, "id": dashboard_id}

    def delete_dashboard(self, dashboard_id: str) -> dict:
        """删除仪表盘"""
        if dashboard_id in self._dashboards:
            del self._dashboards[dashboard_id]
            return {"deleted": True}
        return {"error": "仪表盘不存在"}

    # ----------------------------------------------------------
    # 组件 CRUD
    # ----------------------------------------------------------

    def add_widget(self, dashboard_id: str, widget: dict) -> dict:
        """添加组件"""
        d = self._dashboards.get(dashboard_id)
        if not d:
            return {"error": "仪表盘不存在"}

        w_type = widget.get("widget_type", "metric")
        if w_type not in self.WIDGET_TYPES:
            return {"error": f"不支持的组件类型: {w_type}"}

        widget_id = f"widget_{uuid.uuid4().hex[:8]}"
        widget["id"] = widget_id
        if "position" not in widget:
            widget["position"] = {"x": 0, "y": len(d.widgets) * 3, "w": 4, "h": 3}

        d.widgets.append(widget)
        d.updated_at = datetime.now(timezone.utc).isoformat()
        return {"widget_id": widget_id, "added": True}

    def update_widget(self, dashboard_id: str, widget_id: str, updates: dict) -> dict:
        """更新组件"""
        d = self._dashboards.get(dashboard_id)
        if not d:
            return {"error": "仪表盘不存在"}

        for w in d.widgets:
            if w.get("id") == widget_id:
                w.update(updates)
                d.updated_at = datetime.now(timezone.utc).isoformat()
                return {"updated": True}
        return {"error": "组件不存在"}

    def remove_widget(self, dashboard_id: str, widget_id: str) -> dict:
        """移除组件"""
        d = self._dashboards.get(dashboard_id)
        if not d:
            return {"error": "仪表盘不存在"}

        before = len(d.widgets)
        d.widgets = [w for w in d.widgets if w.get("id") != widget_id]
        if len(d.widgets) < before:
            d.updated_at = datetime.now(timezone.utc).isoformat()
            return {"removed": True}
        return {"error": "组件不存在"}

    def get_widgets(self, dashboard_id: str) -> list[dict]:
        """获取所有组件"""
        d = self._dashboards.get(dashboard_id)
        if not d:
            return []
        return d.widgets

    # ----------------------------------------------------------
    # 共享
    # ----------------------------------------------------------

    def share_dashboard(self, dashboard_id: str, user_ids: list[str]) -> dict:
        """共享仪表盘"""
        d = self._dashboards.get(dashboard_id)
        if not d:
            return {"error": "仪表盘不存在"}
        d.shared_with = list(set(d.shared_with + user_ids))
        return {"shared_with": d.shared_with}

    def can_access(self, dashboard_id: str, user_id: str) -> bool:
        """检查访问权限"""
        d = self._dashboards.get(dashboard_id)
        if not d:
            return False
        return d.is_public or d.owner_id == user_id or user_id in d.shared_with

    # ----------------------------------------------------------
    # 模板
    # ----------------------------------------------------------

    def list_templates(self) -> list[dict]:
        """列出预设模板"""
        return [{"id": t["id"], "name": t["name"], "description": t["description"]} for t in self._templates]

    def get_template(self, template_id: str) -> Optional[dict]:
        """获取模板详情"""
        return next((t for t in self._templates if t["id"] == template_id), None)


# 全局实例
_dashboard_service: Optional[DashboardService] = None


def get_dashboard_service() -> DashboardService:
    global _dashboard_service
    if _dashboard_service is None:
        _dashboard_service = DashboardService()
    return _dashboard_service
