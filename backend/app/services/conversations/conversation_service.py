import json
import uuid
from typing import Optional
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.conversation import Conversation, Message
from app.models.agent import Agent
from app.schemas.conversation import ConversationCreate, ConversationUpdate, MessageCreate

"""对话历史服务 - CRUD 操作与筛选"""




async def _attach_agent_names(db: AsyncSession, conversations: list[Conversation]) -> None:
    """批量填充 agent_name 和 total_tokens 到对话对象（瞬态属性）"""
    if not conversations:
        return

    # agent_name
    agent_ids = list(set(c.agent_id for c in conversations if c.agent_id))
    if agent_ids:
        result = await db.execute(
            select(Agent.id, Agent.name).where(Agent.id.in_(agent_ids))
        )
        agent_map = dict(result.all())
        for conv in conversations:
            conv.agent_name = agent_map.get(conv.agent_id)

    # total_tokens ← token_count
    for conv in conversations:
        conv.total_tokens = conv.token_count or 0


async def _enrich_messages(messages: list[Message]) -> None:
    """批量填充 tokens 瞬态属性到消息对象"""
    for msg in messages:
        msg.tokens = msg.total_tokens or 0


async def list_conversations(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    agent_id: Optional[str] = None,
    search: Optional[str] = None,
    user_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
) -> tuple[list[Conversation], int]:
    """获取对话列表（分页 + 筛选）"""
    query = select(Conversation)

    # 筛选条件
    if user_id:
        query = query.where(Conversation.user_id == user_id)
    if workspace_id:
        query = query.where(Conversation.workspace_id == workspace_id)
    if agent_id:
        query = query.where(Conversation.agent_id == agent_id)
    if search:
        query = query.where(Conversation.title.ilike(f"%{search}%"))

    # 默认排除已删除
    query = query.where(Conversation.status != "deleted")

    # 总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页
    query = query.order_by(Conversation.updated_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    conversations = list(result.scalars().all())

    await _attach_agent_names(db, conversations)

    return conversations, total


async def get_conversation(db: AsyncSession, conversation_id: str) -> Optional[Conversation]:
    """根据 ID 获取对话详情"""
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation or conversation.status == "deleted":
        return None
    await _attach_agent_names(db, [conversation])
    return conversation


async def create_conversation(
    db: AsyncSession,
    data: ConversationCreate,
    user_id: str,
    workspace_id: str,
) -> Conversation:
    """创建新对话"""
    conversation = Conversation(
        id=str(uuid.uuid4()),
        title=data.title,
        agent_id=data.agent_id,
        user_id=user_id,
        workspace_id=workspace_id,
        status="active",
        message_count=0,
        token_count=0,
        compressed=0,
    )
    db.add(conversation)
    await db.flush()
    await _attach_agent_names(db, [conversation])
    return conversation


async def update_conversation(
    db: AsyncSession,
    conversation_id: str,
    data: ConversationUpdate,
) -> Optional[Conversation]:
    """更新对话信息"""
    conversation = await get_conversation(db, conversation_id)
    if not conversation:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(conversation, field, value)

    await db.flush()
    return conversation


async def delete_conversation(db: AsyncSession, conversation_id: str) -> bool:
    """删除对话（软删除 — status → 'deleted'）"""
    conversation = await get_conversation(db, conversation_id)
    if not conversation:
        return False
    conversation.status = "deleted"
    await db.flush()
    return True


async def add_message(
    db: AsyncSession,
    conversation_id: str,
    data: MessageCreate,
) -> Optional[Message]:
    """添加消息到对话并更新统计"""
    conversation = await get_conversation(db, conversation_id)
    if not conversation:
        return None

    message = Message(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role=data.role,
        content=data.content,
        content_type="text",
        total_tokens=data.tokens or 0,
        model_used=data.model_name,
        metadata_json=json.dumps(data.metadata, ensure_ascii=False) if data.metadata else None,
    )
    db.add(message)

    # 更新对话统计
    conversation.message_count = (conversation.message_count or 0) + 1
    conversation.token_count = (conversation.token_count or 0) + (data.tokens or 0)

    await db.flush()
    await _enrich_messages([message])
    return message


async def list_messages(
    db: AsyncSession,
    conversation_id: str,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Message], int]:
    """获取消息列表（分页，按时间正序）"""
    # 验证对话存在
    conversation = await get_conversation(db, conversation_id)
    if not conversation:
        return [], 0

    query = select(Message).where(Message.conversation_id == conversation_id)

    # 总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页，按时间正序
    query = query.order_by(Message.created_at.asc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    messages = list(result.scalars().all())

    await _enrich_messages(messages)
    return messages, total


async def clear_messages(db: AsyncSession, conversation_id: str) -> bool:
    """清空对话的所有消息，重置统计"""
    conversation = await get_conversation(db, conversation_id)
    if not conversation:
        return False

    await db.execute(
        delete(Message).where(Message.conversation_id == conversation_id)
    )

    # 重置统计
    conversation.message_count = 0
    conversation.token_count = 0

    await db.flush()
    return True


async def get_conversation_stats(
    db: AsyncSession,
    user_id: Optional[str] = None,
) -> dict:
    """获取对话统计"""
    query = select(
        func.count(Conversation.id),
        func.coalesce(func.sum(Conversation.token_count), 0),
    ).select_from(Conversation).where(Conversation.status != "deleted")

    if user_id:
        query = query.where(Conversation.user_id == user_id)

    result = await db.execute(query)
    row = result.one()
    return {
        "total_conversations": row[0] or 0,
        "total_tokens": row[1] or 0,
    }
