"""
Skill 使用优化 API - 缓存/执行统计/DAG
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.auth_service import get_current_user
from app.services import skill_optimization_service

router = APIRouter(tags=["Skill 优化"], dependencies=[Depends(get_current_user)])


@router.get("/skills/optimization/cache-stats")
async def get_cache_stats():
    """获取 Skill 缓存统计"""
    return skill_optimization_service.get_cache_stats()


@router.post("/skills/optimization/cache-clear")
async def clear_skill_cache():
    """清除 Skill 缓存"""
    return skill_optimization_service.clear_cache()


@router.get("/skills/optimization/execution-stats")
async def get_execution_stats(
    skill_id: str | None = Query(None, description="指定 Skill ID"),
):
    """获取 Skill 执行统计"""
    return skill_optimization_service.get_execution_stats(skill_id)


@router.get("/skills/optimization/dag-plan")
async def get_dag_plan(
    skill_ids: str = Query(..., description="逗号分隔的 Skill ID 列表"),
    db: AsyncSession = Depends(get_db),
):
    """计算 DAG 执行计划"""
    ids = [s.strip() for s in skill_ids.split(",") if s.strip()]
    deps_data = await skill_optimization_service.get_skill_dependencies(db)
    deps = deps_data["dependencies"]

    levels = skill_optimization_service.compute_dag_plan(ids, deps)
    return {
        "skill_ids": ids,
        "levels": levels,
        "level_count": len(levels),
        "suggestion": "每一层内的 Skill 可以并行执行，不同层按顺序执行",
    }


@router.post("/skills/optimization/record-execution")
async def record_execution(
    skill_id: str = Query(...),
    duration_ms: float = Query(...),
):
    """记录 Skill 执行时间"""
    skill_optimization_service.record_execution(skill_id, duration_ms)
    return {"message": "已记录"}