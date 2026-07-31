"""
智能体自动化运维 API
"""
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.ops import (
    AgentDeployment, AgentDeploymentStatus,
    ScalingPolicy, ScalingEvent, ScalingMetricType, ScalingDirection,
    LogEntry, LogCollectionConfig, LogLevel, LogSourceType,
    MaintenanceTask, MaintenanceExecution, MaintenanceType,
    SelfHealRecord, HealRule, HealLevel, HealStatus,
    OpsReport, ReportType,
)
from app.services.ops_service import (
    DeploymentService, AutoScalingService, LogService,
    MaintenanceService, SelfHealService, ReportService,
    _safe_json_loads,
)

router = APIRouter(prefix="/api/v1/ops", tags=["智能体自动化运维"])


# ==================== 4.22.1 自动部署 ====================

@router.get("/deployments", summary="部署记录列表")
async def list_deployments(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[AgentDeploymentStatus] = None,
    agent_name: Optional[str] = None,
    session: AsyncSession = Depends(deps.get_session),
):
    items, total = await DeploymentService.list_deployments(session, skip, limit, status, agent_name)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.post("/deployments", summary="创建部署")
async def create_deployment(
    body: dict,
    session: AsyncSession = Depends(deps.get_session),
):
    dep = await DeploymentService.create_deployment(
        session=session,
        agent_name=body.get("agent_name"),
        template_yaml=body.get("template_yaml"),
        version=body.get("version", "1.0.0"),
        parameters=body.get("parameters"),
        created_by=body.get("created_by", "system"),
    )
    return {"code": 0, "data": dep, "message": "部署记录已创建"}


@router.get("/deployments/{dep_id}", summary="部署详情")
async def get_deployment(
    dep_id: str,
    session: AsyncSession = Depends(deps.get_session),
):
    dep = await DeploymentService.get_deployment(session, dep_id)
    if not dep:
        raise HTTPException(status_code=404, detail="部署记录不存在")
    return dep


@router.post("/deployments/{dep_id}/status", summary="更新部署状态")
async def update_deployment_status(
    dep_id: str,
    body: dict,
    session: AsyncSession = Depends(deps.get_session),
):
    dep = await DeploymentService.update_status(
        session,
        dep_id,
        status=AgentDeploymentStatus(body.get("status")),
        error_message=body.get("error_message"),
        health_score=body.get("health_score"),
    )
    if not dep:
        raise HTTPException(status_code=404, detail="部署记录不存在")
    return {"code": 0, "data": dep, "message": "状态已更新"}


@router.post("/deployments/{dep_id}/rollback", summary="回滚部署")
async def rollback_deployment(
    dep_id: str,
    session: AsyncSession = Depends(deps.get_session),
):
    dep = await DeploymentService.rollback_deployment(session, dep_id)
    if not dep:
        raise HTTPException(status_code=404, detail="部署记录不存在")
    return {"code": 0, "data": dep, "message": "已回滚"}


@router.delete("/deployments/{dep_id}", summary="删除部署记录")
async def delete_deployment(
    dep_id: str,
    session: AsyncSession = Depends(deps.get_session),
):
    ok = await DeploymentService.delete_deployment(session, dep_id)
    if not ok:
        raise HTTPException(status_code=404, detail="部署记录不存在")
    return {"code": 0, "message": "已删除"}


@router.get("/deployments/stats", summary="部署统计")
async def deployment_stats(
    session: AsyncSession = Depends(deps.get_session),
):
    return await DeploymentService.get_stats(session)


# ==================== 4.22.2 Auto Scaling ====================

@router.get("/scaling/policies", summary="扩缩容策略列表")
async def list_scaling_policies(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    enabled_only: bool = False,
    session: AsyncSession = Depends(deps.get_session),
):
    items, total = await AutoScalingService.list_policies(session, skip, limit, enabled_only)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.post("/scaling/policies", summary="创建/更新扩缩容策略")
async def upsert_scaling_policy(
    body: dict,
    session: AsyncSession = Depends(deps.get_session),
):
    policy = await AutoScalingService.upsert_policy(
        session,
        agent_id=body["agent_id"],
        agent_name=body["agent_name"],
        metric_type=ScalingMetricType(body.get("metric_type", "cpu_usage")),
        scale_out_threshold=body.get("scale_out_threshold", 70.0),
        scale_in_threshold=body.get("scale_in_threshold", 30.0),
        min_instances=body.get("min_instances", 1),
        max_instances=body.get("max_instances", 10),
        scale_out_cooldown=body.get("scale_out_cooldown", 60),
        scale_in_cooldown=body.get("scale_in_cooldown", 180),
        scale_out_step=body.get("scale_out_step", 2),
        scale_in_step=body.get("scale_in_step", 1),
        enabled=body.get("enabled", True),
    )
    return {"code": 0, "data": policy, "message": "策略已保存"}


@router.get("/scaling/policies/{policy_id}", summary="扩缩容策略详情")
async def get_scaling_policy(
    policy_id: str,
    session: AsyncSession = Depends(deps.get_session),
):
    policy = await AutoScalingService.get_policy(session, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="策略不存在")
    return policy


@router.post("/scaling/evaluate", summary="评估扩缩容")
async def evaluate_scaling(
    body: dict,
    session: AsyncSession = Depends(deps.get_session),
):
    event = await AutoScalingService.evaluate_scaling(
        session,
        agent_id=body["agent_id"],
        current_instances=body["current_instances"],
        metric_type=ScalingMetricType(body["metric_type"]),
        metric_value=body["metric_value"],
    )
    if not event:
        return {"code": 0, "data": None, "message": "无需扩缩容或冷却中"}
    return {"code": 0, "data": event, "message": f"触发{event.direction.value}"}


@router.get("/scaling/events", summary="扩缩容事件记录")
async def list_scaling_events(
    agent_id: Optional[str] = None,
    days: int = Query(7, ge=1, le=90),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(deps.get_session),
):
    items, total = await AutoScalingService.list_events(session, agent_id, skip, limit, days)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/scaling/stats", summary="扩缩容统计")
async def scaling_stats(
    days: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(deps.get_session),
):
    return {"code": 0, "data": await AutoScalingService.get_scaling_stats(session, days)}


# ==================== 4.22.3 日志管理 ====================

@router.post("/logs/ingest", summary="写入日志")
async def ingest_log(
    body: dict,
    session: AsyncSession = Depends(deps.get_session),
):
    entry = await LogService.ingest_log(
        session,
        level=LogLevel(body.get("level", "INFO")),
        logger_name=body.get("logger", "system"),
        message=body.get("message", ""),
        source_type=LogSourceType(body.get("source_type", "system")),
        source_id=body.get("source_id"),
        agent_id=body.get("agent_id"),
        trace_id=body.get("trace_id"),
        metadata=body.get("metadata"),
    )
    return {"code": 0, "data": entry, "message": "日志已写入"}


@router.get("/logs", summary="搜索日志")
async def search_logs(
    level: Optional[LogLevel] = None,
    logger: Optional[str] = None,
    source_type: Optional[LogSourceType] = None,
    agent_id: Optional[str] = None,
    keyword: Optional[str] = None,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(deps.get_session),
):
    items, total = await LogService.search_logs(
        session, level, logger, source_type, agent_id,
        keyword, from_time, to_time, skip, limit,
    )
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/logs/stats", summary="日志统计")
async def log_stats(
    days: int = Query(7, ge=1, le=90),
    session: AsyncSession = Depends(deps.get_session),
):
    return await LogService.get_log_stats(session, days)


@router.get("/logs/configs", summary="日志采集配置列表")
async def list_log_configs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(deps.get_session),
):
    items, total = await LogService.list_collection_configs(session, skip, limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.post("/logs/configs", summary="创建/更新日志采集配置")
async def upsert_log_config(
    body: dict,
    session: AsyncSession = Depends(deps.get_session),
):
    config = await LogService.upsert_collection_config(
        session,
        agent_id=body["agent_id"],
        log_level=LogLevel(body.get("log_level", "INFO")),
        enabled=body.get("enabled", True),
        sources=json.dumps(body.get("sources", ["agent", "skill", "mcp", "system"])),
        rotation_size_mb=body.get("rotation_size_mb", 500),
        rotation_interval_days=body.get("rotation_interval_days", 1),
        retention_days=body.get("retention_days", 30),
    )
    return {"code": 0, "data": config, "message": "配置已保存"}


# ==================== 4.22.4 定期维护 ====================

@router.get("/maintenance/tasks", summary="维护任务列表")
async def list_maintenance_tasks(
    task_type: Optional[MaintenanceType] = None,
    enabled_only: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(deps.get_session),
):
    items, total = await MaintenanceService.list_tasks(session, skip, limit, task_type, enabled_only)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.post("/maintenance/tasks", summary="创建维护任务")
async def create_maintenance_task(
    body: dict,
    session: AsyncSession = Depends(deps.get_session),
):
    task = await MaintenanceService.create_task(
        session,
        task_type=MaintenanceType(body["task_type"]),
        name=body["name"],
        cron_expression=body["cron_expression"],
        description=body.get("description"),
        maintenance_window_start=body.get("maintenance_window_start"),
        maintenance_window_end=body.get("maintenance_window_end"),
        timeout_seconds=body.get("timeout_seconds", 3600),
    )
    return {"code": 0, "data": task, "message": "维护任务已创建"}


@router.get("/maintenance/tasks/{task_id}", summary="维护任务详情")
async def get_maintenance_task(
    task_id: str,
    session: AsyncSession = Depends(deps.get_session),
):
    task = await MaintenanceService.get_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="维护任务不存在")
    return task


@router.put("/maintenance/tasks/{task_id}", summary="更新维护任务")
async def update_maintenance_task(
    task_id: str,
    body: dict,
    session: AsyncSession = Depends(deps.get_session),
):
    task = await MaintenanceService.update_task(session, task_id, **body)
    if not task:
        raise HTTPException(status_code=404, detail="维护任务不存在")
    return {"code": 0, "data": task, "message": "已更新"}


@router.delete("/maintenance/tasks/{task_id}", summary="删除维护任务")
async def delete_maintenance_task(
    task_id: str,
    session: AsyncSession = Depends(deps.get_session),
):
    ok = await MaintenanceService.delete_task(session, task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="维护任务不存在")
    return {"code": 0, "message": "已删除"}


@router.post("/maintenance/tasks/{task_id}/execute", summary="执行维护任务")
async def execute_maintenance_task(
    task_id: str,
    body: dict,
    session: AsyncSession = Depends(deps.get_session),
):
    exec_record = await MaintenanceService.execute_task(
        session,
        task_id,
        items_processed=body.get("items_processed", 0),
        items_cleaned=body.get("items_cleaned", 0),
        status=body.get("status", "success"),
        error_message=body.get("error_message"),
    )
    if not exec_record:
        raise HTTPException(status_code=404, detail="维护任务不存在")
    return {"code": 0, "data": exec_record, "message": "执行记录已保存"}


@router.get("/maintenance/executions", summary="维护执行记录")
async def list_maintenance_executions(
    task_id: Optional[str] = None,
    days: int = Query(7, ge=1, le=90),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(deps.get_session),
):
    items, total = await MaintenanceService.list_executions(session, task_id, skip, limit, days)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


# ==================== 4.22.5 异常自愈 ====================

@router.get("/heal/rules", summary="自愈规则列表")
async def list_heal_rules(
    agent_id: Optional[str] = None,
    enabled_only: bool = False,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(deps.get_session),
):
    items, total = await SelfHealService.list_rules(session, agent_id, enabled_only, skip, limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.post("/heal/rules", summary="创建自愈规则")
async def create_heal_rule(
    body: dict,
    session: AsyncSession = Depends(deps.get_session),
):
    rule = await SelfHealService.create_rule(
        session,
        agent_id=body["agent_id"],
        anomaly_type=body["anomaly_type"],
        heal_level=HealLevel(body.get("heal_level", "restart")),
        consecutive_threshold=body.get("consecutive_threshold", 3),
        error_rate_threshold=body.get("error_rate_threshold"),
        p99_latency_threshold_ms=body.get("p99_latency_threshold_ms"),
        health_drop_threshold=body.get("health_drop_threshold"),
        auto_heal=body.get("auto_heal", True),
        cooldown_seconds=body.get("cooldown_seconds", 300),
    )
    return {"code": 0, "data": rule, "message": "自愈规则已创建"}


@router.get("/heal/rules/{rule_id}", summary="自愈规则详情")
async def get_heal_rule(
    rule_id: str,
    session: AsyncSession = Depends(deps.get_session),
):
    rule = await SelfHealService.get_rule(session, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    return rule


@router.put("/heal/rules/{rule_id}", summary="更新自愈规则")
async def update_heal_rule(
    rule_id: str,
    body: dict,
    session: AsyncSession = Depends(deps.get_session),
):
    rule = await SelfHealService.update_rule(session, rule_id, **body)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    return {"code": 0, "data": rule, "message": "已更新"}


@router.delete("/heal/rules/{rule_id}", summary="删除自愈规则")
async def delete_heal_rule(
    rule_id: str,
    session: AsyncSession = Depends(deps.get_session),
):
    ok = await SelfHealService.delete_rule(session, rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="规则不存在")
    return {"code": 0, "message": "已删除"}


@router.post("/heal/trigger", summary="触发自愈")
async def trigger_heal(
    body: dict,
    session: AsyncSession = Depends(deps.get_session),
):
    record = await SelfHealService.trigger_heal(
        session,
        agent_id=body["agent_id"],
        agent_name=body["agent_name"],
        anomaly_type=body["anomaly_type"],
        anomaly_value=body["anomaly_value"],
        threshold_value=body["threshold_value"],
        heal_level=HealLevel(body.get("heal_level", "restart")),
        auto_heal=body.get("auto_heal", True),
    )
    return {"code": 0, "data": record, "message": "自愈事件已记录"}


@router.post("/heal/{record_id}/complete", summary="完成自愈")
async def complete_heal(
    record_id: str,
    body: dict,
    session: AsyncSession = Depends(deps.get_session),
):
    record = await SelfHealService.complete_heal(
        session,
        record_id,
        status=HealStatus(body.get("status", "success")),
        health_score_after=body.get("health_score_after"),
        verified=body.get("verified", False),
        error_message=body.get("error_message"),
    )
    if not record:
        raise HTTPException(status_code=404, detail="自愈记录不存在")
    return {"code": 0, "data": record, "message": "自愈完成"}


@router.get("/heal/records", summary="自愈记录列表")
async def list_heal_records(
    agent_id: Optional[str] = None,
    status: Optional[HealStatus] = None,
    days: int = Query(30, ge=1, le=365),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(deps.get_session),
):
    items, total = await SelfHealService.list_heal_records(session, agent_id, status, skip, limit, days)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/heal/stats", summary="自愈统计")
async def heal_stats(
    days: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(deps.get_session),
):
    return await SelfHealService.get_heal_stats(session, days)


# ==================== 4.22.6 运维报告 ====================

@router.post("/reports/generate", summary="生成运维报告")
async def generate_report(
    body: dict,
    session: AsyncSession = Depends(deps.get_session),
):
    period_end = datetime.utcnow()
    report_type = ReportType(body.get("report_type", "daily"))
    if report_type == ReportType.DAILY:
        period_start = period_end - timedelta(days=1)
    elif report_type == ReportType.WEEKLY:
        period_start = period_end - timedelta(weeks=1)
    else:
        period_start = period_end - timedelta(days=30)

    report = await ReportService.generate_report(session, report_type, period_start, period_end)
    return {"code": 0, "data": report, "message": "报告已生成"}


@router.get("/reports", summary="运维报告列表")
async def list_reports(
    report_type: Optional[ReportType] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(deps.get_session),
):
    items, total = await ReportService.list_reports(session, report_type, skip, limit)
    return {"items": items, "total": total, "skip": skip, "limit": limit}


@router.get("/reports/{report_id}", summary="运维报告详情")
async def get_report(
    report_id: str,
    session: AsyncSession = Depends(deps.get_session),
):
    report = await ReportService.get_report(session, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    return report


@router.delete("/reports/{report_id}", summary="删除运维报告")
async def delete_report(
    report_id: str,
    session: AsyncSession = Depends(deps.get_session),
):
    ok = await ReportService.delete_report(session, report_id)
    if not ok:
        raise HTTPException(status_code=404, detail="报告不存在")
    return {"code": 0, "message": "已删除"}


# ==================== 综合仪表盘 ====================

@router.get("/dashboard", summary="运维概览")
async def ops_dashboard(
    session: AsyncSession = Depends(deps.get_session),
):
    """综合运维概览数据"""
    deploy_stats = await DeploymentService.get_stats(session)
    scaling_stats = await AutoScalingService.get_scaling_stats(session, days=7)
    log_stats = await LogService.get_log_stats(session, days=1)
    heal_stats = await SelfHealService.get_heal_stats(session, days=7)

    return {
        "deployment": deploy_stats,
        "scaling": scaling_stats,
        "logs": {
            "today_count": log_stats.get("total", 0),
            "error_count": log_stats.get("by_level", {}).get("error", 0),
        },
        "healing": {
            "total": heal_stats.get("total", 0),
            "success_rate": heal_stats.get("success_rate", 100),
        },
    }
