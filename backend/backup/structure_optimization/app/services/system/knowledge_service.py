"""
知识库服务 - CRUD/文档管理/检索
"""
import json
import uuid
from typing import Optional

from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import select, func, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeBase, KnowledgeDocument, KnowledgeChunk


async def list_knowledge_bases(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 10,
    search: Optional[str] = None,
) -> tuple[list[KnowledgeBase], int]:
    """获取知识库列表"""
    query = select(KnowledgeBase)
    if search:
        query = query.where(
            or_(KnowledgeBase.name.ilike(f"%{search}%"), KnowledgeBase.description.ilike(f"%{search}%"))
        )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(desc(KnowledgeBase.updated_at)).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all()), total


async def create_knowledge_base(
    db: AsyncSession,
    name: str,
    description: Optional[str] = None,
    icon: str = "📚",
    created_by: str = "",
) -> KnowledgeBase:
    """创建知识库"""
    kb = KnowledgeBase(
        id=str(uuid.uuid4()),
        name=name,
        description=description,
        icon=icon,
        created_by=created_by,
    )
    db.add(kb)
    await db.flush()
    return kb


async def add_document(
    db: AsyncSession,
    knowledge_base_id: str,
    title: str,
    content: str,
    content_type: str = "text",
    file_name: Optional[str] = None,
    created_by: Optional[str] = None,
) -> KnowledgeDocument:
    """添加文档（自动分块）"""
    kb = await db.get(KnowledgeBase, knowledge_base_id)
    if not kb:
        raise ValueError("知识库不存在")

    doc = KnowledgeDocument(
        id=str(uuid.uuid4()),
        knowledge_base_id=knowledge_base_id,
        title=title,
        content=content,
        content_type=content_type,
        file_name=file_name,
        file_size=len(content.encode("utf-8")),
        status="indexed",
        created_by=created_by,
    )
    db.add(doc)
    await db.flush()

    # 自动分块
    chunks = _chunk_text(content, doc.id, knowledge_base_id)
    for chunk in chunks:
        db.add(chunk)

    doc.chunk_count = len(chunks)
    kb.document_count = (kb.document_count or 0) + 1
    kb.chunk_count = (kb.chunk_count or 0) + len(chunks)
    await db.flush()

    return doc


def _chunk_text(text: str, document_id: str, kb_id: str, chunk_size: int = 500, overlap: int = 50) -> list[KnowledgeChunk]:
    """将文本分块（按段落/句子分割）"""
    chunks = []
    paragraphs = text.split("\n\n")

    current_chunk = ""
    index = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) < chunk_size:
            current_chunk += (para + "\n\n")
        else:
            if current_chunk:
                chunk = KnowledgeChunk(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    knowledge_base_id=kb_id,
                    content=current_chunk.strip(),
                    chunk_index=index,
                    token_count=len(current_chunk) // 4,
                )
                chunks.append(chunk)
                index += 1
            current_chunk = para + "\n\n"

    if current_chunk:
        chunk = KnowledgeChunk(
            id=str(uuid.uuid4()),
            document_id=document_id,
            knowledge_base_id=kb_id,
            content=current_chunk.strip(),
            chunk_index=index,
            token_count=len(current_chunk) // 4,
        )
        chunks.append(chunk)

    return chunks


async def search_knowledge(
    db: AsyncSession,
    kb_id: str,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """搜索知识库（关键词匹配）"""
    result = await db.execute(
        select(KnowledgeChunk)
        .where(KnowledgeChunk.knowledge_base_id == kb_id)
        .where(KnowledgeChunk.content.ilike(f"%{query}%"))
        .limit(top_k)
    )
    chunks = result.scalars().all()

    return [
        {
            "chunk_id": c.id,
            "content": c.content,
            "chunk_index": c.chunk_index,
            "token_count": c.token_count,
            "document_id": c.document_id,
            "score": 1.0,  # 关键词匹配得分
        }
        for c in chunks
    ]


async def get_knowledge_base_documents(
    db: AsyncSession,
    kb_id: str,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[KnowledgeDocument], int]:
    """获取知识库文档列表"""
    query = select(KnowledgeDocument).where(KnowledgeDocument.knowledge_base_id == kb_id)
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    query = query.order_by(desc(KnowledgeDocument.created_at)).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all()), total


async def delete_document(db: AsyncSession, document_id: str) -> bool:
    """删除文档"""
    doc = await db.get(KnowledgeDocument, document_id)
    if not doc:
        return False

    kb = await db.get(KnowledgeBase, doc.knowledge_base_id)
    if kb:
        kb.document_count = max(0, (kb.document_count or 0) - 1)
        kb.chunk_count = max(0, (kb.chunk_count or 0) - doc.chunk_count)

    await db.delete(doc)
    await db.flush()
    return True
