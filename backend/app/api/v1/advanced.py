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


# ============================================================
# 16. 敏感字段脱敏
# ============================================================

_masking_service = None

def get_masking_service():
    global _masking_service
    if _masking_service is None:
        from app.services.data_masking_service import DataMaskingService
        _masking_service = DataMaskingService()
    return _masking_service


@router.post("/masking/mask")
async def mask_data(value: str, field_name: str = ""):
    svc = get_masking_service()
    return {"original": value, "masked": svc.mask(value)}


@router.post("/masking/mask-dict")
async def mask_dict_data(data: dict):
    svc = get_masking_service()
    return {"masked": svc.mask_dict(data)}


@router.get("/masking/rules")
async def list_masking_rules():
    return get_masking_service().list_rules()


@router.post("/masking/configure-audit")
async def configure_audit_masking():
    get_masking_service().configure_for_audit()
    return {"status": "ok"}


# ============================================================
# 17. 异常行为检测
# ============================================================

_anomaly_service = None

def get_anomaly_service():
    global _anomaly_service
    if _anomaly_service is None:
        from app.services.anomaly_detection_service import AnomalyDetectionService
        _anomaly_service = AnomalyDetectionService()
    return _anomaly_service


@router.post("/anomaly/ingest")
async def ingest_anomaly_event(event: dict):
    alerts = get_anomaly_service().ingest_event(event)
    return {
        "alerts_triggered": len(alerts),
        "alerts": [{"rule": a.rule_name, "severity": a.severity, "desc": a.description} for a in alerts],
    }


@router.get("/anomaly/alerts")
async def get_anomaly_alerts(severity: str = "", limit: int = 50):
    return get_anomaly_service().get_alerts(severity=severity or None, limit=limit)


@router.get("/anomaly/rules")
async def list_anomaly_rules():
    return get_anomaly_service().list_rules()


@router.get("/anomaly/stats")
async def get_anomaly_stats():
    return get_anomaly_service().get_stats()


# ============================================================
# 18. SIEM 集成
# ============================================================

_siem_service = None

def get_siem_service():
    global _siem_service
    if _siem_service is None:
        from app.services.siem_service import SIEMService
        _siem_service = SIEMService()
    return _siem_service


@router.post("/siem/send")
async def send_to_siem(record: dict):
    svc = get_siem_service()
    await svc.send_audit_record(record)
    return {"status": "ok"}


@router.get("/siem/health")
async def siem_health():
    return await get_siem_service().health_check()


@router.get("/siem/stats")
async def siem_stats():
    return get_siem_service().get_stats()


# ============================================================
# 19. SSE 实时推送
# ============================================================

_sse_service = None

def get_sse_service():
    global _sse_service
    if _sse_service is None:
        from app.services.sse_service import SSEService
        _sse_service = SSEService()
    return _sse_service


@router.get("/sse/connect")
async def sse_connect(client_id: str, user_id: str = "", channels: str = "system"):
    svc = get_sse_service()
    ch_list = [c.strip() for c in channels.split(",")]
    svc.connect(client_id, user_id, ch_list)
    return {"status": "connected", "client_id": client_id}


@router.post("/sse/publish")
async def sse_publish(channel: str, event_type: str, data: dict):
    await get_sse_service().publish(channel, event_type, data)
    return {"status": "ok"}


@router.get("/sse/stats")
async def sse_stats():
    return get_sse_service().get_stats()


# ============================================================
# 20. 模型推荐矩阵
# ============================================================

_recommendation_service = None

def get_recommendation_service():
    global _recommendation_service
    if _recommendation_service is None:
        from app.services.model_recommendation_service import ModelRecommendationService
        _recommendation_service = ModelRecommendationService()
    return _recommendation_service


@router.get("/model-recommend/matrix")
async def get_model_matrix():
    return get_recommendation_service().get_matrix()


@router.get("/model-recommend/scenarios")
async def recommend_by_scenario(
    scenario: str = "simple_qa",
    priority: str = "balanced",
    context_tokens: int = 0,
    multimodal: bool = False,
    function_calling: bool = False,
):
    from app.services.model_recommendation_service import ScenarioType, PriorityDimension
    rec = get_recommendation_service().recommend(
        scenario=ScenarioType(scenario),
        priority=PriorityDimension(priority),
        required_context_tokens=context_tokens,
        requires_multimodal=multimodal,
        requires_function_calling=function_calling,
    )
    return rec.to_dict()


@router.get("/model-recommend/profiles")
async def list_model_profiles():
    return get_recommendation_service().list_profiles()


# ============================================================
# 21. 优化效果评估
# ============================================================

_eval_service = None

def get_eval_service():
    global _eval_service
    if _eval_service is None:
        from app.services.optimization_eval_service import OptimizationEvalService
        _eval_service = OptimizationEvalService()
    return _eval_service


@router.post("/optimization-eval/baseline")
async def set_eval_baseline(data: dict):
    get_eval_service().set_baseline(data=data)
    return {"status": "ok"}


@router.post("/optimization-eval/current")
async def record_eval_current(data: dict):
    get_eval_service().record_current(data=data)
    return {"status": "ok"}


@router.get("/optimization-eval/evaluate")
async def evaluate_optimization(period: str = "monthly"):
    report = get_eval_service().evaluate(period)
    return report.to_dict()


@router.get("/optimization-eval/latest")
async def get_latest_eval():
    result = get_eval_service().get_latest()
    return result or {"message": "No reports yet"}


# ============================================================
# 22. 角色模板 + 专长注册
# ============================================================

_role_service = None

def get_role_service():
    global _role_service
    if _role_service is None:
        from app.services.role_master_service import RoleMasterService
        _role_service = RoleMasterService()
    return _role_service


@router.get("/roles/templates")
async def list_role_templates():
    return get_role_service().list_templates()


@router.post("/roles/templates")
async def create_role_template(data: dict):
    from app.services.role_master_service import RoleTemplate
    tpl = get_role_service().create_template(**data)
    return {"id": tpl.id, "name": tpl.name}


@router.get("/roles/templates/{template_id}")
async def get_role_template(template_id: str):
    result = get_role_service().get_template(template_id)
    if not result:
        raise HTTPException(status_code=404, detail="Template not found")
    return result


@router.post("/roles/experts/register")
async def register_expert(data: dict):
    entry = get_role_service().register_expertise(**data)
    return {"agent_id": entry.agent_id, "domains": entry.domains}


@router.get("/roles/experts")
async def list_experts():
    return get_role_service().list_experts()


@router.get("/roles/recommend")
async def recommend_agents_for_role(
    domains: str = "",
    skills: str = "",
    role: str = "",
    limit: int = 5,
):
    domain_list = [d.strip() for d in domains.split(",") if d.strip()] if domains else None
    skill_list = [s.strip() for s in skills.split(",") if s.strip()] if skills else None
    return get_role_service().recommend_agents(
        required_domains=domain_list,
        required_skills=skill_list,
        role_name=role,
        limit=limit,
    )


@router.post("/roles/assign")
async def assign_role(agent_id: str, role_name: str, task_id: str = ""):
    return get_role_service().assign_role(agent_id, role_name, task_id)


@router.post("/roles/release")
async def release_role(agent_id: str):
    return {"released": get_role_service().release_role(agent_id)}


@router.get("/roles/assignments")
async def get_assignments(agent_id: str = "", limit: int = 50):
    return get_role_service().get_assignments(agent_id=agent_id or None, limit=limit)


@router.get("/roles/domain-matrix")
async def get_domain_matrix():
    return get_role_service().get_domain_matrix()


# ============================================================
# MCP 批量合并 + 模板 (Phase 9)
# ============================================================

class MCPBatchRequest(BaseModel):
    tool_name: str = ""
    requests: list[dict] = []
    timeout: float = 30


class MCPTemplateInstallRequest(BaseModel):
    template_id: str = ""
    custom_config: dict = {}
    server_name: str = ""


@router.post("/mcp/batch/merge")
async def mcp_batch_merge(req: MCPBatchRequest):
    """批量合并 MCP 请求"""
    from app.services.mcp_batch_merge_service import get_mcp_batch_merge_service
    svc = get_mcp_batch_merge_service()
    return await svc.execute_batch(
        tool_name=req.tool_name,
        requests=req.requests,
        timeout=req.timeout,
    )


@router.post("/mcp/batch/compress")
async def mcp_batch_compress(data: dict):
    """gzip 压缩数据"""
    from app.services.mcp_batch_merge_service import get_mcp_batch_merge_service
    svc = get_mcp_batch_merge_service()
    import gzip, json as _j
    raw = _j.dumps(data, ensure_ascii=False).encode("utf-8")
    compressed = svc.compress(raw)
    return {
        "original_size": len(raw),
        "compressed_size": len(compressed),
        "ratio": round(len(compressed) / max(len(raw), 1), 3),
    }


@router.get("/mcp/templates")
async def list_mcp_templates():
    """列出 MCP 模板"""
    from app.services.mcp_template_service import get_mcp_template_service
    return get_mcp_template_service().list_templates()


@router.get("/mcp/templates/{template_id}")
async def get_mcp_template(template_id: str):
    """获取 MCP 模板详情"""
    from app.services.mcp_template_service import get_mcp_template_service
    t = get_mcp_template_service().get_template(template_id)
    if not t:
        raise HTTPException(404, "模板不存在")
    return t


@router.post("/mcp/templates/install")
async def install_mcp_template(req: MCPTemplateInstallRequest):
    """一键安装 MCP 模板"""
    from app.services.mcp_template_service import get_mcp_template_service
    return get_mcp_template_service().install_template(
        req.template_id, req.custom_config, req.server_name
    )


@router.get("/mcp/templates/installed")
async def list_installed_mcp():
    """列出已安装 MCP"""
    from app.services.mcp_template_service import get_mcp_template_service
    return get_mcp_template_service().list_installed()


# ============================================================
# MCP 请求签名 (HMAC)
# ============================================================

class MCPKeyCreateRequest(BaseModel):
    key_id: str = ""
    secret: str = ""
    description: str = ""
    ttl_seconds: int = 86400 * 90


class MCPSignRequest(BaseModel):
    key_id: str = ""
    request_body: dict = {}
    nonce: str = ""


class MCPVerifyRequest(BaseModel):
    key_id: str = ""
    signature: str = ""
    timestamp: float = 0
    nonce: str = ""
    request_body: dict = {}


@router.post("/mcp/signature/keys")
async def create_signature_key(req: MCPKeyCreateRequest):
    """创建签名密钥"""
    from app.services.mcp_signature_service import get_mcp_signature_service
    return get_mcp_signature_service().create_key(
        req.key_id, req.secret, req.description, req.ttl_seconds
    )


@router.get("/mcp/signature/keys")
async def list_signature_keys():
    """列出签名密钥"""
    from app.services.mcp_signature_service import get_mcp_signature_service
    return get_mcp_signature_service().list_keys()


@router.post("/mcp/signature/keys/{key_id}/revoke")
async def revoke_signature_key(key_id: str):
    """吊销密钥"""
    from app.services.mcp_signature_service import get_mcp_signature_service
    return get_mcp_signature_service().revoke_key(key_id)


@router.post("/mcp/signature/keys/rotate")
async def rotate_signature_key(old_key_id: str, new_key_id: str, new_secret: str):
    """轮换密钥"""
    from app.services.mcp_signature_service import get_mcp_signature_service
    return get_mcp_signature_service().rotate_key(old_key_id, new_key_id, new_secret)


@router.post("/mcp/signature/sign")
async def sign_request(req: MCPSignRequest):
    """生成签名"""
    from app.services.mcp_signature_service import get_mcp_signature_service
    result = get_mcp_signature_service().sign(req.key_id, req.request_body, req.nonce)
    return {"key_id": result.key_id, "signature": result.signature, "timestamp": result.timestamp, "nonce": result.nonce}


@router.post("/mcp/signature/sign-headers")
async def sign_headers(req: MCPSignRequest):
    """生成签名 HTTP 头"""
    from app.services.mcp_signature_service import get_mcp_signature_service
    return get_mcp_signature_service().sign_headers(req.key_id, req.request_body, req.nonce)


@router.post("/mcp/signature/verify")
async def verify_signature(req: MCPVerifyRequest):
    """验证签名"""
    from app.services.mcp_signature_service import get_mcp_signature_service
    result = get_mcp_signature_service().verify(
        req.key_id, req.signature, req.timestamp, req.nonce, req.request_body
    )
    return {"valid": result.valid, "key_id": result.key_id, "error": result.error}


@router.get("/mcp/signature/log")
async def signature_verification_log(limit: int = 100):
    """签名验证日志"""
    from app.services.mcp_signature_service import get_mcp_signature_service
    return get_mcp_signature_service().get_verification_log(limit)


# ============================================================
# WebSocket 实时监控
# ============================================================

class WSConnectRequest(BaseModel):
    client_id: str = ""
    channels: list[str] = ["system"]
    metadata: dict = {}


@router.post("/ws-monitor/connect")
async def ws_monitor_connect(req: WSConnectRequest):
    """注册 WebSocket 监控客户端"""
    from app.services.websocket_monitor_service import get_ws_monitor_service
    return await get_ws_monitor_service().connect(req.client_id, req.channels, req.metadata)


@router.post("/ws-monitor/disconnect")
async def ws_monitor_disconnect(client_id: str):
    """断开监控客户端"""
    from app.services.websocket_monitor_service import get_ws_monitor_service
    await get_ws_monitor_service().disconnect(client_id)
    return {"disconnected": True}


@router.post("/ws-monitor/heartbeat")
async def ws_monitor_heartbeat(client_id: str):
    """心跳"""
    from app.services.websocket_monitor_service import get_ws_monitor_service
    ok = await get_ws_monitor_service().heartbeat(client_id)
    return {"ok": ok}


@router.post("/ws-monitor/publish")
async def ws_monitor_publish(channel: str, event_type: str, data: dict = {}):
    """发布事件到监控通道"""
    from app.services.websocket_monitor_service import get_ws_monitor_service
    await get_ws_monitor_service().publish(channel, event_type, data)
    return {"published": True}


@router.get("/ws-monitor/metrics")
async def ws_monitor_current_metrics():
    """获取最新指标"""
    from app.services.websocket_monitor_service import get_ws_monitor_service
    return await get_ws_monitor_service().get_current_metrics() or {"message": "无数据"}


@router.get("/ws-monitor/metrics/history")
async def ws_monitor_metrics_history(duration_seconds: int = 300):
    """获取历史指标"""
    from app.services.websocket_monitor_service import get_ws_monitor_service
    return await get_ws_monitor_service().get_metrics_history(duration_seconds)


@router.get("/ws-monitor/events")
async def ws_monitor_events(channel: str = "", event_type: str = "", limit: int = 100):
    """查询事件历史"""
    from app.services.websocket_monitor_service import get_ws_monitor_service
    return get_ws_monitor_service().get_event_history(channel, event_type, limit)


@router.get("/ws-monitor/clients")
async def ws_monitor_clients():
    """获取客户端列表"""
    from app.services.websocket_monitor_service import get_ws_monitor_service
    svc = get_ws_monitor_service()
    return {"total": svc.get_client_count()}


# ============================================================
# Agent 下钻分析
# ============================================================

@router.get("/agent-drilldown/{agent_id}")
async def agent_drilldown(
    agent_id: str,
    time_range_start: str = "",
    time_range_end: str = "",
):
    """单 Agent 下钻分析"""
    from app.services.agent_drilldown_service import get_drilldown_service
    return get_drilldown_service().drilldown(
        agent_id,
        time_range_start=time_range_start or None,
        time_range_end=time_range_end or None,
    )


@router.post("/agent-drilldown/{agent_id}/record")
async def record_drilldown_request(
    agent_id: str,
    response_time: float = 0,
    tokens_used: int = 0,
    cost_usd: float = 0,
    success: bool = True,
    user_satisfaction: float = 0,
):
    """记录请求数据用于下钻分析"""
    from app.services.agent_drilldown_service import get_drilldown_service
    get_drilldown_service().record_request(
        agent_id, response_time, tokens_used, cost_usd, success, user_satisfaction
    )
    return {"recorded": True}


# ============================================================
# 自定义拖拽仪表盘
# ============================================================

class DashboardCreateRequest(BaseModel):
    name: str = ""
    description: str = ""
    owner_id: str = ""
    template_id: str = ""
    is_public: bool = False
    tags: list[str] = []


class WidgetAddRequest(BaseModel):
    widget_type: str = "metric"
    title: str = ""
    data_source: str = ""
    query: dict = {}
    position: dict = {}
    config: dict = {}


@router.post("/dashboards")
async def create_dashboard(req: DashboardCreateRequest):
    """创建仪表盘"""
    from app.services.dashboard_service import get_dashboard_service
    return get_dashboard_service().create_dashboard(
        req.name, req.owner_id, req.description, req.template_id, req.is_public, req.tags
    )


@router.get("/dashboards")
async def list_dashboards(owner_id: str = "", limit: int = 50):
    """列出仪表盘"""
    from app.services.dashboard_service import get_dashboard_service
    return get_dashboard_service().list_dashboards(owner_id, limit)


@router.get("/dashboards/{dashboard_id}")
async def get_dashboard(dashboard_id: str):
    """获取仪表盘"""
    from app.services.dashboard_service import get_dashboard_service
    d = get_dashboard_service().get_dashboard(dashboard_id)
    if not d:
        raise HTTPException(404, "仪表盘不存在")
    return d


@router.put("/dashboards/{dashboard_id}")
async def update_dashboard(dashboard_id: str, updates: dict = {}):
    """更新仪表盘"""
    from app.services.dashboard_service import get_dashboard_service
    return get_dashboard_service().update_dashboard(dashboard_id, updates)


@router.delete("/dashboards/{dashboard_id}")
async def delete_dashboard(dashboard_id: str):
    """删除仪表盘"""
    from app.services.dashboard_service import get_dashboard_service
    return get_dashboard_service().delete_dashboard(dashboard_id)


@router.post("/dashboards/{dashboard_id}/widgets")
async def add_widget(dashboard_id: str, req: WidgetAddRequest):
    """添加组件"""
    from app.services.dashboard_service import get_dashboard_service
    return get_dashboard_service().add_widget(dashboard_id, req.dict())


@router.put("/dashboards/{dashboard_id}/widgets/{widget_id}")
async def update_widget(dashboard_id: str, widget_id: str, updates: dict = {}):
    """更新组件"""
    from app.services.dashboard_service import get_dashboard_service
    return get_dashboard_service().update_widget(dashboard_id, widget_id, updates)


@router.delete("/dashboards/{dashboard_id}/widgets/{widget_id}")
async def remove_widget(dashboard_id: str, widget_id: str):
    """移除组件"""
    from app.services.dashboard_service import get_dashboard_service
    return get_dashboard_service().remove_widget(dashboard_id, widget_id)


@router.post("/dashboards/{dashboard_id}/share")
async def share_dashboard(dashboard_id: str, user_ids: list[str] = []):
    """共享仪表盘"""
    from app.services.dashboard_service import get_dashboard_service
    return get_dashboard_service().share_dashboard(dashboard_id, user_ids)


@router.get("/dashboards/templates/list")
async def list_dashboard_templates():
    """列出仪表盘模板"""
    from app.services.dashboard_service import get_dashboard_service
    return get_dashboard_service().list_templates()


# ============================================================
# 模型基准评测
# ============================================================

class BenchmarkRunRequest(BaseModel):
    model_id: str = ""
    tasks: list[dict] = []


@router.post("/benchmark/run")
async def run_benchmark(req: BenchmarkRunRequest):
    """执行模型评测"""
    from app.services.model_benchmark_service import get_benchmark_service
    return get_benchmark_service().run_benchmark(req.model_id, req.tasks or None)


@router.get("/benchmark/leaderboard")
async def benchmark_leaderboard(metric: str = "composite_score"):
    """模型排行榜"""
    from app.services.model_benchmark_service import get_benchmark_service
    return get_benchmark_service().leaderboard(metric)


@router.get("/benchmark/compare")
async def benchmark_compare(model_ids: str = ""):
    """模型对比"""
    from app.services.model_benchmark_service import get_benchmark_service
    ids = [m.strip() for m in model_ids.split(",") if m.strip()]
    return get_benchmark_service().compare(ids)


@router.get("/benchmark/report/{model_id}")
async def benchmark_report(model_id: str):
    """获取评测报告"""
    from app.services.model_benchmark_service import get_benchmark_service
    r = get_benchmark_service().get_report(model_id)
    if not r:
        raise HTTPException(404, "无评测数据")
    return r


@router.get("/benchmark/tasks")
async def list_benchmark_tasks():
    """列出评测任务"""
    from app.services.model_benchmark_service import get_benchmark_service
    return get_benchmark_service().list_tasks()


# ============================================================
# 模型热切换
# ============================================================

class ModelRegisterRequest(BaseModel):
    model_id: str = ""
    provider: str = ""
    api_key: str = ""
    endpoint: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    priority: int = 0


class ModelSwitchRequest(BaseModel):
    to_model: str = ""
    reason: str = ""
    traffic_percent: int = 100


@router.post("/hotswap/models")
async def register_model(req: ModelRegisterRequest):
    """注册模型"""
    from app.services.model_hotswap_service import get_hotswap_service
    return get_hotswap_service().register_model(req.dict())


@router.get("/hotswap/models")
async def list_models():
    """列出模型"""
    from app.services.model_hotswap_service import get_hotswap_service
    return get_hotswap_service().list_models()


@router.get("/hotswap/models/{model_id}")
async def get_model(model_id: str):
    """获取模型详情"""
    from app.services.model_hotswap_service import get_hotswap_service
    m = get_hotswap_service().get_model(model_id)
    if not m:
        raise HTTPException(404, "模型不存在")
    return m


@router.post("/hotswap/switch")
async def switch_model(req: ModelSwitchRequest):
    """切换模型"""
    from app.services.model_hotswap_service import get_hotswap_service
    return get_hotswap_service().switch(req.to_model, req.reason, "manual", req.traffic_percent)


@router.post("/hotswap/rollback")
async def rollback_model(reason: str = "manual_rollback"):
    """回滚模型"""
    from app.services.model_hotswap_service import get_hotswap_service
    return get_hotswap_service().rollback(reason)


@router.get("/hotswap/current")
async def current_model():
    """获取当前模型"""
    from app.services.model_hotswap_service import get_hotswap_service
    return {"model_id": get_hotswap_service().get_current_model()}


@router.get("/hotswap/history")
async def switch_history(limit: int = 50):
    """切换历史"""
    from app.services.model_hotswap_service import get_hotswap_service
    return get_hotswap_service().get_history(limit)


@router.get("/hotswap/stats")
async def hotswap_stats():
    """切换统计"""
    from app.services.model_hotswap_service import get_hotswap_service
    return get_hotswap_service().get_stats()


# ============================================================
# 会话沙箱测试
# ============================================================

class SandboxTestCaseRequest(BaseModel):
    name: str = ""
    description: str = ""
    agent_id: str = ""
    messages: list[dict] = []
    assertions: list[dict] = []
    tags: list[str] = []


@router.post("/sandbox/test-cases")
async def create_sandbox_test_case(req: SandboxTestCaseRequest):
    """创建沙箱测试用例"""
    from app.services.conversation_sandbox_service import get_sandbox_service
    return get_sandbox_service().create_test_case(req.dict())


@router.get("/sandbox/test-cases")
async def list_sandbox_test_cases(tag: str = "", agent_id: str = ""):
    """列出测试用例"""
    from app.services.conversation_sandbox_service import get_sandbox_service
    return get_sandbox_service().list_test_cases(tag, agent_id)


@router.delete("/sandbox/test-cases/{case_id}")
async def delete_sandbox_test_case(case_id: str):
    """删除测试用例"""
    from app.services.conversation_sandbox_service import get_sandbox_service
    return get_sandbox_service().delete_test_case(case_id)


@router.post("/sandbox/run/{case_id}")
async def run_sandbox_test(case_id: str):
    """执行单条测试"""
    from app.services.conversation_sandbox_service import get_sandbox_service
    return await get_sandbox_service().run_single(case_id)


@router.post("/sandbox/run-batch")
async def run_sandbox_batch(case_ids: list[str] = [], tag: str = ""):
    """批量执行测试"""
    from app.services.conversation_sandbox_service import get_sandbox_service
    return await get_sandbox_service().run_batch(case_ids or None, tag)


@router.post("/sandbox/sessions")
async def create_sandbox_session(agent_id: str):
    """创建交互式沙箱"""
    from app.services.conversation_sandbox_service import get_sandbox_service
    return get_sandbox_service().create_session(agent_id)


@router.post("/sandbox/sessions/{session_id}/send")
async def send_sandbox_message(session_id: str, content: str):
    """发送沙箱消息"""
    from app.services.conversation_sandbox_service import get_sandbox_service
    return await get_sandbox_service().send_message(session_id, content)


@router.get("/sandbox/sessions/{session_id}/history")
async def sandbox_session_history(session_id: str):
    """获取沙箱会话历史"""
    from app.services.conversation_sandbox_service import get_sandbox_service
    return get_sandbox_service().get_session_history(session_id)


@router.post("/sandbox/sessions/{session_id}/close")
async def close_sandbox_session(session_id: str):
    """关闭沙箱会话"""
    from app.services.conversation_sandbox_service import get_sandbox_service
    return get_sandbox_service().close_session(session_id)


@router.get("/sandbox/statistics")
async def sandbox_statistics():
    """沙箱统计"""
    from app.services.conversation_sandbox_service import get_sandbox_service
    return get_sandbox_service().get_statistics()


# ============================================================
# 跨 Agent 恢复
# ============================================================

class RestorePlanRequest(BaseModel):
    backup_id: str = ""
    target_agent_id: str = ""
    components: list[str] = []
    conflict_resolution: str = "skip"


@router.post("/cross-restore/backup")
async def register_backup(backup_id: str, agent_id: str, data: dict = {}):
    """注册备份"""
    from app.services.cross_agent_restore_service import get_cross_agent_restore_service
    return get_cross_agent_restore_service().register_backup(backup_id, agent_id, data)


@router.post("/cross-restore/agent")
async def register_restore_agent(agent_id: str, config: dict = {}):
    """注册目标 Agent"""
    from app.services.cross_agent_restore_service import get_cross_agent_restore_service
    return get_cross_agent_restore_service().register_agent(agent_id, config)


@router.post("/cross-restore/plan")
async def create_restore_plan(req: RestorePlanRequest):
    """创建恢复计划"""
    from app.services.cross_agent_restore_service import get_cross_agent_restore_service
    return get_cross_agent_restore_service().create_restore_plan(
        req.backup_id, req.target_agent_id, req.components or None, req.conflict_resolution
    )


@router.post("/cross-restore/execute")
async def execute_restore(plan_id: str):
    """执行恢复"""
    from app.services.cross_agent_restore_service import get_cross_agent_restore_service
    return await get_cross_agent_restore_service().execute_restore(plan_id)


@router.get("/cross-restore/verify")
async def verify_restore(plan_id: str):
    """验证恢复结果"""
    from app.services.cross_agent_restore_service import get_cross_agent_restore_service
    return get_cross_agent_restore_service().verify_restore(plan_id)


@router.get("/cross-restore/history")
async def restore_history(limit: int = 20):
    """恢复历史"""
    from app.services.cross_agent_restore_service import get_cross_agent_restore_service
    return get_cross_agent_restore_service().get_history(limit)


# ============================================================
# Token 配额管理
# ============================================================

class QuotaCreateRequest(BaseModel):
    entity_type: str = "user"
    entity_id: str = ""
    daily_limit: int = 0
    monthly_limit: int = 0
    total_limit: int = 0
    alert_threshold: float = 0.8


class QuotaUsageRequest(BaseModel):
    entity_type: str = "user"
    entity_id: str = ""
    tokens: int = 0
    model: str = ""
    agent_id: str = ""
    operation: str = "chat"


class QuotaUpdateRequest(BaseModel):
    daily_limit: Optional[int] = None
    monthly_limit: Optional[int] = None
    total_limit: Optional[int] = None
    alert_threshold: Optional[float] = None


@router.post("/quotas")
async def create_quota(req: QuotaCreateRequest):
    """创建配额"""
    from app.services.token_quota_service import get_quota_service
    return get_quota_service().create_quota(
        req.entity_type, req.entity_id, req.daily_limit, req.monthly_limit,
        req.total_limit, req.alert_threshold
    )


@router.get("/quotas")
async def list_quotas(entity_type: str = "", entity_id: str = "", limit: int = 50):
    """列出配额"""
    from app.services.token_quota_service import get_quota_service
    return get_quota_service().list_quotas(entity_type, entity_id, limit)


@router.get("/quotas/{quota_id}")
async def get_quota(quota_id: str):
    """获取配额"""
    from app.services.token_quota_service import get_quota_service
    q = get_quota_service().get_quota(quota_id)
    if not q:
        raise HTTPException(404, "配额不存在")
    return q


@router.put("/quotas/{quota_id}")
async def update_quota(quota_id: str, req: QuotaUpdateRequest):
    """更新配额"""
    from app.services.token_quota_service import get_quota_service
    updates = {k: v for k, v in req.dict().items() if v is not None}
    return get_quota_service().update_quota(quota_id, updates)


@router.delete("/quotas/{quota_id}")
async def delete_quota(quota_id: str):
    """删除配额"""
    from app.services.token_quota_service import get_quota_service
    return get_quota_service().delete_quota(quota_id)


@router.post("/quotas/usage")
async def record_quota_usage(req: QuotaUsageRequest):
    """记录使用量"""
    from app.services.token_quota_service import get_quota_service
    return get_quota_service().record_usage(
        req.entity_type, req.entity_id, req.tokens, req.model, req.agent_id, req.operation
    )


@router.get("/quotas/usage/check")
async def check_quota_available(entity_type: str, entity_id: str, tokens: int = 1000):
    """检查配额可用性"""
    from app.services.token_quota_service import get_quota_service
    return get_quota_service().check_available(entity_type, entity_id, tokens)


@router.get("/quotas/usage/{quota_id}")
async def quota_usage_history(quota_id: str, limit: int = 100):
    """使用历史"""
    from app.services.token_quota_service import get_quota_service
    return get_quota_service().get_usage_history(quota_id, limit)


@router.get("/quotas/alerts")
async def quota_alerts(limit: int = 50):
    """配额告警"""
    from app.services.token_quota_service import get_quota_service
    return get_quota_service().get_alerts(limit)


@router.get("/quotas/statistics")
async def quota_statistics():
    """配额统计"""
    from app.services.token_quota_service import get_quota_service
    return get_quota_service().get_statistics()


@router.post("/quotas/reset/daily")
async def reset_daily_quotas():
    """重置日配额"""
    from app.services.token_quota_service import get_quota_service
    get_quota_service().reset_daily()
    return {"reset": "daily"}


@router.post("/quotas/reset/monthly")
async def reset_monthly_quotas():
    """重置月配额"""
    from app.services.token_quota_service import get_quota_service
    get_quota_service().reset_monthly()
    return {"reset": "monthly"}


# ============================================================
# 技能组合优化
# ============================================================

class SkillRegisterRequest(BaseModel):
    id: str = ""
    name: str = ""
    category: str = ""
    tags: list[str] = []
    dependencies: list[str] = []
    conflicts: list[str] = []
    resource_cost: float = 1.0
    performance_impact: float = 0


class SkillRecommendRequest(BaseModel):
    purpose: str = ""
    max_skills: int = 5
    exclude: list[str] = []
    include: list[str] = []


@router.post("/skill-combo/register")
async def register_skill(req: SkillRegisterRequest):
    """注册技能"""
    from app.services.skill_combination_service import get_skill_combination_service
    return get_skill_combination_service().register_skill(req.dict())


@router.get("/skill-combo/skills")
async def list_skills(category: str = ""):
    """列出技能"""
    from app.services.skill_combination_service import get_skill_combination_service
    return get_skill_combination_service().list_skills(category)


@router.post("/skill-combo/detect-conflicts")
async def detect_skill_conflicts(skill_ids: list[str] = []):
    """检测冲突"""
    from app.services.skill_combination_service import get_skill_combination_service
    conflicts = get_skill_combination_service().detect_conflicts(skill_ids)
    return [{"skill_a": c.skill_a, "skill_b": c.skill_b, "reason": c.reason, "severity": c.severity} for c in conflicts]


@router.post("/skill-combo/check-dependencies")
async def check_skill_dependencies(skill_ids: list[str] = []):
    """检查依赖"""
    from app.services.skill_combination_service import get_skill_combination_service
    return get_skill_combination_service().check_dependencies(skill_ids)


@router.post("/skill-combo/score")
async def score_skill_combination(skill_ids: list[str] = []):
    """评分组合"""
    from app.services.skill_combination_service import get_skill_combination_service
    result = get_skill_combination_service().score_combination(skill_ids)
    return {
        "score": result.score,
        "conflicts": result.conflicts,
        "total_resource_cost": result.total_resource_cost,
        "synergy_score": result.synergy_score,
        "coverage_score": result.coverage_score,
    }


@router.post("/skill-combo/recommend")
async def recommend_skills(req: SkillRecommendRequest):
    """推荐技能组合"""
    from app.services.skill_combination_service import get_skill_combination_service
    return get_skill_combination_service().recommend(
        req.purpose, req.max_skills, req.exclude, req.include
    )


@router.get("/skill-combo/statistics")
async def skill_combo_statistics():
    """统计"""
    from app.services.skill_combination_service import get_skill_combination_service
    return get_skill_combination_service().get_statistics()


# ============================================================
# 对话理解增强 (意图保持 / 共指消解 / 话题切换)
# ============================================================

class IntentRequest(BaseModel):
    text: str = ""
    session_id: str = ""


class CoreferenceRequest(BaseModel):
    text: str = ""
    session_id: str = ""


class TopicSwitchRequest(BaseModel):
    text: str = ""
    session_id: str = ""
    threshold: float = 0.3


class EnhanceMessageRequest(BaseModel):
    text: str = ""
    session_id: str = ""


@router.post("/dialogue/intent")
async def detect_intent(req: IntentRequest):
    """意图识别"""
    from app.services.dialogue_enhancement_service import get_dialogue_enhancement_service
    return await get_dialogue_enhancement_service().detect_intent(req.text, req.session_id)


@router.post("/dialogue/intent/batch")
async def detect_intent_batch(texts: list[str] = []):
    """批量意图识别"""
    from app.services.dialogue_enhancement_service import get_dialogue_enhancement_service
    return await get_dialogue_enhancement_service().detect_intent_batch(texts)


@router.post("/dialogue/coreference")
async def resolve_coreference(req: CoreferenceRequest):
    """共指消解"""
    from app.services.dialogue_enhancement_service import get_dialogue_enhancement_service
    return await get_dialogue_enhancement_service().resolve_coreference(req.text, req.session_id)


@router.post("/dialogue/topic-switch")
async def detect_topic_switch(req: TopicSwitchRequest):
    """话题切换检测"""
    from app.services.dialogue_enhancement_service import get_dialogue_enhancement_service
    return await get_dialogue_enhancement_service().detect_topic_switch(
        req.text, req.session_id, req.threshold
    )


@router.post("/dialogue/enhance")
async def enhance_message(req: EnhanceMessageRequest):
    """完整对话增强管道 (意图 + 共指 + 话题)"""
    from app.services.dialogue_enhancement_service import get_dialogue_enhancement_service
    return await get_dialogue_enhancement_service().enhance_message(req.text, req.session_id)


@router.get("/dialogue/quality/{session_id}")
async def dialogue_quality(session_id: str):
    """上下文质量评估"""
    from app.services.dialogue_enhancement_service import get_dialogue_enhancement_service
    return await get_dialogue_enhancement_service().evaluate_context_quality(session_id)


@router.get("/dialogue/sessions")
async def dialogue_sessions():
    """列出活跃对话会话"""
    from app.services.dialogue_enhancement_service import get_dialogue_enhancement_service
    return get_dialogue_enhancement_service().list_sessions()


@router.get("/dialogue/sessions/{session_id}/summary")
async def dialogue_session_summary(session_id: str):
    """会话摘要"""
    from app.services.dialogue_enhancement_service import get_dialogue_enhancement_service
    return get_dialogue_enhancement_service().get_session_summary(session_id)


@router.delete("/dialogue/sessions/{session_id}")
async def clear_dialogue_session(session_id: str):
    """清除会话历史"""
    from app.services.dialogue_enhancement_service import get_dialogue_enhancement_service
    get_dialogue_enhancement_service().clear_session(session_id)
    return {"cleared": True}


# ============================================================
# 多 Agent 会话路由 + 消息序列化
# ============================================================

class AgentRegisterRequest(BaseModel):
    agent_id: str = ""
    name: str = ""
    capabilities: list[str] = []
    max_concurrent: int = 10


class AgentStatusUpdateRequest(BaseModel):
    current_load: int = 0
    queue_depth: int = 0
    avg_response_time: float = 0
    is_healthy: bool = True


class RoutingRuleRequest(BaseModel):
    id: str = ""
    source_pattern: str = ""
    target_agent: str = ""
    strategy: str = "round_robin"
    capability_required: str = ""
    priority: int = 0


class RouteMessageRequest(BaseModel):
    session_id: str = ""
    content: dict = {}
    user_id: str = ""
    strategy: str = ""
    capability_required: str = ""
    priority: int = 1


class SendMessageRequest(BaseModel):
    source_session: str = ""
    target_session: str = ""
    content: dict = {}
    priority: int = 1
    correlation_id: str = ""


class SessionMigrateRequest(BaseModel):
    session_id: str = ""
    to_agent: str = ""
    reason: str = ""


@router.post("/routing/agents")
async def register_routing_agent(req: AgentRegisterRequest):
    """注册 Agent 端点"""
    from app.services.multi_agent_routing_service import get_multi_agent_routing_service
    return get_multi_agent_routing_service().register_agent(
        req.agent_id, req.name, req.capabilities, req.max_concurrent
    )


@router.delete("/routing/agents/{agent_id}")
async def unregister_routing_agent(agent_id: str):
    """注销 Agent"""
    from app.services.multi_agent_routing_service import get_multi_agent_routing_service
    return get_multi_agent_routing_service().unregister_agent(agent_id)


@router.put("/routing/agents/{agent_id}/status")
async def update_agent_status(agent_id: str, req: AgentStatusUpdateRequest):
    """更新 Agent 状态"""
    from app.services.multi_agent_routing_service import get_multi_agent_routing_service
    return get_multi_agent_routing_service().update_agent_status(
        agent_id, req.current_load, req.queue_depth, req.avg_response_time, req.is_healthy
    )


@router.get("/routing/agents")
async def list_routing_agents():
    """列出所有 Agent"""
    from app.services.multi_agent_routing_service import get_multi_agent_routing_service
    return get_multi_agent_routing_service().list_agents()


@router.post("/routing/agents/{agent_id}/migrate")
async def migrate_session(session_id: str, to_agent: str, reason: str = ""):
    """会话迁移"""
    from app.services.multi_agent_routing_service import get_multi_agent_routing_service
    return await get_multi_agent_routing_service().migrate_session(session_id, to_agent, reason)


@router.get("/routing/migrations")
async def migration_history(limit: int = 20):
    """迁移历史"""
    from app.services.multi_agent_routing_service import get_multi_agent_routing_service
    return get_multi_agent_routing_service().get_migration_history(limit)


@router.post("/routing/rules")
async def add_routing_rule(req: RoutingRuleRequest):
    """添加路由规则"""
    from app.services.multi_agent_routing_service import get_multi_agent_routing_service
    return get_multi_agent_routing_service().add_routing_rule(req.dict())


@router.delete("/routing/rules/{rule_id}")
async def remove_routing_rule(rule_id: str):
    """删除路由规则"""
    from app.services.multi_agent_routing_service import get_multi_agent_routing_service
    return get_multi_agent_routing_service().remove_routing_rule(rule_id)


@router.get("/routing/rules")
async def list_routing_rules():
    """列出路由规则"""
    from app.services.multi_agent_routing_service import get_multi_agent_routing_service
    return get_multi_agent_routing_service().list_routing_rules()


@router.post("/routing/route")
async def route_message(req: RouteMessageRequest):
    """路由消息到最优 Agent"""
    from app.services.multi_agent_routing_service import get_multi_agent_routing_service
    return get_multi_agent_routing_service().route_message(
        req.session_id, req.content, req.user_id, req.strategy,
        req.capability_required, req.priority
    )


@router.post("/routing/messages")
async def send_message(req: SendMessageRequest):
    """发送序列化消息"""
    from app.services.multi_agent_routing_service import get_multi_agent_routing_service
    return await get_multi_agent_routing_service().send_message(
        req.source_session, req.target_session, req.content,
        req.priority, req.correlation_id
    )


@router.post("/routing/messages/{message_id}/process")
async def process_message(message_id: str):
    """确认消息已处理"""
    from app.services.multi_agent_routing_service import get_multi_agent_routing_service
    return await get_multi_agent_routing_service().process_message(message_id)


@router.post("/routing/messages/{message_id}/fail")
async def fail_message(message_id: str, error: str = ""):
    """标记消息失败"""
    from app.services.multi_agent_routing_service import get_multi_agent_routing_service
    return await get_multi_agent_routing_service().fail_message(message_id, error)


@router.get("/routing/messages/pending")
async def pending_messages(limit: int = 50):
    """待处理消息"""
    from app.services.multi_agent_routing_service import get_multi_agent_routing_service
    return get_multi_agent_routing_service().get_pending_messages(limit)


@router.get("/routing/sequence")
async def current_sequence():
    """当前全局序列号"""
    from app.services.multi_agent_routing_service import get_multi_agent_routing_service
    return {"sequence": get_multi_agent_routing_service().get_sequence_number()}


@router.get("/routing/sessions/{session_id}/agent")
async def get_session_agent(session_id: str):
    """获取会话绑定的 Agent"""
    from app.services.multi_agent_routing_service import get_multi_agent_routing_service
    agent_id = get_multi_agent_routing_service().get_session_agent(session_id)
    return {"session_id": session_id, "agent_id": agent_id}


@router.get("/routing/agents/{agent_id}/sessions")
async def get_agent_sessions(agent_id: str):
    """获取 Agent 下的所有会话"""
    from app.services.multi_agent_routing_service import get_multi_agent_routing_service
    return {"agent_id": agent_id, "sessions": get_multi_agent_routing_service().get_agent_sessions(agent_id)}


@router.get("/routing/statistics")
async def routing_statistics():
    """路由统计"""
    from app.services.multi_agent_routing_service import get_multi_agent_routing_service
    return get_multi_agent_routing_service().get_statistics()
