"""
本地组件扫描器 API - 触发扫描/查看结果/历史
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services import scanner_service

router = APIRouter(tags=["组件扫描器"])


class ScanSummary(BaseModel):
    checked: int = 0
    healthy: int = 0
    warning: int = 0
    error: int = 0


class ScanItem(BaseModel):
    id: str
    scan_id: str
    component_type: str
    component_id: str
    component_name: str | None = None
    status: str
    error_message: str | None = None
    details: dict | None = None
    scanned_at: str | None = None


class ScanSession(BaseModel):
    id: str
    status: str
    summary: ScanSummary | None = None
    started_at: str | None = None
    completed_at: str | None = None
    triggered_by: str | None = None


@router.post("/scanner/trigger")
async def trigger_scan(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """触发一次手动扫描"""
    scan = await scanner_service.trigger_scan(user_id=current_user.id)
    return {"message": "扫描已触发", "scan_id": scan.id}


@router.get("/scanner/latest")
async def get_latest_scan(
    db: AsyncSession = Depends(get_db),
):
    """获取最近一次扫描"""
    scan = await scanner_service.get_latest_scan(db)
    if not scan:
        return {"scan": None}
    return {"scan": _format_scan(scan)}


@router.get("/scanner/history")
async def get_scan_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """获取扫描历史"""
    scans, total = await scanner_service.get_scan_history(db, page=page, page_size=page_size)
    return {
        "scans": [_format_scan(s) for s in scans],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/scanner/results/{scan_id}")
async def get_scan_results(
    scan_id: str,
    component_type: str | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取特定扫描的详细结果"""
    items = await scanner_service.get_scan_items(db, scan_id, component_type=component_type, status_filter=status)
    return {"items": [_format_item(i) for i in items]}


@router.post("/scanner/cleanup")
async def cleanup_old_scans(
    keep_count: int = Query(30, ge=5, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """清理旧的扫描记录"""
    deleted = await scanner_service.clean_old_scans(db, keep_count=keep_count)
    return {"message": f"已清理旧记录", "deleted": deleted, "keep_count": keep_count}


@router.get("/scanner/alerts")
async def get_scan_alerts(
    status: str | None = Query(None),
    severity: str | None = Query(None),
    component_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """扫描变化告警列表（状态降级/异常/恢复）"""
    from sqlalchemy import select, func
    from app.models.scanner import ScannerAlert
    filters = []
    if status:
        filters.append(ScannerAlert.status == status)
    if severity:
        filters.append(ScannerAlert.severity == severity)
    if component_type:
        filters.append(ScannerAlert.component_type == component_type)
    total = (await db.execute(select(func.count()).select_from(ScannerAlert).where(*filters))).scalar() or 0
    rows = (await db.execute(
        select(ScannerAlert).where(*filters)
        .order_by(ScannerAlert.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [{
            "id": a.id,
            "component_type": a.component_type,
            "component_id": a.component_id,
            "component_name": a.component_name,
            "previous_status": a.previous_status,
            "current_status": a.current_status,
            "severity": a.severity,
            "message": a.message,
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        } for a in rows],
    }


@router.patch("/scanner/alerts/{alert_id}")
async def update_scan_alert(
    alert_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新扫描告警状态（acknowledged/resolved）"""
    from sqlalchemy import select
    from app.models.scanner import ScannerAlert
    alert = (await db.execute(select(ScannerAlert).where(ScannerAlert.id == alert_id))).scalars().first()
    if not alert:
        raise HTTPException(404, "告警不存在")
    if body.get("status") in ("open", "acknowledged", "resolved"):
        alert.status = body["status"]
    await db.commit()
    return {"id": alert_id, "status": alert.status}


def _format_scan(scan) -> dict:
    import json
    summary = None
    if scan.summary:
        try:
            summary = json.loads(scan.summary)
        except (json.JSONDecodeError, TypeError):
            summary = {"checked": 0, "healthy": 0, "warning": 0, "error": 0}
    return {
        "id": scan.id,
        "status": scan.status,
        "summary": summary,
        "started_at": scan.started_at.isoformat() if scan.started_at else None,
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        "triggered_by": scan.triggered_by,
    }


def _format_item(item) -> dict:
    import json
    details = None
    if item.details:
        try:
            details = json.loads(item.details)
        except (json.JSONDecodeError, TypeError):
            details = {}
    return {
        "id": item.id,
        "scan_id": item.scan_id,
        "component_type": item.component_type,
        "component_id": item.component_id,
        "component_name": item.component_name,
        "status": item.status,
        "error_message": item.error_message,
        "details": details,
        "scanned_at": item.scanned_at.isoformat() if item.scanned_at else None,
    }
