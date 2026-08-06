"""
高级功能 API — P0/P1/P2/P3 全部新服务的端点

覆盖：
- 预算告警 / 自愈 / 会话恢复 / 备份完整性
- 对话质量 / 健康评分 / 会话导出
- 知识库分块 / MCP 治理 / Skill 版本
- 自动扩缩容 / Agent 通信 / 定期维护
- 运维报告 / 增量备份
- 事件总线 / 追踪 / 审计哈希链
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


# ============================================================
# Request/Response Models
# ============================================================

class BudgetSetRequest(BaseModel):
    daily_limit_tokens: int = 0
    monthly_limit_tokens: int = 0
    daily_limit_cost: float = 0.0
    monthly_limit_cost: float = 0.0
    auto_downgrade_enabled: bool = True
    downgrade_model: str = "gpt-4o-mini"


class BudgetRecordRequest(BaseModel):
    tokens: int = 0
    cost: float = 0.0
    model: str = ""
    dimension: str = "global"
    dimension_id: str = "system"


class HealingTriggerRequest(BaseModel):
    agent_id: str
    error_rate: float = 0
    response_time_p99_ms: float = 0
    health_score: float = 100
    consecutive_failures: int = 0


class QualityScoreRequest(BaseModel):
    conversation_id: str
    agent_id: str
    messages: list[dict] = []
    resolved: bool = False


class CSATRequest(BaseModel):
    score: int
    comment: str = ""


class ExportRequest(BaseModel):
    session_ids: list[str]
    format: str = "markdown"
    include_metadata: bool = True


class ChunkingConfigRequest(BaseModel):
    strategy: str = "fixed_size"
    chunk_size: int = 500
    chunk_overlap: int = 50


class CanaryRequest(BaseModel):
    canary_version: str
    stable_version: str
    initial_percentage: int = 10


class VersionPublishRequest(BaseModel):
    version: str
    description: str = ""
    dependencies: list[dict] = []


class ScalingConfigRequest(BaseModel):
    metric: str = "cpu"
    target_value: float = 70
    scale_up_threshold: float = 80
    scale_down_threshold: float = 50
    min_instances: int = 1
    max_instances: int = 10


class RPCRequestModel(BaseModel):
    to_agent: str
    method: str
    params: dict = {}


class BlackboardWriteRequest(BaseModel):
    key: str
    value: dict
    metadata: dict = {}


# ============================================================
# 1. 预算告警
# ============================================================

_budget_service = None

def get_budget_service():
    global _budget_service
    if _budget_service is None:
        from app.services.budget_alert_service import BudgetAlertService, BudgetConfig, BudgetDimension
        _budget_service = BudgetAlertService()
    return _budget_service


@router.post("/budget/config")
async def set_budget_config(req: BudgetSetRequest):
    svc = get_budget_service()
    from app.services.budget_alert_service import BudgetConfig, BudgetDimension
    config = BudgetConfig(
        daily_limit_tokens=req.daily_limit_tokens,
        monthly_limit_tokens=req.monthly_limit_tokens,
        daily_limit_cost=req.daily_limit_cost,
        monthly_limit_cost=req.monthly_limit_cost,
        auto_downgrade_enabled=req.auto_downgrade_enabled,
        downgrade_model=req.downgrade_model,
    )
    svc.set_budget(config)
    return {"status": "ok"}


@router.post("/budget/record")
async def record_budget_usage(req: BudgetRecordRequest):
    svc = get_budget_service()
    from app.services.budget_alert_service import BudgetDimension
    dim = BudgetDimension(req.dimension)
    alerts = svc.record_usage(
        tokens=req.tokens, cost=req.cost, model=req.model,
        dimension=dim, dimension_id=req.dimension_id,
    )
    return {
        "alerts_triggered": len(alerts),
        "alerts": [
            {"level": a.level.value, "message": a.message, "auto_action": a.auto_action}
            for a in alerts
        ],
    }


@router.get("/budget/status")
async def get_budget_status(dimension: str = "global", dimension_id: str = "system"):
    svc = get_budget_service()
    from app.services.budget_alert_service import BudgetDimension
    return svc.get_budget_status(BudgetDimension(dimension), dimension_id)


@router.get("/budget/alerts")
async def get_budget_alerts(limit: int = 50):
    return get_budget_service().get_recent_alerts(limit)


# ============================================================
# 2. 自愈
# ============================================================

_healing_service = None

def get_healing_service():
    global _healing_service
    if _healing_service is None:
        from app.services.self_healing_service import SelfHealingService
        _healing_service = SelfHealingService()
    return _healing_service


@router.post("/healing/detect")
async def detect_anomalies(req: HealingTriggerRequest):
    svc = get_healing_service()
    anomalies = svc.detect_anomaly(req.agent_id, {
        "error_rate": req.error_rate,
        "response_time_p99_ms": req.response_time_p99_ms,
        "health_score": req.health_score,
        "consecutive_failures": req.consecutive_failures,
    })
    return {
        "anomalies_detected": len(anomalies),
        "anomalies": [
            {"type": a.anomaly_type.value, "severity": a.severity, "message": a.message}
            for a in anomalies
        ],
    }


@router.get("/healing/history")
async def get_healing_history(agent_id: Optional[str] = None, limit: int = 50):
    return get_healing_service().get_healing_history(agent_id, limit)


@router.get("/healing/stats")
async def get_healing_stats():
    return get_healing_service().get_healing_stats()


# ============================================================
# 3. 对话质量
# ============================================================

_quality_service = None

def get_quality_service():
    global _quality_service
    if _quality_service is None:
        from app.services.conversation_quality_service import ConversationQualityService
        _quality_service = ConversationQualityService()
    return _quality_service


@router.post("/quality/score")
async def score_conversation(req: QualityScoreRequest):
    svc = get_quality_service()
    score = svc.score_conversation(
        conversation_id=req.conversation_id,
        agent_id=req.agent_id,
        messages=req.messages,
        resolved=req.resolved,
    )
    return score.to_dict()


@router.get("/quality/ranking")
async def get_quality_ranking(limit: int = 20):
    return get_quality_service().get_agent_ranking(limit)


@router.get("/quality/stats")
async def get_quality_stats():
    return get_quality_service().get_overall_stats()


@router.get("/quality/trend")
async def get_quality_trend(agent_id: Optional[str] = None, days: int = 7):
    return get_quality_service().get_quality_trend(agent_id, days)


# ============================================================
# 4. 健康评分
# ============================================================

_health_scoring_service = None

def get_health_scoring_service():
    global _health_scoring_service
    if _health_scoring_service is None:
        from app.services.health_scoring_service import HealthScoringService
        _health_scoring_service = HealthScoringService()
    return _health_scoring_service


@router.post("/health-scoring/score")
async def score_health(agent_id: str, metrics: dict):
    svc = get_health_scoring_service()
    score = svc.score_agent(agent_id, metrics)
    return score.to_dict()


@router.get("/health-scoring/top-healthy")
async def get_top_healthy(limit: int = 5):
    return get_health_scoring_service().get_top_healthy(limit)


@router.get("/health-scoring/top-degraded")
async def get_top_degraded(limit: int = 5):
    return get_health_scoring_service().get_top_degraded(limit)


@router.get("/health-scoring/radar/{agent_id}")
async def get_radar_data(agent_ids: str = ""):
    ids = [a.strip() for a in agent_ids.split(",") if a.strip()] if agent_ids else None
    radar = get_health_scoring_service().get_radar_data(ids)
    return {
        "agents": radar.agents,
        "dimensions": radar.dimensions,
        "scores": radar.scores,
    }


@router.get("/health-scoring/stats")
async def get_health_scoring_stats():
    return get_health_scoring_service().get_overall_stats()


# ============================================================
# 5. 会话导出
# ============================================================

_export_service = None

def get_export_service():
    global _export_service
    if _export_service is None:
        from app.services.session_export_service import SessionExportService
        _export_service = SessionExportService()
    return _export_service


@router.post("/export/sessions")
async def export_sessions(req: ExportRequest):
    svc = get_export_service()
    from app.services.session_export_service import ExportFormat
    fmt = ExportFormat(req.format)
    result = await svc.export_sessions(
        session_ids=req.session_ids,
        format=fmt,
        include_metadata=req.include_metadata,
    )
    return result.to_dict()


@router.get("/export/history")
async def get_export_history(limit: int = 20):
    return get_export_service().get_history(limit)


# ============================================================
# 6. 知识库分块
# ============================================================

_chunking_service = None

def get_chunking_service():
    global _chunking_service
    if _chunking_service is None:
        from app.services.knowledge_chunking_service import KnowledgeChunkingService
        _chunking_service = KnowledgeChunkingService()
    return _chunking_service


@router.post("/knowledge/chunk")
async def chunk_document(document_id: str, content: str, strategy: str = "fixed_size", chunk_size: int = 500):
    svc = get_chunking_service()
    from app.services.knowledge_chunking_service import ChunkingConfig, ChunkingStrategy
    config = ChunkingConfig(
        strategy=ChunkingStrategy(strategy),
        chunk_size=chunk_size,
    )
    chunks = svc.chunk_document(document_id, content, config)
    return {
        "document_id": document_id,
        "chunk_count": len(chunks),
        "chunks": [
            {"id": c.id, "content": c.content[:100] + "...", "token_count": c.token_count}
            for c in chunks[:20]
        ],
    }


@router.post("/knowledge/search")
async def hybrid_search(
    query: str,
    mode: str = "hybrid",
    limit: int = 10,
    vector_results: list[dict] = [],
    keyword_results: list[dict] = [],
):
    from app.services.knowledge_chunking_service import SearchMode
    results = get_chunking_service().hybrid_search(
        query=query, vector_results=vector_results,
        keyword_results=keyword_results, mode=SearchMode(mode), limit=limit,
    )
    return {"results": [
        {"chunk_id": r.chunk_id, "score": r.score, "content": r.content[:100]}
        for r in results
    ]}


@router.post("/knowledge/permission")
async def grant_permission(resource_type: str, resource_id: str, user_id: str, permission: str = "read"):
    perm = get_chunking_service().grant_permission(resource_type, resource_id, user_id, permission)
    return {"status": "ok", "permission": permission}


@router.get("/knowledge/permissions")
async def list_permissions(resource_type: str = "", resource_id: str = ""):
    return get_chunking_service().list_permissions(resource_type, resource_id)


# ============================================================
# 7. MCP 治理
# ============================================================

_mcp_governance = None

def get_mcp_governance():
    global _mcp_governance
    if _mcp_governance is None:
        from app.services.mcp_governance_service import MCPGovernanceService
        _mcp_governance = MCPGovernanceService()
    return _mcp_governance


@router.post("/mcp-governance/canary")
async def configure_canary(server_id: str, req: CanaryRequest):
    svc = get_mcp_governance()
    config = svc.configure_canary(server_id, req.canary_version, req.stable_version, req.initial_percentage)
    return {"status": "ok", "current_percentage": config.current_percentage}


@router.post("/mcp-governance/canary/{server_id}/advance")
async def advance_canary(server_id: str):
    config = await get_mcp_governance().advance_canary(server_id)
    if not config:
        raise HTTPException(status_code=404, detail="No canary config found")
    return {"status": config.status, "current_percentage": config.current_percentage}


@router.get("/mcp-governance/stats")
async def get_mcp_governance_stats():
    return get_mcp_governance().get_call_stats()


# ============================================================
# 8. Skill 版本管理
# ============================================================

_version_service = None

def get_version_service():
    global _version_service
    if _version_service is None:
        from app.services.skill_version_service import SkillVersionService
        _version_service = SkillVersionService()
    return _version_service


@router.post("/skill-versions/{skill_id}/publish")
async def publish_version(skill_id: str, req: VersionPublishRequest):
    svc = get_version_service()
    sv = svc.publish_version(skill_id, req.version, req.description, dependencies=[])
    return {"status": "ok", "version": sv.version}


@router.get("/skill-versions/{skill_id}")
async def list_versions(skill_id: str):
    return get_version_service().get_versions(skill_id)


@router.get("/skill-versions/{skill_id}/resolve")
async def resolve_deps(skill_id: str):
    return get_version_service().resolve_dependencies(skill_id)


@router.get("/skill-versions/{skill_id}/compatibility")
async def check_compatibility(skill_id: str, version: str):
    result = get_version_service().check_compatibility(skill_id, version)
    return {
        "compatible": result.compatible,
        "conflicts": result.conflicts,
        "suggestions": result.suggestions,
    }


@router.post("/skill-versions/{skill_id}/lock")
async def lock_version(skill_id: str, version: str, reason: str = ""):
    lock = get_version_service().lock_version(skill_id, version, reason=reason)
    return {"status": "ok", "locked_version": lock.locked_version}


@router.delete("/skill-versions/{skill_id}/lock")
async def unlock_version(skill_id: str):
    result = get_version_service().unlock_version(skill_id)
    return {"status": "ok" if result else "not_found"}


# ============================================================
# 9. 自动扩缩容
# ============================================================

_scaling_service = None

def get_scaling_service():
    global _scaling_service
    if _scaling_service is None:
        from app.services.auto_scaling_service import AutoScalingService
        _scaling_service = AutoScalingService()
    return _scaling_service


@router.post("/auto-scaling/config")
async def configure_scaling(service_id: str, req: ScalingConfigRequest):
    svc = get_scaling_service()
    from app.services.auto_scaling_service import ScalingPolicy, ScalingMetric
    policy = ScalingPolicy(
        metric=ScalingMetric(req.metric),
        target_value=req.target_value,
        scale_up_threshold=req.scale_up_threshold,
        scale_down_threshold=req.scale_down_threshold,
        min_instances=req.min_instances,
        max_instances=req.max_instances,
    )
    svc.configure(service_id, policy)
    return {"status": "ok"}


@router.post("/auto-scaling/metric")
async def record_scaling_metric(service_id: str, metric: str, value: float):
    get_scaling_service().record_metric(service_id, metric, value)
    return {"status": "ok"}


@router.get("/auto-scaling/status/{service_id}")
async def get_scaling_status(service_id: str):
    return get_scaling_service().get_status(service_id)


@router.get("/auto-scaling/stats")
async def get_scaling_stats():
    return get_scaling_service().get_stats()


# ============================================================
# 10. Agent 通信
# ============================================================

_comm_service = None

def get_comm_service():
    global _comm_service
    if _comm_service is None:
        from app.services.agent_communication_service import AgentCommunicationService
        _comm_service = AgentCommunicationService()
    return _comm_service


@router.post("/communication/rpc")
async def rpc_call(from_agent: str, req: RPCRequestModel):
    svc = get_comm_service()
    resp = await svc.rpc_call(from_agent, req.to_agent, req.method, req.params)
    return resp.to_jsonrpc()


@router.post("/communication/blackboard")
async def blackboard_write(agent_id: str, req: BlackboardWriteRequest):
    entry = get_comm_service().blackboard_write(agent_id, req.key, req.value, req.metadata)
    return {"key": entry.key, "version": entry.version}


@router.get("/communication/blackboard/{key}")
async def blackboard_read(key: str):
    entry = get_comm_service().blackboard_read(key)
    if not entry:
        raise HTTPException(status_code=404, detail="Key not found")
    return {"key": entry.key, "value": entry.value, "agent_id": entry.agent_id, "version": entry.version}


@router.get("/communication/blackboard")
async def blackboard_list(prefix: str = ""):
    return get_comm_service().blackboard_read_all(prefix)


@router.get("/communication/history")
async def get_comm_history(agent_id: Optional[str] = None, protocol: Optional[str] = None, limit: int = 100):
    return get_comm_service().get_communication_history(agent_id, protocol, limit)


@router.get("/communication/stats")
async def get_comm_stats():
    return get_comm_service().get_stats()


# ============================================================
# 11. 定期维护
# ============================================================

_maintenance_service = None

def get_maintenance_service():
    global _maintenance_service
    if _maintenance_service is None:
        from app.services.scheduled_maintenance_service import ScheduledMaintenanceService
        _maintenance_service = ScheduledMaintenanceService()
        _maintenance_service.setup_defaults()
    return _maintenance_service


@router.get("/maintenance/tasks")
async def list_maintenance_tasks():
    return get_maintenance_service().list_tasks()


@router.post("/maintenance/tasks/{task_id}/run")
async def run_maintenance_task(task_id: str):
    record = await get_maintenance_service().run_task(task_id)
    return {
        "status": record.status.value,
        "duration_ms": record.duration_ms,
        "result": record.result,
    }


@router.get("/maintenance/records")
async def get_maintenance_records(limit: int = 50):
    return get_maintenance_service().get_records(limit=limit)


@router.get("/maintenance/reports")
async def get_maintenance_reports(limit: int = 20):
    return get_maintenance_service().get_reports(limit)


# ============================================================
# 12. 运维报告
# ============================================================

_report_service = None

def get_report_service():
    global _report_service
    if _report_service is None:
        from app.services.ops_report_service import OpsReportService
        _report_service = OpsReportService()
    return _report_service


@router.post("/ops-reports/generate")
async def generate_ops_report(report_type: str = "daily"):
    from app.services.ops_report_service import ReportType
    svc = get_report_service()
    report = await svc.generate_report(ReportType(report_type))
    return report.to_dict()


@router.post("/ops-reports/{report_id}/deliver")
async def deliver_report(report_id: str, channels: list[str] = []):
    result = await get_report_service().deliver_report(report_id, channels)
    return result


@router.get("/ops-reports")
async def list_ops_reports(report_type: Optional[str] = None, limit: int = 20):
    from app.services.ops_report_service import ReportType
    rt = ReportType(report_type) if report_type else None
    return get_report_service().list_reports(rt, limit)


# ============================================================
# 13. 增量备份
# ============================================================

_incr_backup_service = None

def get_incr_backup_service():
    global _incr_backup_service
    if _incr_backup_service is None:
        from app.services.incremental_backup_service import IncrementalBackupService
        _incr_backup_service = IncrementalBackupService()
    return _incr_backup_service


@router.post("/incremental-backup/full")
async def create_full_backup(components: list[str] = []):
    svc = get_incr_backup_service()
    backup = await svc.create_full_backup(components or None)
    return backup.to_dict()


@router.post("/incremental-backup/incremental")
async def create_incremental_backup(parent_id: str):
    svc = get_incr_backup_service()
    backup = await svc.create_incremental_backup(parent_id)
    return backup.to_dict()


@router.get("/incremental-backup/list")
async def list_incr_backups(backup_type: Optional[str] = None, limit: int = 50):
    from app.services.incremental_backup_service import BackupType
    bt = BackupType(backup_type) if backup_type else None
    return get_incr_backup_service().list_backups(bt, limit)


@router.get("/incremental-backup/chain/{backup_id}")
async def get_backup_chain(backup_id: str):
    return get_incr_backup_service().get_backup_chain(backup_id)


@router.post("/incremental-backup/diff")
async def diff_backups(backup_id_a: str, backup_id_b: str):
    return get_incr_backup_service().diff_backups(backup_id_a, backup_id_b)


@router.post("/incremental-backup/drill/{backup_id}")
async def run_backup_drill(backup_id: str):
    return await get_incr_backup_service().run_drill(backup_id)


@router.get("/incremental-backup/stats")
async def get_incr_backup_stats():
    return get_incr_backup_service().get_stats()


# ============================================================
# 14. 事件总线
# ============================================================

@router.get("/event-bus/stats")
async def get_event_bus_stats():
    from app.core.event_bus import event_bus
    return event_bus.get_stats()


# ============================================================
# 15. 追踪
# ============================================================

@router.get("/tracing/recent")
async def get_recent_spans(limit: int = 100):
    from app.core.tracing import get_tracer
    return get_tracer().get_recent_spans(limit)


@router.get("/tracing/trace/{trace_id}")
async def get_trace(trace_id: str):
    from app.core.tracing import get_tracer
    return get_tracer().get_trace(trace_id)
