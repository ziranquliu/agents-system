"""
多智能体监控看板服务 — 指标 / 告警 / 面板
"""
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import select, func as sa_func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.monitoring import AgentMetric, AlertConfig, AlertRecord, DashboardPanel


class MonitoringService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ----------------------------------------------------------
    # 指标记录与查询
    # ----------------------------------------------------------

    async def record_metric(self, data: dict[str, Any]) -> AgentMetric:
        """记录 Agent 指标"""
        metric = AgentMetric(
            agent_id=data["agent_id"],
            agent_name=data.get("agent_name", ""),
            qps=data.get("qps", 0.0),
            success_rate=data.get("success_rate", 100.0),
            latency_p50=data.get("latency_p50", 0.0),
            latency_p95=data.get("latency_p95", 0.0),
            latency_p99=data.get("latency_p99", 0.0),
            memory_mb=data.get("memory_mb", 0.0),
            cpu_percent=data.get("cpu_percent", 0.0),
            health_score=data.get("health_score", 100.0),
            recorded_at=datetime.now(timezone.utc),
        )
        self.db.add(metric)
        await self.db.flush()

        # 自动检查告警
        await self._check_alerts(metric)
        return metric

    async def get_latest_metrics(self) -> dict[str, dict]:
        """获取所有 Agent 的最新指标"""
        subq = (
            select(
                AgentMetric.agent_id,
                sa_func.max(AgentMetric.recorded_at).label("max_time")
            )
            .group_by(AgentMetric.agent_id)
            .subquery()
        )
        r = await self.db.execute(
            select(AgentMetric).join(
                subq,
                and_(
                    AgentMetric.agent_id == subq.c.agent_id,
                    AgentMetric.recorded_at == subq.c.max_time,
                )
            )
        )
        metrics = list(r.scalars().all())
        result = {}
        for m in metrics:
            result[m.agent_id] = {
                "agent_id": m.agent_id,
                "agent_name": m.agent_name or m.agent_id,
                "qps": m.qps,
                "success_rate": m.success_rate,
                "latency_p50": m.latency_p50,
                "latency_p95": m.latency_p95,
                "latency_p99": m.latency_p99,
                "memory_mb": m.memory_mb,
                "cpu_percent": m.cpu_percent,
                "health_score": m.health_score,
                "recorded_at": m.recorded_at.isoformat() if m.recorded_at else None,
            }
        return result

    async def get_metric_history(
        self, agent_id: str,
        metric_names: list[str],
        hours: int = 24,
        interval_minutes: int = 5,
    ) -> dict[str, list]:
        """获取指标历史（聚合）"""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        r = await self.db.execute(
            select(AgentMetric).where(
                AgentMetric.agent_id == agent_id,
                AgentMetric.recorded_at >= since,
            ).order_by(AgentMetric.recorded_at)
        )
        metrics = list(r.scalars().all())

        # 按 interval 聚合
        result: dict[str, list] = {name: [] for name in metric_names}
        buckets: dict[int, list] = defaultdict(list)

        for m in metrics:
            bucket_key = int(m.recorded_at.timestamp() / (interval_minutes * 60))
            buckets[bucket_key].append(m)

        for key in sorted(buckets.keys()):
            batch = buckets[key]
            avg = lambda attr: sum(getattr(m, attr, 0) or 0 for m in batch) / len(batch)
            time_str = datetime.fromtimestamp(key * interval_minutes * 60, tz=timezone.utc).isoformat()

            for name in metric_names:
                val = round(avg(name), 2)
                result[name].append({"time": time_str, "value": val})

        return result

    async def get_agent_ranking(self, sort_by: str = "health_score", limit: int = 20) -> list[dict]:
        """Agent 排行"""
        latest = await self.get_latest_metrics()
        sorted_agents = sorted(
            latest.values(),
            key=lambda x: x.get(sort_by, 0) or 0,
            reverse=True,
        )[:limit]
        return sorted_agents

    # ----------------------------------------------------------
    # 健康评分计算
    # ----------------------------------------------------------

    @staticmethod
    def compute_health_score(metrics: dict[str, float]) -> float:
        """计算综合健康评分 (0-100)"""
        weights = {
            "success_rate": 0.35,
            "latency_p95": 0.20,
            "cpu_percent": 0.15,
            "memory_mb": 0.15,
            "qps": 0.15,
        }

        score = 0.0

        # success_rate: 目标 100%
        sr = metrics.get("success_rate", 100)
        sr_score = min(100, sr)
        score += sr_score * weights["success_rate"]

        # latency_p95: 越低越好 (目标 < 1000ms)
        lat = metrics.get("latency_p95", 0)
        lat_score = max(0, 100 - lat / 20)
        score += lat_score * weights["latency_p95"]

        # cpu_percent: 越低越好
        cpu = metrics.get("cpu_percent", 0)
        cpu_score = max(0, 100 - cpu)
        score += cpu_score * weights["cpu_percent"]

        # memory_mb: 越低越好 (假设阈值 4096MB)
        mem = metrics.get("memory_mb", 0)
        mem_score = max(0, 100 - (mem / 4096 * 100))
        score += mem_score * weights["memory_mb"]

        # qps: 越高越好 (目标 100qps)
        qps = metrics.get("qps", 0)
        qps_score = min(100, qps * 2)
        score += qps_score * weights["qps"]

        return round(min(100, max(0, score)), 1)

    # ----------------------------------------------------------
    # 告警管理
    # ----------------------------------------------------------

    async def create_alert_config(self, data: dict[str, Any]) -> AlertConfig:
        config = AlertConfig(
            name=data["name"],
            description=data.get("description", ""),
            priority=data.get("priority", "P2"),
            metric_name=data["metric_name"],
            operator=data["operator"],
            threshold=data["threshold"],
            duration_seconds=data.get("duration_seconds", 60),
            target_type=data.get("target_type", "all"),
            target_agent_id=data.get("target_agent_id"),
            notify_method=data.get("notify_method", ""),
            notify_target=data.get("notify_target", ""),
            enabled=data.get("enabled", True),
        )
        self.db.add(config)
        await self.db.flush()
        return config

    async def update_alert_config(self, config_id: str, data: dict[str, Any]) -> Optional[AlertConfig]:
        r = await self.db.execute(select(AlertConfig).where(AlertConfig.id == config_id))
        config = r.scalar_one_or_none()
        if not config:
            return None
        for key in ["name", "description", "priority", "metric_name", "operator", "threshold",
                     "duration_seconds", "target_type", "target_agent_id", "notify_method",
                     "notify_target", "enabled"]:
            if key in data:
                setattr(config, key, data[key])
        await self.db.flush()
        return config

    async def list_alert_configs(self, enabled_only: bool = False) -> list[AlertConfig]:
        conditions = []
        if enabled_only:
            conditions.append(AlertConfig.enabled == True)
        where = and_(*conditions) if conditions else True
        r = await self.db.execute(select(AlertConfig).where(where).order_by(AlertConfig.priority))
        return list(r.scalars().all())

    async def delete_alert_config(self, config_id: str) -> bool:
        r = await self.db.execute(select(AlertConfig).where(AlertConfig.id == config_id))
        config = r.scalar_one_or_none()
        if not config:
            return False
        await self.db.delete(config)
        await self.db.flush()
        return True

    async def _check_alerts(self, metric: AgentMetric):
        """检查是否有告警触发"""
        r = await self.db.execute(
            select(AlertConfig).where(AlertConfig.enabled == True)
        )
        configs = list(r.scalars().all())

        for cfg in configs:
            if cfg.target_type == "specific_agent" and cfg.target_agent_id != metric.agent_id:
                continue

            actual = getattr(metric, cfg.metric_name, None)
            if actual is None:
                continue

            triggered = False
            if cfg.operator == "gt" and actual > cfg.threshold:
                triggered = True
            elif cfg.operator == "lt" and actual < cfg.threshold:
                triggered = True
            elif cfg.operator == "gte" and actual >= cfg.threshold:
                triggered = True
            elif cfg.operator == "lte" and actual <= cfg.threshold:
                triggered = True
            elif cfg.operator == "eq" and actual == cfg.threshold:
                triggered = True

            if triggered:
                # 避免重复告警
                recent = await self.db.execute(
                    select(AlertRecord).where(
                        AlertRecord.config_id == cfg.id,
                        AlertRecord.agent_id == metric.agent_id,
                        AlertRecord.status == "firing",
                    )
                )
                if not recent.scalar_one_or_none():
                    record = AlertRecord(
                        config_id=cfg.id,
                        alert_name=cfg.name,
                        priority=cfg.priority,
                        agent_id=metric.agent_id,
                        metric_name=cfg.metric_name,
                        current_value=actual,
                        threshold=cfg.threshold,
                        operator=cfg.operator,
                        status="firing",
                        fired_at=datetime.now(timezone.utc),
                    )
                    self.db.add(record)

        await self.db.flush()

    async def list_alerts(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        agent_id: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[AlertRecord], int]:
        conditions = []
        if status:
            conditions.append(AlertRecord.status == status)
        if priority:
            conditions.append(AlertRecord.priority == priority)
        if agent_id:
            conditions.append(AlertRecord.agent_id == agent_id)

        where = and_(*conditions) if conditions else True
        count_q = select(sa_func.count()).select_from(AlertRecord).where(where)
        total = (await self.db.execute(count_q)).scalar() or 0

        r = await self.db.execute(
            select(AlertRecord).where(where)
            .order_by(AlertRecord.fired_at.desc())
            .offset(offset).limit(limit)
        )
        return list(r.scalars().all()), total

    async def acknowledge_alert(self, alert_id: str, user_id: str = "") -> Optional[AlertRecord]:
        r = await self.db.execute(select(AlertRecord).where(AlertRecord.id == alert_id))
        alert = r.scalar_one_or_none()
        if not alert:
            return None
        alert.status = "acknowledged"
        alert.acknowledged_by = user_id
        alert.acknowledged_at = datetime.now(timezone.utc)
        await self.db.flush()
        return alert

    async def resolve_alert(self, alert_id: str) -> Optional[AlertRecord]:
        r = await self.db.execute(select(AlertRecord).where(AlertRecord.id == alert_id))
        alert = r.scalar_one_or_none()
        if not alert:
            return None
        alert.status = "resolved"
        alert.resolved_at = datetime.now(timezone.utc)
        await self.db.flush()
        return alert

    # ----------------------------------------------------------
    # 面板管理
    # ----------------------------------------------------------

    async def create_panel(self, data: dict[str, Any]) -> DashboardPanel:
        panel = DashboardPanel(
            title=data["title"],
            chart_type=data.get("chart_type", "line"),
            metric_names=json.dumps(data.get("metric_names", []), ensure_ascii=False),
            agent_ids=json.dumps(data.get("agent_ids", []), ensure_ascii=False),
            position_x=data.get("position_x", 0),
            position_y=data.get("position_y", 0),
            width=data.get("width", 2),
            height=data.get("height", 2),
            config=json.dumps(data.get("config", {}), ensure_ascii=False),
            created_by=data.get("created_by", ""),
        )
        self.db.add(panel)
        await self.db.flush()
        return panel

    async def update_panel(self, panel_id: str, data: dict[str, Any]) -> Optional[DashboardPanel]:
        r = await self.db.execute(select(DashboardPanel).where(DashboardPanel.id == panel_id))
        panel = r.scalar_one_or_none()
        if not panel:
            return None
        updatable = ["title", "chart_type", "position_x", "position_y", "width", "height", "enabled"]
        for key in updatable:
            if key in data:
                setattr(panel, key, data[key])
        if "metric_names" in data:
            panel.metric_names = json.dumps(data["metric_names"], ensure_ascii=False)
        if "agent_ids" in data:
            panel.agent_ids = json.dumps(data["agent_ids"], ensure_ascii=False)
        if "config" in data:
            panel.config = json.dumps(data["config"], ensure_ascii=False)
        await self.db.flush()
        return panel

    async def list_panels(self) -> list[DashboardPanel]:
        r = await self.db.execute(
            select(DashboardPanel).where(DashboardPanel.enabled == True)
            .order_by(DashboardPanel.position_y, DashboardPanel.position_x)
        )
        return list(r.scalars().all())

    async def delete_panel(self, panel_id: str) -> bool:
        r = await self.db.execute(select(DashboardPanel).where(DashboardPanel.id == panel_id))
        panel = r.scalar_one_or_none()
        if not panel:
            return False
        await self.db.delete(panel)
        await self.db.flush()
        return True

    # ----------------------------------------------------------
    # Prometheus 格式导出
    # ----------------------------------------------------------

    async def metrics_for_prometheus(self) -> str:
        """生成 Prometheus 兼容的 metrics 文本"""
        latest = await self.get_latest_metrics()
        lines = [
            "# HELP agent_health_score Agent health score (0-100)",
            "# TYPE agent_health_score gauge",
        ]
        for agent_id, m in latest.items():
            lines.append(f'agent_health_score{{agent="{agent_id}",name="{m.get("agent_name", "")}"}} {m.get("health_score", 0)}')
            lines.append(f'agent_qps{{agent="{agent_id}"}} {m.get("qps", 0)}')
            lines.append(f'agent_success_rate{{agent="{agent_id}"}} {m.get("success_rate", 0)}')
            lines.append(f'agent_latency_p50_ms{{agent="{agent_id}"}} {m.get("latency_p50", 0)}')
            lines.append(f'agent_latency_p95_ms{{agent="{agent_id}"}} {m.get("latency_p95", 0)}')
            lines.append(f'agent_memory_mb{{agent="{agent_id}"}} {m.get("memory_mb", 0)}')
            lines.append(f'agent_cpu_percent{{agent="{agent_id}"}} {m.get("cpu_percent", 0)}')

        lines.append("\n# HELP agent_alert_count Active alert count by priority")
        for p in ["P0", "P1", "P2", "P3"]:
            r = await self.db.execute(
                select(sa_func.count()).select_from(AlertRecord).where(
                    AlertRecord.priority == p, AlertRecord.status == "firing"
                )
            )
            count = r.scalar() or 0
            lines.append(f'agent_alert_count{{priority="{p}"}} {count}')

        return "\n".join(lines)
