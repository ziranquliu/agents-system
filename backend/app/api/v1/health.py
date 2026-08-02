"""
各智能体健康监控 API
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.auth_service import get_current_user
from app.models.health import (
    HealthCheckRun, HealthSnapshot, HealthScoreWeight, AgentHealthConfig,
    HealthTrendPoint, HealthEvent,
    HealthLevel, CheckStatus, AgentHealthStatus,
)
from app.services.health_service import (
    HealthCheckExecutor, HealthScoringService, HealthPanelService,
    HealthConfigService,
)

router = APIRouter(prefix="/api/v1/health", tags=["各智能体健康监控"], dependencies=[Depends(get_current_user)])

JSON_FIELDS = {"details", "score_details", "l3_failed_items", "apply_agents", "l3_skills", "l3_mcp_servers"}


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


# ==================== 健康检查执行 ====================

@router.post("/check", summary="执行健康检查")
async def run_check(
    body: dict,
    session: AsyncSession = Depends(get_db),
):
    agent_id = body["agent_id"]
    agent_name = body.get("agent_name", agent_id)
    level_str = body.get("level")
    level = HealthLevel(level_str) if level_str else None

    snapshot = await HealthCheckExecutor.run_full_check(session, agent_id, agent_name, level)

    # 计算评分（仅全量检查时）
    if not level:
        metrics = body.get("metrics")
        snapshot = await HealthScoringService.score_snapshot(session, snapshot, metrics)
        # 记录趋势点
        await HealthScoringService.save_trend_point(session, agent_id, snapshot.score)
        # 状态变更事件
        await HealthPanelService.create_event(
            session, agent_id, agent_name,
            event_type="check",
            level="info" if snapshot.status == AgentHealthStatus.HEALTHY else "warning",
            message=f"健康检查完成，评分 {snapshot.score}，状态 {snapshot.status}",
            score_after=snapshot.score,
        )

    await session.commit()
    return {"code": 0, "data": _serialize(snapshot), "message": "检查完成"}


@router.get("/check-runs", summary="检查执行记录")
async def list_check_runs(
    agent_id: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
):
    runs = await HealthPanelService.list_check_runs(session, agent_id, level, limit)
    return {"items": _serialize_list(runs), "total": len(runs)}


# ==================== 健康快照/面板 ====================

@router.get("/snapshots", summary="Agent 健康列表")
async def list_snapshots(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
):
    items, total = await HealthPanelService.get_all_snapshots(session, skip, limit, status)
    return {"items": _serialize_list(items), "total": total, "skip": skip, "limit": limit}


@router.get("/snapshots/{agent_id}", summary="Agent 健康详情")
async def get_snapshot(
    agent_id: str,
    session: AsyncSession = Depends(get_db),
):
    snapshot = await HealthPanelService.get_snapshot(session, agent_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="该 Agent 尚无健康快照，请先执行健康检查")
    return _serialize(snapshot)


@router.get("/top5/healthy", summary="Top5 健康 Agent")
async def top5_healthy(
    session: AsyncSession = Depends(get_db),
):
    items = await HealthPanelService.get_top5_healthy(session)
    return {"items": _serialize_list(items)}


@router.get("/top5/unhealthy", summary="Top5 亚健康 Agent")
async def top5_unhealthy(
    session: AsyncSession = Depends(get_db),
):
    items = await HealthPanelService.get_top5_unhealthy(session)
    return {"items": _serialize_list(items)}


@router.get("/trend", summary="健康趋势")
async def health_trend(
    agent_id: Optional[str] = None,
    hours: int = Query(24, ge=1, le=168),
    session: AsyncSession = Depends(get_db),
):
    trend = await HealthPanelService.get_trend(session, agent_id, hours)
    return {"items": trend}


@router.get("/overview", summary="健康概览")
async def health_overview(
    session: AsyncSession = Depends(get_db),
):
    return await HealthPanelService.get_overview(session)


@router.get("/events", summary="健康事件")
async def health_events(
    agent_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
):
    items = await HealthPanelService.list_events(session, agent_id, limit)
    return {"items": _serialize_list(items)}


# ==================== 权重模板 ====================

@router.get("/weights", summary="权重模板列表")
async def list_weight_templates(
    session: AsyncSession = Depends(get_db),
):
    stmt = select(HealthScoreWeight).order_by(HealthScoreWeight.created_at.desc())
    result = await session.execute(stmt)
    return {"items": _serialize_list(result.scalars().all())}


@router.post("/weights", summary="创建/更新权重模板")
async def upsert_weight_template(
    body: dict,
    session: AsyncSession = Depends(get_db),
):
    # 如果设置默认，先清除其他默认
    if body.get("is_default"):
        update_stmt = select(HealthScoreWeight).where(HealthScoreWeight.is_default == True)
        update_result = await session.execute(update_stmt)
        for tpl in update_result.scalars().all():
            tpl.is_default = False

    tpl = HealthScoreWeight(
        template_name=body.get("template_name", "未命名模板"),
        description=body.get("description"),
        weight_response_time=body.get("weight_response_time", 30.0),
        weight_token=body.get("weight_token", 20.0),
        weight_error_rate=body.get("weight_error_rate", 25.0),
        weight_session_success=body.get("weight_session_success", 15.0),
        weight_dependency=body.get("weight_dependency", 10.0),
        threshold_p95_warn_ms=body.get("threshold_p95_warn_ms", 5000),
        threshold_p95_critical_ms=body.get("threshold_p95_critical_ms", 10000),
        threshold_error_rate_warn=body.get("threshold_error_rate_warn", 1.0),
        threshold_error_rate_critical=body.get("threshold_error_rate_critical", 5.0),
        threshold_session_success_warn=body.get("threshold_session_success_warn", 95.0),
        threshold_session_success_critical=body.get("threshold_session_success_critical", 80.0),
        apply_agents=json.dumps(body.get("apply_agents", [])) if body.get("apply_agents") is not None else None,
        is_default=body.get("is_default", False),
        enabled=body.get("enabled", True),
    )
    session.add(tpl)
    await session.flush()
    await session.commit()
    return {"code": 0, "data": _serialize(tpl), "message": "权重模板已保存"}


@router.delete("/weights/{template_id}", summary="删除权重模板")
async def delete_weight_template(
    template_id: str,
    session: AsyncSession = Depends(get_db),
):
    stmt = select(HealthScoreWeight).where(HealthScoreWeight.id == template_id)
    result = await session.execute(stmt)
    tpl = result.scalar_one_or_none()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    tpl.enabled = False
    await session.commit()
    return {"code": 0, "message": "模板已停用"}


# ==================== 检查配置 ====================

@router.get("/configs", summary="健康检查配置列表")
async def list_configs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
):
    items, total = await HealthConfigService.list_configs(session, skip, limit)
    return {"items": _serialize_list(items), "total": total}


@router.post("/configs", summary="创建/更新检查配置")
async def upsert_config(
    body: dict,
    session: AsyncSession = Depends(get_db),
):
    config = await HealthConfigService.upsert_config(
        session,
        agent_id=body["agent_id"],
        agent_name=body.get("agent_name", body["agent_id"]),
        l1_interval_sec=body.get("l1_interval_sec", 10),
        l2_interval_sec=body.get("l2_interval_sec", 30),
        l3_interval_sec=body.get("l3_interval_sec", 300),
        l4_interval_sec=body.get("l4_interval_sec", 900),
        ready_endpoint=body.get("ready_endpoint"),
        pid=body.get("pid"),
        process_name=body.get("process_name"),
        l3_skills=json.dumps(body.get("l3_skills", [])) if body.get("l3_skills") is not None else None,
        l3_mcp_servers=json.dumps(body.get("l3_mcp_servers", [])) if body.get("l3_mcp_servers") is not None else None,
        l3_model_id=body.get("l3_model_id"),
        l4_test_prompt=body.get("l4_test_prompt"),
        auto_restart_on_l1_fail=body.get("auto_restart_on_l1_fail", True),
        enabled=body.get("enabled", True),
    )
    await session.commit()
    return {"code": 0, "data": _serialize(config), "message": "配置已保存"}


@router.delete("/configs/{agent_id}", summary="停用检查配置")
async def delete_config(
    agent_id: str,
    session: AsyncSession = Depends(get_db),
):
    ok = await HealthConfigService.delete_config(session, agent_id)
    if not ok:
        raise HTTPException(status_code=404, detail="配置不存在")
    await session.commit()
    return {"code": 0, "message": "配置已停用"}


# ==================== 雷达对比 ====================

@router.post("/compare", summary="Agent 间健康对比（雷达数据）")
async def compare_agents(
    body: dict,
    session: AsyncSession = Depends(get_db),
):
    agent_ids = body.get("agent_ids", [])
    if not agent_ids:
        raise HTTPException(status_code=400, detail="请提供 agent_ids")
    result = []
    for aid in agent_ids:
        snapshot = await HealthPanelService.get_snapshot(session, aid)
        if not snapshot:
            continue
        details = {}
        try:
            details = json.loads(snapshot.score_details or "{}")
        except (json.JSONDecodeError, TypeError):
            pass
        deductions = details.get("deductions", {})
        result.append({
            "agent_id": snapshot.agent_id,
            "agent_name": snapshot.agent_name,
            "score": snapshot.score,
            "status": snapshot.status,
            "dimensions": {
                "response_time": 100 - deductions.get("response_time", 0) * 3,
                "token": 100 - deductions.get("token", 0) * 3,
                "error_rate": 100 - deductions.get("error_rate", 0) * 3,
                "session_success": 100 - deductions.get("session_success", 0) * 3,
                "dependency": 100 - deductions.get("dependency", 0) * 3,
            },
        })
    return {"items": result}