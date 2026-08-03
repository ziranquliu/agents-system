"""
会话增强 API - Token管理/上下文优化/生命周期/导出
"""
from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services import conversation_enhancement_service

router = APIRouter(tags=["会话增强"], dependencies=[Depends(get_current_user)])


# ---- Token 管理 ----
@router.get("/conversations/token-stats")
async def get_token_stats():
    """获取 Token 使用统计"""
    return conversation_enhancement_service.get_token_stats()


@router.post("/conversations/token-stats/reset")
async def reset_token_stats():
    """重置 Token 统计"""
    return conversation_enhancement_service.reset_token_stats()


@router.post("/conversations/token-usage/record")
async def record_token_usage(
    model_name: str = Query(...),
    input_tokens: int = Query(...),
    output_tokens: int = Query(...),
):
    """记录 Token 使用"""
    return conversation_enhancement_service.record_token_usage(model_name, input_tokens, output_tokens)


# ---- 上下文优化 ----
@router.post("/conversations/context/optimize")
async def optimize_context(
    messages: list[dict] = Body(...),
    max_tokens: int = Query(8000),
):
    """优化上下文窗口"""
    result = conversation_enhancement_service.optimize_context(messages, max_tokens)
    return {"original_count": len(messages), "optimized_count": len(result), "messages": result}


@router.get("/conversations/context/suggest")
async def suggest_context_window(
    conversation_length: int = Query(10, ge=1),
):
    """根据对话长度建议 context window"""
    return conversation_enhancement_service.suggest_context_window(conversation_length)


# ---- 会话生命周期 ----
@router.post("/conversations/{conversation_id}/archive")
async def archive_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """归档对话"""
    try:
        return await conversation_enhancement_service.archive_conversation(db, conversation_id)
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/conversations/{conversation_id}/export")
async def export_conversation(
    conversation_id: str,
    format: str = Query("json", pattern="^(json|markdown)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出对话"""
    try:
        return await conversation_enhancement_service.export_conversation(db, conversation_id, format)
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=str(e))