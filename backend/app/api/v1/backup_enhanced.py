"""
各智能体备份与恢复(增强) API
"""
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.backup_enhanced import (
    BackupRecord, BackupPolicy, BackupEventLog, RestoreOperation,
    RestoreDrill, EncryptionKey,
    BackupType, BackupStatus, BackupScope,
    RestoreType, RestoreStatus, DrillStatus, EncryptionAlgo,
)
from app.services.backup_enhanced_service import (
    KeyManager, BackupEnhancedService, RestoreService, DrillService,
)

router = APIRouter(prefix="/api/v1/backup-enhanced", tags=["各智能体备份与恢复(增强)"])

JSON_FIELDS = {"data_stats", "precheck_result", "restored_stats", "report_data", "event_meta", "event_types"}


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


# ==================== 备份策略 ====================

@router.get("/policies", summary="备份策略列表")
async def list_policies(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    enabled_only: bool = False,
    session: AsyncSession = Depends(deps.get_session),
):
    items, total = await BackupEnhancedService.list_policies(session, skip, limit, enabled_only)
    return {"items": _serialize_list(items), "total": total, "skip": skip, "limit": limit}


@router.post("/policies", summary="创建/更新备份策略")
async def upsert_policy(
    body: dict,
    session: AsyncSession = Depends(deps.get_session),
):
    policy = await BackupEnhancedService.upsert_policy(
        session,
        agent_id=body["agent_id"],
        agent_name=body["agent_name"],
        enabled=body.get("enabled", True),
        full_backup_cron=body.get("full_backup_cron", "0 3 * * *"),
        incremental_interval_hours=body.get("incremental_interval_hours", 6),
        event_trigger_enabled=body.get("event_trigger_enabled", True),
        event_types=json.dumps(body.get("event_types", [])) if body.get("event_types") is not None else None,
        encryption_enabled=body.get("encryption_enabled", True),
        retention_full_count=body.get("retention_full_count", 7),
        retention_incremental_count=body.get("retention_incremental_count", 48),
        retention_days=body.get("retention_days", 90),
        drill_enabled=body.get("drill_enabled", True),
        drill_cron=body.get("drill_cron", "0 4 * * 0"),
        default_scope=BackupScope(body.get("default_scope", "all")),
    )
    return {"code": 0, "data": _serialize(policy), "message": "策略已保存"}


@router.get("/policies/agent/{agent_id}", summary="按 Agent 查询策略")
async def get_policy_by_agent(
    agent_id: str,
    session: AsyncSession = Depends(deps.get_session),
):
    policy = await BackupEnhancedService.get_policy(session, agent_id)
    if not policy:
        raise HTTPException(status_code=404, detail="策略不存在")
    return _serialize(policy)


@router.delete("/policies/{policy_id}", summary="删除备份策略")
async def delete_policy(
    policy_id: str,
    session: AsyncSession = Depends(deps.get_session),
):
    ok = await BackupEnhancedService.delete_policy(session, policy_id)
    if not ok:
        raise HTTPException(status_code=404, detail="策略不存在")
    return {"code": 0, "message": "策略已停用"}


# ==================== 备份记录 ====================

@router.post("/backups", summary="创建备份")
async def create_backup(
    body: dict,
    session: AsyncSession = Depends(deps.get_session),
):
    record = await BackupEnhancedService.create_backup(
        session,
        agent_id=body["agent_id"],
        agent_name=body.get("agent_name", body["agent_id"]),
        backup_type=BackupType(body.get("backup_type", "full")),
        scope=BackupScope(body.get("scope", "all")),
        created_by=body.get("created_by", "system"),
        encryption_enabled=body.get("encryption_enabled"),
    )
    return {"code": 0, "data": _serialize(record), "message": "备份完成" if record.status == BackupStatus.SUCCESS else "备份失败"}


@router.get("/backups", summary="备份记录列表")
async def list_backups(
    agent_id: Optional[str] = None,
    backup_type: Optional[BackupType] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(deps.get_session),
):
    items, total = await BackupEnhancedService.list_backups(session, agent_id, backup_type, skip, limit)
    return {"items": _serialize_list(items), "total": total, "skip": skip, "limit": limit}


@router.get("/backups/{backup_id}", summary="备份详情")
async def get_backup(
    backup_id: str,
    session: AsyncSession = Depends(deps.get_session),
):
    record = await BackupEnhancedService.get_backup(session, backup_id)
    if not record:
        raise HTTPException(status_code=404, detail="备份不存在")
    return _serialize(record)


@router.delete("/backups/{backup_id}", summary="删除备份")
async def delete_backup(
    backup_id: str,
    session: AsyncSession = Depends(deps.get_session),
):
    ok = await BackupEnhancedService.delete_backup(session, backup_id)
    if not ok:
        raise HTTPException(status_code=404, detail="备份不存在")
    return {"code": 0, "message": "已删除"}


@router.get("/stats", summary="备份统计")
async def backup_stats(
    days: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(deps.get_session),
):
    return {"code": 0, "data": await BackupEnhancedService.get_stats(session, days)}


# ==================== 事件触发 ====================

@router.post("/events", summary="事件触发备份")
async def trigger_event_backup(
    body: dict,
    session: AsyncSession = Depends(deps.get_session),
):
    """外部系统调用：发生配置变更/Skill 绑定等事件时自动备份"""
    record = await BackupEnhancedService.log_event(
        session,
        agent_id=body["agent_id"],
        event_type=body["event_type"],
        event_meta=body.get("event_meta"),
    )
    if not record:
        return {"code": 0, "data": None, "message": "事件未触发备份（策略未启用或类型不匹配）"}
    return {"code": 0, "data": _serialize(record), "message": "事件备份完成"}


@router.get("/events", summary="事件触发日志")
async def list_events(
    agent_id: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(deps.get_session),
):
    conditions = []
    if agent_id:
        conditions.append(BackupEventLog.agent_id == agent_id)
    stmt = (
        select(BackupEventLog)
        .where(*conditions)
        .order_by(BackupEventLog.triggered_at.desc())
        .offset(skip).limit(limit)
    )
    count_stmt = select(func.count(BackupEventLog.id)).where(*conditions)
    result = await session.execute(stmt)
    count_result = await session.execute(count_stmt)
    items = [_serialize(e) for e in result.scalars().all()]
    return {"items": items, "total": count_result.scalar() or 0, "skip": skip, "limit": limit}


# ==================== 恢复 ====================

@router.post("/restores", summary="创建恢复操作")
async def create_restore(
    body: dict,
    session: AsyncSession = Depends(deps.get_session),
):
    try:
        operation = await RestoreService.create_restore(
            session,
            backup_id=body["backup_id"],
            restore_type=RestoreType(body.get("restore_type", "full")),
            target_agent_id=body["target_agent_id"],
            target_agent_name=body.get("target_agent_name", body["target_agent_id"]),
            created_by=body.get("created_by", "system"),
        )
        return {"code": 0, "data": _serialize(operation), "message": "恢复完成" if operation.status == RestoreStatus.SUCCESS else "恢复失败"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/restores", summary="恢复操作列表")
async def list_restores(
    agent_id: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(deps.get_session),
):
    items, total = await RestoreService.list_restores(session, agent_id, skip, limit)
    return {"items": _serialize_list(items), "total": total, "skip": skip, "limit": limit}


@router.get("/restores/{restore_id}", summary="恢复详情")
async def get_restore(
    restore_id: str,
    session: AsyncSession = Depends(deps.get_session),
):
    operation = await RestoreService.get_restore(session, restore_id)
    if not operation:
        raise HTTPException(status_code=404, detail="恢复操作不存在")
    return _serialize(operation)


# ==================== 恢复演练 ====================

@router.post("/drills", summary="创建恢复演练")
async def create_drill(
    body: dict,
    session: AsyncSession = Depends(deps.get_session),
):
    drill = await DrillService.create_drill(
        session,
        agent_id=body["agent_id"],
        agent_name=body.get("agent_name", body["agent_id"]),
        backup_id=body["backup_id"],
        created_by=body.get("created_by", "system"),
    )
    return {"code": 0, "data": _serialize(drill), "message": "演练已开始"}


@router.post("/drills/{drill_id}/complete", summary="完成恢复演练")
async def complete_drill(
    drill_id: str,
    body: dict,
    session: AsyncSession = Depends(deps.get_session),
):
    drill = await DrillService.complete_drill(
        session,
        drill_id,
        restore_ok=body.get("restore_ok", True),
        report_data=body.get("report_data"),
        error_message=body.get("error_message"),
    )
    if not drill:
        raise HTTPException(status_code=404, detail="演练不存在")
    return {"code": 0, "data": _serialize(drill), "message": "演练完成"}


@router.get("/drills", summary="演练记录列表")
async def list_drills(
    agent_id: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(deps.get_session),
):
    items, total = await DrillService.list_drills(session, agent_id, skip, limit)
    return {"items": _serialize_list(items), "total": total, "skip": skip, "limit": limit}


@router.get("/drills/stats", summary="演练统计")
async def drill_stats(
    days: int = Query(90, ge=1, le=365),
    session: AsyncSession = Depends(deps.get_session),
):
    return {"code": 0, "data": await DrillService.get_drill_stats(session, days)}


# ==================== 密钥管理 ====================

@router.post("/keys/rotate", summary="轮换加密密钥")
async def rotate_key(
    body: dict,
    session: AsyncSession = Depends(deps.get_session),
):
    key = await KeyManager.create_key(session, note=body.get("note"))
    return {"code": 0, "data": _serialize(key), "message": "密钥已轮换，旧密钥已停用"}


@router.get("/keys", summary="密钥列表")
async def list_keys(
    session: AsyncSession = Depends(deps.get_session),
):
    items, total = await KeyManager.list_keys(session)
    return {"items": _serialize_list(items), "total": total}


@router.get("/dashboard", summary="备份恢复概览")
async def backup_dashboard(
    session: AsyncSession = Depends(deps.get_session),
):
    stats = await BackupEnhancedService.get_stats(session, days=30)
    drill_stats = await DrillService.get_drill_stats(session, days=90)
    # 最近备份
    recent_stmt = (
        select(BackupRecord)
        .where(BackupRecord.is_deleted == False)
        .order_by(BackupRecord.created_at.desc())
        .limit(5)
    )
    recent_result = await session.execute(recent_stmt)
    recent = [_serialize(r) for r in recent_result.scalars().all()]

    # 启用策略数
    policy_stmt = select(func.count(BackupPolicy.id)).where(BackupPolicy.enabled == True)
    policy_result = await session.execute(policy_stmt)

    # 加密备份占比
    enc_stmt = select(func.count(BackupRecord.id)).where(
        and_(
            BackupRecord.encryption_algo == EncryptionAlgo.AES_256_GCM,
            BackupRecord.is_deleted == False,
        )
    )
    enc_result = await session.execute(enc_stmt)

    return {
        "stats": stats,
        "drills": drill_stats,
        "recent_backups": recent,
        "active_policies": policy_result.scalar() or 0,
        "encrypted_backups": enc_result.scalar() or 0,
    }
