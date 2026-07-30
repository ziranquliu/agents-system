"""
系统监控 API - 健康检查/性能统计
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services import system_monitor_service

router = APIRouter(tags=["系统监控"])


@router.get("/system/health")
async def get_system_health():
    """获取系统健康状态"""
    return await system_monitor_service.get_system_health()


@router.get("/system/latency")
async def get_api_latency():
    """获取 API 延迟统计"""
    stats = system_monitor_service.get_api_latency_stats()
    return {"endpoints": stats}


@router.post("/system/latency/record")
async def record_latency(
    endpoint: str = Query(...),
    duration_ms: float = Query(...),
):
    """记录 API 延迟"""
    system_monitor_service.record_api_latency(endpoint, duration_ms)
    return {"message": "recorded"}
