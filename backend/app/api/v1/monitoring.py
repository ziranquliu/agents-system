"""
多智能体监控看板 API
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.auth_service import get_current_user
from app.services.monitoring_service import MonitoringService

router = APIRouter(prefix="/api/v1/monitoring", tags=["监控看板"], dependencies=[Depends(get_current_user)])


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


def _safe_json_list(s):
    """安全解析 JSON 列表"""
    if not s:
        return []
    try:
        return json.loads(s) if isinstance(s, str) else s
    except (json.JSONDecodeError, TypeError):
        return []


def _safe_json_dict(s):
    """安全解析 JSON 字典"""
    if not s:
        return {}
    try:
        return json.loads(s) if isinstance(s, str) else s
    except (json.JSONDecodeError, TypeError):
        return {}


def _panel_to_dict(p):
    return {
        "id": p.id, "title": p.title, "chart_type": p.chart_type,
        "metric_names": _safe_json_list(p.metric_names),
        "agent_ids": _safe_json_list(p.agent_ids),
        "position_x": p.position_x, "position_y": p.position_y,
        "width": p.width, "height": p.height,
        "config": _safe_json_dict(p.config),
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


@router.get("/metrics", summary="标准 Prometheus /metrics 端点")
async def standard_metrics():
    """返回标准 Prometheus exposition format 指标"""
    from app.core.prometheus import metrics
    return PlainTextResponse(content=metrics.render(), media_type="text/plain")

# ----------------------------------------------------------
# 自愈通知通道
# ----------------------------------------------------------

def _notify_config_to_dict(c):
    return {
        "id": c.id,
        "notify_method": c.notify_method,
        "webhook_url": c.webhook_url,
        "smtp_host": c.smtp_host,
        "smtp_port": c.smtp_port,
        "smtp_user": c.smtp_user,
        "smtp_use_ssl": c.smtp_use_ssl,
        "smtp_from": c.smtp_from,
        "default_recipients": c.default_recipients,
        # 密码不回显
        "smtp_password_set": bool(c.smtp_password),
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }

@router.get("/notify/config", summary="查看自愈通知配置")
async def get_notify_config(db: AsyncSession = Depends(get_db)):
    from app.services.notification_service import get_notification_config
    cfg = await get_notification_config(db)
    return {"success": True, "data": _notify_config_to_dict(cfg)}

@router.put("/notify/config", summary="更新自愈通知配置")
async def update_notify_config(data: dict, db: AsyncSession = Depends(get_db)):
    from app.services.notification_service import get_notification_config
    from app.models.notification import NotifyMethod

    cfg = await get_notification_config(db)

    method = data.get("notify_method")
    if method is not None:
        if method not in (NotifyMethod.WEBHOOK, NotifyMethod.EMAIL,
                          NotifyMethod.BOTH, NotifyMethod.OFF):
            raise HTTPException(400, f"notify_method 取值非法: {method}")
        cfg.notify_method = method
    for field in ("webhook_url", "smtp_host", "smtp_user", "smtp_from",
                  "default_recipients"):
        if field in data:
            setattr(cfg, field, data[field] or None)
    if "smtp_port" in data:
        cfg.smtp_port = int(data["smtp_port"])
    if "smtp_use_ssl" in data:
        cfg.smtp_use_ssl = bool(data["smtp_use_ssl"])
    from app.core.encryption import encrypt_secret
    if "smtp_password" in data and data.get("smtp_password"):
        cfg.smtp_password = encrypt_secret(data["smtp_password"])

    await db.commit()
    await db.refresh(cfg)
    return {"success": True, "data": _notify_config_to_dict(cfg)}

@router.post("/notify/test", summary="发送测试通知")
async def send_test_notify(data: dict, db: AsyncSession = Depends(get_db)):
    from app.services.notification_service import get_notification_config, notify
    from app.models.notification import NotifyMethod

    method = data.get("method") or NotifyMethod.BOTH
    if method not in (NotifyMethod.WEBHOOK, NotifyMethod.EMAIL, NotifyMethod.BOTH):
        raise HTTPException(400, f"method 取值非法: {method}")
    if method == NotifyMethod.EMAIL and not data.get("target"):
        raise HTTPException(400, "邮件模式需要 target 收件人")

    cfg = await get_notification_config(db)
    title = data.get("title") or "自愈通知测试"
    content = data.get("content") or "这是一条测试通知，用于验证自愈通知通道是否可用。"
    result = await notify(
        method=method,
        target=data.get("target"),
        title=title,
        content=content,
        webhook_url=data.get("webhook_url"),
        cfg=cfg,
    )
    ok = any(result.values())
    return {"success": ok, "data": result, "message": "通知已尝试发送" if ok else "通知发送失败，详见服务端日志"}


# ----------------------------------------------------------
# 告警静默管理
# ----------------------------------------------------------

@router.get("/alerts/active", summary="获取当前活跃告警")
async def get_active_alerts(
    priority: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    from app.services.alert_silence_service import AlertSilenceManager
    records = await AlertSilenceManager.get_active_alerts(db, priority=priority, agent_id=agent_id)
    return {"items": [_alert_record_to_dict(r) for r in records], "total": len(records)}


@router.get("/alerts/stats", summary="告警统计")
async def get_alert_stats(db: AsyncSession = Depends(get_db)):
    from app.services.alert_silence_service import AlertSilenceManager
    stats = await AlertSilenceManager.get_alert_stats(db)
    return stats


@router.put("/alerts/{alert_id}/silence", summary="配置告警静默规则")
async def silence_alert(
    alert_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    from app.services.alert_silence_service import AlertSilenceManager
    silence_start = data.get("silence_start")
    silence_end = data.get("silence_end")
    if not silence_start or not silence_end:
        raise HTTPException(400, "silence_start 和 silence_end 不能为空")

    config = await AlertSilenceManager.silence_alert_config(
        db=db,
        config_id=alert_id,
        silence_start=silence_start,
        silence_end=silence_end,
        silence_days=data.get("silence_days"),
        cooldown_minutes=data.get("cooldown_minutes", 15),
    )
    if not config:
        raise HTTPException(404, "告警配置不存在")
    return _alert_config_to_dict(config)


@router.delete("/alerts/{alert_id}/silence", summary="清除告警静默规则")
async def clear_alert_silence(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
):
    from app.services.alert_silence_service import AlertSilenceManager
    config = await AlertSilenceManager.clear_silence(db, alert_id)
    if not config:
        raise HTTPException(404, "告警配置不存在")
    return {"success": True}


@router.post("/alerts/batch-resolve", summary="批量解除告警")
async def batch_resolve_alerts(
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    from app.services.alert_silence_service import AlertSilenceManager
    agent_id = data.get("agent_id")
    count = await AlertSilenceManager.batch_resolve(db, agent_id=agent_id)
    return {"resolved": count}


# ----------------------------------------------------------
# 日志聚合
# ----------------------------------------------------------

@router.get("/logs/search", summary="搜索聚合日志")
async def search_logs(
    query: str = Query(""),
    level: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    backend: str = Query("elasticsearch"),
    size: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    from app.services.log_aggregation_service import get_log_aggregation_service
    svc = get_log_aggregation_service()
    result = await svc.search(query=query, level=level, agent_id=agent_id, backend=backend, size=size)
    return result


@router.get("/logs/health", summary="日志聚合后端健康检查")
async def log_backend_health():
    from app.services.log_aggregation_service import get_log_aggregation_service
    svc = get_log_aggregation_service()
    return await svc.health_check()