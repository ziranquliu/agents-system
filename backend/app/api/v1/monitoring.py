"""
多智能体监控看板 API
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.monitoring_service import MonitoringService

router = APIRouter(prefix="/api/v1/monitoring", tags=["监控看板"])


def _alert_config_to_dict(c):
    return {
        "id": c.id, "name": c.name, "description": c.description,
        "priority": c.priority, "metric_name": c.metric_name,
        "operator": c.operator, "threshold": c.threshold,
        "duration_seconds": c.duration_seconds,
        "target_type": c.target_type, "target_agent_id": c.target_agent_id,
        "notify_method": c.notify_method, "notify_target": c.notify_target,
        "enabled": c.enabled,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _alert_record_to_dict(a):
    return {
        "id": a.id, "config_id": a.config_id, "alert_name": a.alert_name,
        "priority": a.priority, "agent_id": a.agent_id,
        "metric_name": a.metric_name, "current_value": a.current_value,
        "threshold": a.threshold, "operator": a.operator,
        "status": a.status, "acknowledged_by": a.acknowledged_by,
        "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
        "fired_at": a.fired_at.isoformat() if a.fired_at else None,
    }


def _panel_to_dict(p):
    return {
        "id": p.id, "title": p.title, "chart_type": p.chart_type,
        "metric_names": json.loads(p.metric_names) if p.metric_names else [],
        "agent_ids": json.loads(p.agent_ids) if p.agent_ids else [],
        "position_x": p.position_x, "position_y": p.position_y,
        "width": p.width, "height": p.height,
        "config": json.loads(p.config) if p.config else {},
        "enabled": p.enabled, "created_by": p.created_by,
    }


# ----------------------------------------------------------
# 指标
# ----------------------------------------------------------

@router.post("/metrics", summary="记录指标")
async def record_metric(data: dict, db: AsyncSession = Depends(get_db)):
    svc = MonitoringService(db)
    metric = await svc.record_metric(data)
    return {"success": True, "data": {"id": metric.id, "health_score": metric.health_score}}


@router.get("/metrics/latest", summary="获取所有 Agent 最新指标")
async def get_latest_metrics(db: AsyncSession = Depends(get_db)):
    svc = MonitoringService(db)
    data = await svc.get_latest_metrics()
    return {"success": True, "data": data}


@router.get("/metrics/history/{agent_id}", summary="获取指标历史")
async def get_metric_history(
    agent_id: str,
    metric_names: str = Query("health_score,qps,latency_p95"),
    hours: int = Query(24, ge=1, le=168),
    interval_minutes: int = Query(5, ge=1, le=60),
    db: AsyncSession = Depends(get_db),
):
    svc = MonitoringService(db)
    names = [n.strip() for n in metric_names.split(",")]
    data = await svc.get_metric_history(agent_id, names, hours, interval_minutes)
    return {"success": True, "data": data}


@router.get("/metrics/ranking", summary="Agent 排行")
async def get_ranking(sort_by: str = Query("health_score"), limit: int = Query(20),
                      db: AsyncSession = Depends(get_db)):
    svc = MonitoringService(db)
    data = await svc.get_agent_ranking(sort_by, limit)
    return {"success": True, "data": data}


# ----------------------------------------------------------
# 告警配置
# ----------------------------------------------------------

@router.post("/alert-configs", summary="创建告警配置")
async def create_alert_config(data: dict, db: AsyncSession = Depends(get_db)):
    svc = MonitoringService(db)
    config = await svc.create_alert_config(data)
    return {"success": True, "data": _alert_config_to_dict(config)}


@router.put("/alert-configs/{config_id}", summary="更新告警配置")
async def update_alert_config(config_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    svc = MonitoringService(db)
    config = await svc.update_alert_config(config_id, data)
    if not config:
        raise HTTPException(404, "配置不存在")
    return {"success": True, "data": _alert_config_to_dict(config)}


@router.get("/alert-configs", summary="告警配置列表")
async def list_alert_configs(enabled_only: bool = Query(False), db: AsyncSession = Depends(get_db)):
    svc = MonitoringService(db)
    configs = await svc.list_alert_configs(enabled_only)
    return {"success": True, "data": [_alert_config_to_dict(c) for c in configs]}


@router.delete("/alert-configs/{config_id}", summary="删除告警配置")
async def delete_alert_config(config_id: str, db: AsyncSession = Depends(get_db)):
    svc = MonitoringService(db)
    ok = await svc.delete_alert_config(config_id)
    if not ok:
        raise HTTPException(404, "配置不存在")
    return {"success": True, "message": "已删除"}


# ----------------------------------------------------------
# 告警记录
# ----------------------------------------------------------

@router.get("/alerts", summary="告警记录列表")
async def list_alerts(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    svc = MonitoringService(db)
    items, total = await svc.list_alerts(status, priority, agent_id, offset, limit)
    return {"success": True, "data": [_alert_record_to_dict(a) for a in items], "total": total}


@router.post("/alerts/{alert_id}/acknowledge", summary="确认告警")
async def acknowledge_alert(alert_id: str, data: dict = {}, db: AsyncSession = Depends(get_db)):
    svc = MonitoringService(db)
    alert = await svc.acknowledge_alert(alert_id, data.get("user_id", ""))
    if not alert:
        raise HTTPException(404, "告警不存在")
    return {"success": True, "data": _alert_record_to_dict(alert)}


@router.post("/alerts/{alert_id}/resolve", summary="解决告警")
async def resolve_alert(alert_id: str, db: AsyncSession = Depends(get_db)):
    svc = MonitoringService(db)
    alert = await svc.resolve_alert(alert_id)
    if not alert:
        raise HTTPException(404, "告警不存在")
    return {"success": True, "data": _alert_record_to_dict(alert)}


# ----------------------------------------------------------
# 面板
# ----------------------------------------------------------

@router.post("/panels", summary="创建面板")
async def create_panel(data: dict, db: AsyncSession = Depends(get_db)):
    svc = MonitoringService(db)
    panel = await svc.create_panel(data)
    return {"success": True, "data": _panel_to_dict(panel)}


@router.put("/panels/{panel_id}", summary="更新面板")
async def update_panel(panel_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    svc = MonitoringService(db)
    panel = await svc.update_panel(panel_id, data)
    if not panel:
        raise HTTPException(404, "面板不存在")
    return {"success": True, "data": _panel_to_dict(panel)}


@router.get("/panels", summary="面板列表")
async def list_panels(db: AsyncSession = Depends(get_db)):
    svc = MonitoringService(db)
    panels = await svc.list_panels()
    return {"success": True, "data": [_panel_to_dict(p) for p in panels]}


@router.delete("/panels/{panel_id}", summary="删除面板")
async def delete_panel(panel_id: str, db: AsyncSession = Depends(get_db)):
    svc = MonitoringService(db)
    ok = await svc.delete_panel(panel_id)
    if not ok:
        raise HTTPException(404, "面板不存在")
    return {"success": True, "message": "已删除"}


# ----------------------------------------------------------
# Prometheus
# ----------------------------------------------------------

@router.get("/prometheus", summary="Prometheus metrics 端点")
async def prometheus_metrics(db: AsyncSession = Depends(get_db)):
    svc = MonitoringService(db)
    content = await svc.metrics_for_prometheus()
    return PlainTextResponse(content=content, media_type="text/plain")
