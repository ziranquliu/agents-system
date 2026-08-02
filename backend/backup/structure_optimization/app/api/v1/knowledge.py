"""
知识库 API - CRUD/文档管理/检索
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services import knowledge_service

router = APIRouter(tags=["知识库"])


@router.get("/knowledge-bases")
async def list_knowledge_bases(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    items, total = await knowledge_service.list_knowledge_bases(db, page=page, page_size=page_size, search=search)
    return {
        "items": [_format_kb(k) for k in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/knowledge-bases")
async def create_knowledge_base(
    name: str = Body(...),
    description: str | None = None,
    icon: str = "📚",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kb = await knowledge_service.create_knowledge_base(db, name=name, description=description, icon=icon, created_by=current_user.id)
    return _format_kb(kb)


@router.get("/knowledge-bases/{kb_id}")
async def get_knowledge_base(
    kb_id: str,
    db: AsyncSession = Depends(get_db),
):
    kb = await db.get(knowledge_service.KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return _format_kb(kb)


@router.get("/knowledge-bases/{kb_id}/documents")
async def get_documents(
    kb_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    items, total = await knowledge_service.get_knowledge_base_documents(db, kb_id, page=page, page_size=page_size)
    return {
        "items": [_format_doc(d) for d in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/knowledge-bases/{kb_id}/documents")
async def add_document(
    kb_id: str,
    title: str = Body(...),
    content: str = Body(...),
    content_type: str = "text",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        doc = await knowledge_service.add_document(
            db, kb_id, title=title, content=content, content_type=content_type, created_by=current_user.id,
        )
        return _format_doc(doc)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/knowledge-bases/{kb_id}/documents/{doc_id}")
async def delete_document(
    kb_id: str,
    doc_id: str,
    db: AsyncSession = Depends(get_db),
):
    success = await knowledge_service.delete_document(db, doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"message": "文档已删除"}


@router.get("/knowledge-bases/{kb_id}/search")
async def search_knowledge(
    kb_id: str,
    query: str = Query(..., min_length=1),
    top_k: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    results = await knowledge_service.search_knowledge(db, kb_id, query=query, top_k=top_k)
    return {"results": results, "query": query, "count": len(results)}


def _format_kb(k):
    return {
        "id": k.id,
        "name": k.name,
        "description": k.description,
        "icon": k.icon,
        "document_count": k.document_count,
        "chunk_count": k.chunk_count,
        "status": k.status,
        "created_by": k.created_by,
        "created_at": k.created_at.isoformat() if k.created_at else None,
        "updated_at": k.updated_at.isoformat() if k.updated_at else None,
    }


def _format_doc(d):
    return {
        "id": d.id,
        "knowledge_base_id": d.knowledge_base_id,
        "title": d.title,
        "content": d.content[:200] + "..." if d.content and len(d.content) > 200 else d.content,
        "content_type": d.content_type,
        "file_name": d.file_name,
        "file_size": d.file_size,
        "chunk_count": d.chunk_count,
        "status": d.status,
        "created_by": d.created_by,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }
