"""
4.16 Token 使用管理与优化 API
覆盖：用量记录/统计、预算与配额、告警、模型选择建议、上下文优化、级联规则、效果评估
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.auth_service import get_current_user
from app.services.token_service import TokenService, OptimizationService

router = APIRouter(prefix="/api/v1/tokens", tags=["Token 使用管理"], dependencies=[Depends(get_current_user)])


def _serialize(record):
    return {
        "id": record.id,
        "user_id": record.user_id,
        "agent_id": record.agent_id,
        "conversation_id": record.conversation_id,
        "model_name": record.model_name,
        "input_tokens": record.input_tokens,
        "output_tokens": record.output_tokens,
        "cached_tokens": record.cached_tokens,
        "compressed_tokens": record.compressed_tokens,
        "cost": record.cost,
        "usage_date": record.usage_date,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


# ==================== 用量记录与统计 ====================

@router.post("/usage/record", summary="记录一次 Token 用量（自动预算检查）")
async def record_usage(body: dict, session: AsyncSession = Depends(get_db)):
    try:
        return await TokenService.record_usage(
            session,
            user_id=body["user_id"],
            model_name=body["model_name"],
            input_tokens=body.get("input_tokens", 0),
            output_tokens=body.get("output_tokens", 0),
            agent_id=body.get("agent_id"),
            conversation_id=body.get("conversation_id"),
            cached_tokens=body.get("cached_tokens", 0),
            compressed_tokens=body.get("compressed_tokens", 0),
        )
    except KeyError as e:
        raise HTTPException(400, f"缺少必填字段: {e}")


@router.get("/stats", summary="Token 统计（总计/模型分布/日趋势/用户排名）")
async def get_stats(
    user_id: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_db),
):
    return await TokenService.get_stats(session, user_id=user_id, days=days)


@router.get("/usage", summary="用量明细（分页）")
async def list_usage(
    user_id: Optional[str] = None,
    model_name: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    session: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select, func
    from app.models.token import TokenUsage
    filters = []
    if user_id:
        filters.append(TokenUsage.user_id == user_id)
    if model_name:
        filters.append(TokenUsage.model_name == model_name)
    total = (await session.execute(select(func.count()).select_from(TokenUsage).where(*filters))).scalar() or 0
    rows = (await session.execute(
        select(TokenUsage).where(*filters)
        .order_by(TokenUsage.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return {"total": total, "page": page, "page_size": page_size, "items": [_serialize(r) for r in rows]}


# ==================== 预算与配额 ====================

@router.get("/budget", summary="用户预算/配额状态")
async def get_budget(user_id: str, session: AsyncSession = Depends(get_db)):
    return await TokenService.get_user_budget(session, user_id)


@router.put("/budget", summary="更新用户预算/配额")
async def update_budget(body: dict, session: AsyncSession = Depends(get_db)):
    user_id = body.get("user_id")
    if not user_id:
        raise HTTPException(400, "缺少 user_id")
    allowed = {
        "monthly_budget", "token_quota", "alert_threshold",
        "block_when_exceeded", "cascade_enabled", "cascade_chain",
    }
    data = {k: v for k, v in body.items() if k in allowed}
    return await TokenService.update_budget(session, user_id, data)


@router.get("/alerts", summary="预算/配额告警列表")
async def list_alerts(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_db),
):
    return await TokenService.list_alerts(session, user_id=user_id, status=status)


@router.patch("/alerts/{alert_id}", summary="更新告警状态")
async def update_alert(alert_id: str, body: dict, session: AsyncSession = Depends(get_db)):
    try:
        return await TokenService.update_alert(session, alert_id, body.get("status", "resolved"))
    except ValueError as e:
        raise HTTPException(404, str(e))


# ==================== 优化策略 ====================

@router.post("/optimize/context", summary="上下文裁剪优化（Prompt 压缩）")
async def optimize_context(body: dict, session: AsyncSession = Depends(get_db)):
    return await OptimizationService.optimize_context(
        session,
        messages=body.get("messages", []),
        max_tokens=body.get("max_tokens", 8000),
        user_id=body.get("user_id"),
    )


@router.get("/suggest", summary="模型选择建议（任务-模型匹配矩阵）")
async def suggest_model(
    task_type: str = Query("chat"),
    input_tokens: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    return await OptimizationService.suggest_model(task_type, input_tokens)


@router.get("/cascade", summary="模型级联计划（降级链）")
async def get_cascade(
    task_type: str = Query("chat"),
    session: AsyncSession = Depends(get_db),
):
    return await OptimizationService.get_cascade_plan(session, task_type)


@router.get("/cascade/rules", summary="全部级联规则")
async def list_cascade_rules(session: AsyncSession = Depends(get_db)):
    return await OptimizationService.list_cascade_rules(session)


@router.post("/cascade/rules", summary="保存级联规则")
async def save_cascade_rule(body: dict, session: AsyncSession = Depends(get_db)):
    if not body.get("task_type"):
        raise HTTPException(400, "缺少 task_type")
    return await OptimizationService.save_cascade_rule(session, body)


@router.get("/effectiveness", summary="优化效果评估（压缩率/缓存命中率/成本节省）")
async def effectiveness(days: int = Query(30, ge=1, le=365), session: AsyncSession = Depends(get_db)):
    return await OptimizationService.get_effectiveness(session, days=days)


# ----------------------------------------------------------
# 成本分摊
# ----------------------------------------------------------

@router.get("/cost/by-project", summary="按项目聚合成本")
async def cost_by_project(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    from app.services.cost_allocation_service import CostAllocationService
    return await CostAllocationService.get_cost_by_project(session, start_date, end_date)


@router.get("/cost/by-department", summary="按部门聚合成本")
async def cost_by_department(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    from app.services.cost_allocation_service import CostAllocationService
    return await CostAllocationService.get_cost_by_department(session, start_date, end_date)


@router.get("/cost/by-model", summary="按模型聚合成本")
async def cost_by_model(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    from app.services.cost_allocation_service import CostAllocationService
    return await CostAllocationService.get_cost_by_model(session, start_date, end_date)


@router.get("/cost/trend", summary="每日成本趋势")
async def cost_trend(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    from app.services.cost_allocation_service import CostAllocationService
    return await CostAllocationService.get_daily_cost_trend(
        session, start_date, end_date, project_id, department
    )


@router.get("/cost/summary", summary="成本分摊综合报告")
async def cost_summary(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    from app.services.cost_allocation_service import CostAllocationService
    return await CostAllocationService.get_cost_summary(session, start_date, end_date)