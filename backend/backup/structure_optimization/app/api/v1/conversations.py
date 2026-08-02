"""对话历史管理 API — 完整的 CRUD + 消息管理"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationListResponse,
    ConversationStatsResponse,
    MessageCreate,
    MessageResponse,
    MessageListResponse,
)
from app.services.auth_service import get_current_user
from app.services import conversation_service

router = APIRouter()


# ──────────────────────────────────────────
# 统计（置于参数化路由之前，避免被 /{id} 吞掉）
# ──────────────────────────────────────────


@router.get("/stats/overview", response_model=ConversationStatsResponse)
async def get_conversation_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的对话统计"""
    stats = await conversation_service.get_conversation_stats(
        db=db,
        user_id=current_user.id,
    )
    return ConversationStatsResponse(**stats)


# ──────────────────────────────────────────
# 对话 CRUD
# ──────────────────────────────────────────


@router.get("/", response_model=ConversationListResponse)
async def list_conversations(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    agent_id: str = Query(None, description="按 Agent 筛选"),
    search: str = Query(None, description="搜索标题关键词"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取对话列表（分页 + 按 Agent 筛选 + 搜索标题）"""
    conversations, total = await conversation_service.list_conversations(
        db=db,
        page=page,
        page_size=page_size,
        agent_id=agent_id,
        search=search,
        user_id=current_user.id,
    )
    return ConversationListResponse(
        items=[ConversationResponse.model_validate(c) for c in conversations],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    data: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建新对话"""
    workspace_id = f"default_{current_user.id}"
    conversation = await conversation_service.create_conversation(
        db=db,
        data=data,
        user_id=current_user.id,
        workspace_id=workspace_id,
    )
    return ConversationResponse.model_validate(conversation)


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取对话详情"""
    conversation = await conversation_service.get_conversation(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationResponse.model_validate(conversation)


@router.put("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    data: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新对话（标题等）"""
    conversation = await conversation_service.update_conversation(db, conversation_id, data)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationResponse.model_validate(conversation)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除对话（软删除）"""
    success = await conversation_service.delete_conversation(db, conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return None


# ──────────────────────────────────────────
# 消息管理
# ──────────────────────────────────────────


@router.get("/{conversation_id}/messages", response_model=MessageListResponse)
async def list_messages(
    conversation_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页数量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取消息列表（分页，按时间正序）"""
    messages, total = await conversation_service.list_messages(
        db=db,
        conversation_id=conversation_id,
        page=page,
        page_size=page_size,
    )
    return MessageListResponse(
        items=[MessageResponse.model_validate(m) for m in messages],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{conversation_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def add_message(
    conversation_id: str,
    data: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """添加消息到对话"""
    message = await conversation_service.add_message(db, conversation_id, data)
    if not message:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return MessageResponse.model_validate(message)


@router.delete("/{conversation_id}/messages", status_code=status.HTTP_204_NO_CONTENT)
async def clear_messages(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """清空对话的所有消息"""
    success = await conversation_service.clear_messages(db, conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return None
