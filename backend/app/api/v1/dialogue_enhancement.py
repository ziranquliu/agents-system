"""
对话增强 API — Human-in-the-loop / 评分 / 满意度 / 高级导出
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.dialogue_enhancement_service import DialogueEnhancementService

router = APIRouter(prefix="/api/v1/dialogue", tags=["对话增强"])


def _inv_to_dict(i):
    return {
        "id": i.id,
        "conversation_id": i.conversation_id,
        "message_id": i.message_id,
        "agent_id": i.agent_id,
        "intervention_type": i.intervention_type,
        "original_content": i.original_content,
        "modified_content": i.modified_content,
        "approved": i.approved,
        "approval_note": i.approval_note,
        "handled_by": i.handled_by,
        "status": i.status,
        "handled_at": i.handled_at.isoformat() if i.handled_at else None,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }


def _rating_to_dict(r):
    return {
        "id": r.id,
        "conversation_id": r.conversation_id,
        "message_id": r.message_id,
        "satisfaction_score": r.satisfaction_score,
        "relevance_score": r.relevance_score,
        "accuracy_score": r.accuracy_score,
        "completeness_score": r.completeness_score,
        "clarity_score": r.clarity_score,
        "speed_score": r.speed_score,
        "overall_score": r.overall_score,
        "feedback_text": r.feedback_text,
        "feedback_category": r.feedback_category,
        "rated_by": r.rated_by,
        "rated_by_type": r.rated_by_type,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


# ----------------------------------------------------------
# Human-in-the-Loop
# ----------------------------------------------------------

@router.post("/interventions", summary="创建人工介入")
async def create_intervention(data: dict, db: AsyncSession = Depends(get_db)):
    svc = DialogueEnhancementService(db)
    inv = await svc.create_intervention(
        conversation_id=data["conversation_id"],
        agent_id=data["agent_id"],
        intervention_type=data["intervention_type"],
        original_content=data.get("original_content", ""),
        message_id=data.get("message_id", ""),
        handled_by=data.get("handled_by", ""),
    )
    return {"success": True, "data": _inv_to_dict(inv)}


@router.post("/interventions/{intervention_id}/approve", summary="审批通过")
async def approve_intervention(intervention_id: str, data: dict = {},
                               db: AsyncSession = Depends(get_db)):
    svc = DialogueEnhancementService(db)
    inv = await svc.approve_intervention(intervention_id, data.get("note", ""))
    if not inv:
        raise HTTPException(404, "介入记录不存在")
    return {"success": True, "data": _inv_to_dict(inv)}


@router.post("/interventions/{intervention_id}/reject", summary="驳回")
async def reject_intervention(intervention_id: str, data: dict = {},
                              db: AsyncSession = Depends(get_db)):
    svc = DialogueEnhancementService(db)
    inv = await svc.reject_intervention(intervention_id, data.get("note", ""))
    if not inv:
        raise HTTPException(404, "介入记录不存在")
    return {"success": True, "data": _inv_to_dict(inv)}


@router.post("/interventions/{intervention_id}/modify", summary="修改内容")
async def modify_content(intervention_id: str, data: dict,
                         db: AsyncSession = Depends(get_db)):
    svc = DialogueEnhancementService(db)
    inv = await svc.modify_content(intervention_id, data["new_content"])
    if not inv:
        raise HTTPException(404, "介入记录不存在")
    return {"success": True, "data": _inv_to_dict(inv)}


@router.get("/interventions", summary="查询介入列表")
async def list_interventions(
    conversation_id: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    svc = DialogueEnhancementService(db)
    items, total = await svc.list_interventions(
        conversation_id=conversation_id, agent_id=agent_id,
        status=status, offset=offset, limit=limit,
    )
    return {"success": True, "data": [_inv_to_dict(i) for i in items], "total": total}


# ----------------------------------------------------------
# 对话评分
# ----------------------------------------------------------

@router.post("/ratings", summary="创建评分")
async def create_rating(data: dict, db: AsyncSession = Depends(get_db)):
    svc = DialogueEnhancementService(db)
    rating = await svc.create_rating(data)
    return {"success": True, "data": _rating_to_dict(rating)}


@router.get("/ratings", summary="查询评分列表")
async def list_ratings(
    conversation_id: Optional[str] = Query(None),
    min_overall: Optional[float] = Query(None),
    feedback_category: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    svc = DialogueEnhancementService(db)
    items, total = await svc.list_ratings(
        conversation_id=conversation_id, min_overall=min_overall,
        feedback_category=feedback_category, offset=offset, limit=limit,
    )
    return {"success": True, "data": [_rating_to_dict(r) for r in items], "total": total}


@router.get("/ratings/stats", summary="评分统计")
async def get_rating_stats(db: AsyncSession = Depends(get_db)):
    svc = DialogueEnhancementService(db)
    stats = await svc.get_rating_stats()
    return {"success": True, "data": stats}


@router.post("/ratings/snapshot", summary="记录评分快照")
async def record_snapshot(data: dict = {}, db: AsyncSession = Depends(get_db)):
    svc = DialogueEnhancementService(db)
    analytics = await svc.record_analytics_snapshot(data.get("period", "realtime"))
    return {
        "success": True,
        "data": {
            "id": analytics.id,
            "period": analytics.period,
            "total_ratings": analytics.total_ratings,
            "avg_overall": analytics.avg_overall,
            "created_at": analytics.created_at.isoformat() if analytics.created_at else None,
        },
    }


# ----------------------------------------------------------
# 高级导出
# ----------------------------------------------------------

@router.get("/export/csv/{conversation_id}", summary="导出对话为 CSV")
async def export_csv(conversation_id: str, db: AsyncSession = Depends(get_db)):
    svc = DialogueEnhancementService(db)
    content = await svc.export_conversation_csv(conversation_id)
    return PlainTextResponse(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=conversation_{conversation_id[:8]}.csv"},
    )


@router.get("/export/pdf-html/{conversation_id}", summary="导出对话为 HTML（可打印/转 PDF）")
async def export_pdf_html(conversation_id: str, db: AsyncSession = Depends(get_db)):
    svc = DialogueEnhancementService(db)
    try:
        html = await svc.export_conversation_pdf_html(conversation_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return HTMLResponse(
        content=html,
        headers={"Content-Disposition": f"inline; filename=conversation_{conversation_id[:8]}.html"},
    )


@router.get("/export/conversations", summary="获取可导出的对话列表")
async def list_exportable_conversations(
    agent_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    svc = DialogueEnhancementService(db)
    items, total = await svc.list_conversations_for_export(
        agent_id=agent_id, user_id=user_id, offset=offset, limit=limit,
    )
    return {
        "success": True,
        "data": [
            {
                "id": c.id,
                "title": c.title,
                "agent_id": c.agent_id,
                "user_id": c.user_id,
                "message_count": c.message_count,
                "status": c.status,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in items
        ],
        "total": total,
    }
