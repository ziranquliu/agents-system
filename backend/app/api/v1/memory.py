"""
记忆管理 API - 三层记忆体系的 RESTful 接口
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.auth_service import get_current_user
from app.services.memory_service import MemoryService

router = APIRouter(prefix="/api/v1/memories", tags=["记忆管理"], dependencies=[Depends(get_current_user)])


def _memory_to_dict(m) -> dict:
    return {
        "id": m.id,
        "agent_id": m.agent_id,
        "memory_type": m.memory_type,
        "title": m.title,
        "content": m.content,
        "summary": m.summary,
        "category": m.category,
        "tags": m.tags,
        "keywords": m.keywords,
        "importance_score": m.importance_score,
        "access_count": m.access_count,
        "last_accessed_at": m.last_accessed_at.isoformat() if m.last_accessed_at else None,
        "is_sensitive": m.is_sensitive,
        "sensitive_info_type": m.sensitive_info_type,
        "masked_content": m.masked_content,
        "source_type": m.source_type,
        "source_id": m.source_id,
        "created_by": m.created_by,
        "is_public": m.is_public,
        "shared_to_agents": m.shared_to_agents,
        "is_forgotten": m.is_forgotten,
        "forget_reason": m.forget_reason,
        "forgotten_at": m.forgotten_at.isoformat() if m.forgotten_at else None,
        "ttl_seconds": m.ttl_seconds,
        "expires_at": m.expires_at.isoformat() if m.expires_at else None,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


# ----------------------------------------------------------
# CRUD
# ----------------------------------------------------------

@router.post("", summary="创建记忆")
async def create_memory(data: dict, db: AsyncSession = Depends(get_db)):
    """创建一条新记忆，自动进行敏感信息检测和重要性评分"""
    service = MemoryService(db)
    memory = await service.create_memory(data)
    return {"success": True, "data": _memory_to_dict(memory)}


@router.get("/{memory_id}", summary="获取单条记忆")
async def get_memory(memory_id: str, db: AsyncSession = Depends(get_db)):
    """获取记忆详情，同时自动更新访问计数和重要性评分"""
    service = MemoryService(db)
    memory = await service.get_memory(memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在或已被遗忘")
    return {"success": True, "data": _memory_to_dict(memory)}


@router.put("/{memory_id}", summary="更新记忆")
async def update_memory(memory_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    """更新记忆内容，重新进行敏感检测和评分"""
    service = MemoryService(db)
    memory = await service.update_memory(memory_id, data)
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在或已被遗忘")
    return {"success": True, "data": _memory_to_dict(memory)}


@router.delete("/{memory_id}", summary="遗忘记忆（软删除）")
async def delete_memory(memory_id: str, reason: str = Query("manual"), db: AsyncSession = Depends(get_db)):
    """将记忆标记为遗忘（软删除），支持指定原因"""
    service = MemoryService(db)
    ok = await service.delete_memory(memory_id, reason)
    if not ok:
        raise HTTPException(status_code=404, detail="记忆不存在或已被遗忘")
    return {"success": True, "message": "记忆已标记为遗忘"}


@router.delete("/{memory_id}/hard", summary="物理删除记忆（GDPR）")
async def hard_delete_memory(memory_id: str, db: AsyncSession = Depends(get_db)):
    """从数据库中彻底删除（GDPR 合规擦除）"""
    service = MemoryService(db)
    ok = await service.hard_delete_memory(memory_id)
    if not ok:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return {"success": True, "message": "记忆已永久删除"}


# ----------------------------------------------------------
# 查询
# ----------------------------------------------------------

@router.get("", summary="查询记忆列表")
async def list_memories(
    agent_id: Optional[str] = Query(None),
    memory_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    is_sensitive: Optional[bool] = Query(None),
    is_public: Optional[bool] = Query(None),
    include_forgotten: bool = Query(False),
    keyword: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    importance_min: Optional[float] = Query(None),
    importance_max: Optional[float] = Query(None),
    sort_by: str = Query("created_at"),
    sort_desc: bool = Query(True),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """多维过滤查询记忆列表"""
    service = MemoryService(db)
    items, total = await service.list_memories(
        agent_id=agent_id,
        memory_type=memory_type,
        category=category,
        is_sensitive=is_sensitive,
        is_public=is_public,
        include_forgotten=include_forgotten,
        keyword=keyword,
        tag=tag,
        importance_min=importance_min,
        importance_max=importance_max,
        sort_by=sort_by,
        sort_desc=sort_desc,
        offset=offset,
        limit=limit,
    )
    return {
        "success": True,
        "data": [_memory_to_dict(m) for m in items],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


# ----------------------------------------------------------
# 遗忘管理
# ----------------------------------------------------------

@router.post("/process-expired", summary="处理过期记忆")
async def process_expired(db: AsyncSession = Depends(get_db)):
    """自动处理所有已过期/低重要性的记忆"""
    service = MemoryService(db)
    expired = await service.process_expired_memories()
    low_imp = await service.process_low_importance_memories()
    return {
        "success": True,
        "data": {
            "expired_count": expired,
            "low_importance_count": low_imp,
        },
        "message": f"已处理 {expired} 条过期记忆、{low_imp} 条低重要性记忆",
    }


@router.post("/batch-forget", summary="批量遗忘智能体记忆")
async def batch_forget(data: dict, db: AsyncSession = Depends(get_db)):
    """批量遗忘某个智能体的全部或指定类型记忆"""
    service = MemoryService(db)
    count = await service.forget_memories_by_agent(
        agent_id=data["agent_id"],
        memory_type=data.get("memory_type"),
    )
    return {"success": True, "data": {"forgotten_count": count}}


@router.post("/merge-duplicates", summary="合并重复记忆")
async def merge_duplicates(data: dict, db: AsyncSession = Depends(get_db)):
    """合并指定智能体的相似记忆（基于内容相似度）"""
    service = MemoryService(db)
    count = await service.merge_duplicate_memories(
        agent_id=data["agent_id"],
        similarity_threshold=data.get("similarity_threshold", 0.8),
    )
    return {"success": True, "data": {"merged_count": count}}


# ----------------------------------------------------------
# 统计
# ----------------------------------------------------------

@router.get("/stats/{agent_id}", summary="获取智能体记忆统计")
async def get_memory_stats(agent_id: str, db: AsyncSession = Depends(get_db)):
    """获取指定智能体的记忆统计数据"""
    service = MemoryService(db)
    stats = await service.get_memory_stats(agent_id)
    return {"success": True, "data": stats}


@router.post("/snapshot/{agent_id}", summary="记录记忆分析快照")
async def record_snapshot(agent_id: str, db: AsyncSession = Depends(get_db)):
    """记录当前时刻的记忆分析快照到历史表"""
    service = MemoryService(db)
    analytics = await service.record_analytics_snapshot(agent_id)
    return {
        "success": True,
        "data": {
            "id": analytics.id,
            "agent_id": analytics.agent_id,
            "total_memories": analytics.total_memories,
            "created_at": analytics.created_at.isoformat() if analytics.created_at else None,
        },
    }


# ----------------------------------------------------------
# GDPR
# ----------------------------------------------------------

@router.delete("/gdpr/user/{user_id}", summary="GDPR 删除用户数据")
async def gdpr_delete(user_id: str, db: AsyncSession = Depends(get_db)):
    """GDPR 合规：删除指定用户创建的所有记忆"""
    service = MemoryService(db)
    count = await service.gdpr_delete_user_data(user_id)
    return {"success": True, "message": f"已永久删除 {count} 条记忆"}


@router.get("/gdpr/export/{user_id}", summary="GDPR 导出用户数据")
async def gdpr_export(user_id: str, db: AsyncSession = Depends(get_db)):
    """GDPR 合规：导出指定用户创建的所有记忆"""
    service = MemoryService(db)
    data = await service.gdpr_export_user_data(user_id)
    return {"success": True, "data": data}