"""
操作审计（增强）API
覆盖：审计日志写入/查询/校验、CSV 导出、SIEM 输出、异常行为检测、规则管理、配置管理
"""
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.audit import (
    AuditLog, AuditArchive, AuditRule, AuditAlert, AuditConfig,
    AuditCategory, AuditResult, AnomalyType, AlertSeverity,
)
from app.services.audit_service import (
    AuditService, HashChainService, SIEMExporter, AnomalyDetector,
)

router = APIRouter(prefix="/api/v1/audit", tags=["操作审计"])

CATEGORIES = [AuditCategory.USER, AuditCategory.AGENT, AuditCategory.SYSTEM, AuditCategory.SECURITY]
RESULTS = [AuditResult.SUCCESS, AuditResult.FAILURE, AuditResult.DENIED]


def _serialize(record, exclude=()):
    d = {}
    for col in record.__table__.columns:
        if col.name in exclude:
            continue
        val = getattr(record, col.name)
        if isinstance(val, datetime):
            val = val.isoformat()
        d[col.name] = val
    return d


def _serialize_list(records):
    return [_serialize(r) for r in records]


# ==================== 审计日志写入 ====================

@router.post("/logs", summary="写入审计日志（追加，自动哈希链）")
async def create_log(body: dict, session: AsyncSession = Depends(get_db)):
    category = body.get("category", AuditCategory.SYSTEM)
    if category not in CATEGORIES:
        raise HTTPException(400, f"无效分类: {category}")
    result = body.get("result", AuditResult.SUCCESS)
    if result not in RESULTS:
        raise HTTPException(400, f"无效结果: {result}")
    record = await AuditService.log(
        session,
        operator_id=body["operator_id"],
        action_type=body["action_type"],
        category=category,
        result=result,
        operator_name=body.get("operator_name"),
        operator_ip=body.get("operator_ip"),
        device_info=body.get("device_info"),
        target_id=body.get("target_id"),
        details=body.get("details"),
        failure_reason=body.get("failure_reason"),
        trace_id=body.get("trace_id"),
    )
    return _serialize(record)


# ==================== 审计查询 ====================

@router.get("/logs", summary="审计日志多维查询")
async def list_logs(
    operator_id: Optional[str] = None,
    action_type: Optional[str] = None,
    category: Optional[str] = None,
    target_id: Optional[str] = None,
    result: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
):
    data = await AuditService.query(
        session,
        operator_id=operator_id,
        action_type=action_type,
        category=category,
        target_id=target_id,
        result=result,
        start_time=start_time,
        end_time=end_time,
        page=page,
        page_size=page_size,
    )
    return {
        "total": data["total"],
        "page": data["page"],
        "page_size": data["page_size"],
        "items": _serialize_list(data["items"]),
    }


@router.get("/logs/{log_id}", summary="审计日志详情")
async def get_log(log_id: str, session: AsyncSession = Depends(get_db)):
    record = await session.get(AuditLog, log_id)
    if not record:
        raise HTTPException(404, "审计记录不存在")
    return _serialize(record)


@router.get("/stats", summary="审计统计（分类/结果分布 + 合规状态）")
async def get_stats(session: AsyncSession = Depends(get_db)):
    return await AuditService.stats(session)


# ==================== 防篡改校验 ====================

@router.get("/verify", summary="哈希链完整性校验（防篡改）")
async def verify_chain(session: AsyncSession = Depends(get_db)):
    return await HashChainService.verify_chain(session)


@router.post("/verify", summary="校验指定记录的哈希")
async def verify_record(body: dict, session: AsyncSession = Depends(get_db)):
    log_id = body.get("id")
    if not log_id:
        raise HTTPException(400, "缺少记录 id")
    record = await session.get(AuditLog, log_id)
    if not record:
        raise HTTPException(404, "审计记录不存在")
    record_dict = {c.name: getattr(record, c.name) for c in record.__table__.columns}
    expected = HashChainService.build_curr_hash(record_dict, record.prev_hash)
    return {"id": log_id, "valid": expected == record.curr_hash, "curr_hash": record.curr_hash}


# ==================== 导出与 SIEM ====================

@router.get("/export/csv", summary="CSV 导出（合规格式）")
async def export_csv(
    operator_id: Optional[str] = None,
    action_type: Optional[str] = None,
    category: Optional[str] = None,
    target_id: Optional[str] = None,
    result: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    session: AsyncSession = Depends(get_db),
):
    filters = {
        "operator_id": operator_id, "action_type": action_type, "category": category,
        "target_id": target_id, "result": result, "start_time": start_time, "end_time": end_time,
    }
    csv_text = await AuditService.export_csv(session, filters)
    filename = f"audit_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return PlainTextResponse(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/siem/export", summary="SIEM 集成：导出 Syslog 格式日志")
async def export_siem(
    minutes: int = Query(60, ge=1, le=1440),
    session: AsyncSession = Depends(get_db),
):
    lines = await SIEMExporter.export_recent(session, minutes=minutes)
    return PlainTextResponse(
        content="\n".join(lines),
        media_type="text/plain",
        headers={"Content-Disposition": "inline"},
    )


# ==================== 异常行为检测 ====================

@router.post("/anomalies/scan", summary="执行异常行为检测（内置规则引擎）")
async def run_anomaly_scan(session: AsyncSession = Depends(get_db)):
    return await AnomalyDetector.run_detection(session)


@router.get("/anomalies", summary="异常告警列表")
async def list_anomalies(
    alert_type: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
):
    filters = []
    if alert_type:
        filters.append(AuditAlert.alert_type == alert_type)
    if severity:
        filters.append(AuditAlert.severity == severity)
    if status:
        filters.append(AuditAlert.status == status)
    total = (await session.execute(select(func.count()).select_from(AuditAlert).where(*filters))).scalar() or 0
    stmt = (
        select(AuditAlert).where(*filters)
        .order_by(AuditAlert.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    records = (await session.execute(stmt)).scalars().all()
    return {"total": total, "page": page, "page_size": page_size, "items": _serialize_list(records)}


@router.patch("/anomalies/{alert_id}", summary="更新告警状态")
async def update_alert(alert_id: str, body: dict, session: AsyncSession = Depends(get_db)):
    alert = await session.get(AuditAlert, alert_id)
    if not alert:
        raise HTTPException(404, "告警不存在")
    if body.get("status") in ("open", "acknowledged", "resolved"):
        alert.status = body["status"]
    await session.commit()
    return _serialize(alert)


# ==================== 规则管理 ====================

@router.get("/rules", summary="异常检测规则列表")
async def list_rules(session: AsyncSession = Depends(get_db)):
    await AnomalyDetector.ensure_rules(session)
    records = (await session.execute(select(AuditRule))).scalars().all()
    return _serialize_list(records)


@router.post("/rules", summary="创建规则")
async def create_rule(body: dict, session: AsyncSession = Depends(get_db)):
    rule = AuditRule(
        rule_name=body.get("rule_name", "自定义规则"),
        rule_type=body["rule_type"],
        params=json.dumps(body.get("params", {}), ensure_ascii=False),
        enabled=body.get("enabled", True),
        severity=body.get("severity", "medium"),
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return _serialize(rule)


@router.put("/rules/{rule_id}", summary="更新规则")
async def update_rule(rule_id: str, body: dict, session: AsyncSession = Depends(get_db)):
    rule = await session.get(AuditRule, rule_id)
    if not rule:
        raise HTTPException(404, "规则不存在")
    if "rule_name" in body:
        rule.rule_name = body["rule_name"]
    if "rule_type" in body:
        rule.rule_type = body["rule_type"]
    if "params" in body:
        rule.params = json.dumps(body["params"], ensure_ascii=False)
    if "enabled" in body:
        rule.enabled = body["enabled"]
    if "severity" in body:
        rule.severity = body["severity"]
    await session.commit()
    return _serialize(rule)


@router.delete("/rules/{rule_id}", summary="删除规则")
async def delete_rule(rule_id: str, session: AsyncSession = Depends(get_db)):
    rule = await session.get(AuditRule, rule_id)
    if not rule:
        raise HTTPException(404, "规则不存在")
    await session.delete(rule)
    await session.commit()
    return {"deleted": True, "id": rule_id}


# ==================== 归档与合规 ====================

@router.get("/archives", summary="归档记录列表（冷热分离）")
async def list_archives(session: AsyncSession = Depends(get_db)):
    records = (await session.execute(select(AuditArchive).order_by(AuditArchive.created_at.desc()))).scalars().all()
    return _serialize_list(records)


@router.post("/archive", summary="执行归档（超过阈值自动归档）")
async def run_archive(session: AsyncSession = Depends(get_db)):
    return await AuditService.archive_old(session)


@router.post("/retention", summary="执行合规保留期清理")
async def run_retention(session: AsyncSession = Depends(get_db)):
    return await AuditService.enforce_retention(session)


# ==================== 审计配置 ====================

@router.get("/config", summary="审计配置（保留期/SIEM/脱敏）")
async def get_config(session: AsyncSession = Depends(get_db)):
    config = await AuditService.get_config(session)
    if not config:
        config = AuditConfig()
        session.add(config)
        await session.commit()
        await session.refresh(config)
    return _serialize(config)


@router.put("/config", summary="更新审计配置")
async def update_config(body: dict, session: AsyncSession = Depends(get_db)):
    allowed = {
        "retention_days", "archive_after_days", "rotation_size_mb",
        "siem_enabled", "siem_host", "siem_port", "siem_protocol", "mask_sensitive",
    }
    data = {k: v for k, v in body.items() if k in allowed}
    config = await AuditService.update_config(session, data)
    return _serialize(config)
