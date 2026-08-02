"""
Skill 跨 Agent 复用 API
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.auth_service import get_current_user
from app.services.skill_reuse_service import SkillReuseService

router = APIRouter(prefix="/api/v1/skill-reuse", tags=["Skill 复用"], dependencies=[Depends(get_current_user)])


def _relation_to_dict(r):
    return {
        "id": r.id,
        "source_skill_id": r.source_skill_id,
        "source_skill_name": r.source_skill_name,
        "source_agent_id": r.source_agent_id,
        "target_skill_id": r.target_skill_id,
        "target_skill_name": r.target_skill_name,
        "target_agent_id": r.target_agent_id,
        "reuse_mode": r.reuse_mode,
        "sync_mode": r.sync_mode,
        "status": r.status,
        "source_version": r.source_version,
        "target_version": r.target_version,
        "synced_version": r.synced_version,
        "last_notified_at": r.last_notified_at.isoformat() if r.last_notified_at else None,
        "last_synced_at": r.last_synced_at.isoformat() if r.last_synced_at else None,
        "reuse_count": r.reuse_count or 0,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


# ----------------------------------------------------------
# 复用关系 CRUD
# ----------------------------------------------------------

@router.post("", summary="创建复用关系")
async def create_reuse(data: dict, db: AsyncSession = Depends(get_db)):
    """创建 Skill 跨 Agent 复用关系"""
    svc = SkillReuseService(db)
    try:
        rel = await svc.create_reuse(
            source_skill_id=data["source_skill_id"],
            target_agent_id=data["target_agent_id"],
            reuse_mode=data.get("reuse_mode", "direct_ref"),
            sync_mode=data.get("sync_mode", "manual"),
            source_agent_id=data.get("source_agent_id", ""),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": _relation_to_dict(rel)}


@router.delete("/{relation_id}", summary="删除复用关系")
async def remove_reuse(relation_id: str, db: AsyncSession = Depends(get_db)):
    svc = SkillReuseService(db)
    ok = await svc.remove_reuse(relation_id)
    if not ok:
        raise HTTPException(404, "关系不存在")
    return {"success": True, "message": "复用关系已删除"}


@router.get("/{relation_id}", summary="获取复用关系详情")
async def get_reuse(relation_id: str, db: AsyncSession = Depends(get_db)):
    svc = SkillReuseService(db)
    rel = await svc.get_reuse(relation_id)
    if not rel:
        raise HTTPException(404, "关系不存在")
    return {"success": True, "data": _relation_to_dict(rel)}


@router.get("", summary="查询复用关系列表")
async def list_reuses(
    source_skill_id: Optional[str] = Query(None),
    target_agent_id: Optional[str] = Query(None),
    target_skill_id: Optional[str] = Query(None),
    reuse_mode: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    svc = SkillReuseService(db)
    items, total = await svc.list_reuses(
        source_skill_id=source_skill_id,
        target_agent_id=target_agent_id,
        target_skill_id=target_skill_id,
        reuse_mode=reuse_mode,
        status=status,
        offset=offset,
        limit=limit,
    )
    return {
        "success": True,
        "data": [_relation_to_dict(r) for r in items],
        "total": total,
    }


# ----------------------------------------------------------
# 同步
# ----------------------------------------------------------

@router.get("/check-updates/{source_skill_id}", summary="检查源 Skill 更新")
async def check_updates(source_skill_id: str, db: AsyncSession = Depends(get_db)):
    svc = SkillReuseService(db)
    data = await svc.check_updates(source_skill_id)
    return {"success": True, "data": data}


@router.post("/sync/{relation_id}", summary="同步单条复用")
async def sync_reuse(relation_id: str, db: AsyncSession = Depends(get_db)):
    svc = SkillReuseService(db)
    result = await svc.sync_reuse(relation_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return {"success": True, "data": result}


@router.post("/sync-all/{source_skill_id}", summary="同步源 Skill 所有复用")
async def sync_all(source_skill_id: str, db: AsyncSession = Depends(get_db)):
    svc = SkillReuseService(db)
    results = await svc.sync_all_for_source(source_skill_id)
    return {"success": True, "data": results, "total": len(results)}


# ----------------------------------------------------------
# 统计与排行
# ----------------------------------------------------------

@router.get("/stats/{skill_id}", summary="获取 Skill 复用统计")
async def get_reuse_stats(skill_id: str, db: AsyncSession = Depends(get_db)):
    svc = SkillReuseService(db)
    stats = await svc.get_reuse_stats(skill_id)
    return {"success": True, "data": stats}


@router.get("/ranking", summary="复用排行")
async def get_reuse_ranking(limit: int = Query(10, ge=1, le=50), db: AsyncSession = Depends(get_db)):
    svc = SkillReuseService(db)
    data = await svc.get_reuse_ranking(limit)
    return {"success": True, "data": data}


@router.get("/graph/{source_skill_id}", summary="复用关系图")
async def get_reuse_graph(source_skill_id: str, db: AsyncSession = Depends(get_db)):
    svc = SkillReuseService(db)
    data = await svc.get_reuse_graph(source_skill_id)
    return {"success": True, "data": data}