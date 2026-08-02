"""
MCP 使用优化 API - 熔断器/连接池/负载均衡/安全
"""
from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel

from app.services import mcp_optimization_service
from app.services.auth_service import get_current_user

router = APIRouter(tags=["MCP 优化"], dependencies=[Depends(get_current_user)])


# ---- 熔断器 ----
@router.get("/mcp/optimization/circuit-breaker/{server_id}")
async def check_circuit_breaker(server_id: str):
    return mcp_optimization_service.check_circuit_breaker(server_id)


@router.post("/mcp/optimization/circuit-breaker/{server_id}/failure")
async def record_failure(server_id: str):
    return mcp_optimization_service.record_failure(server_id)


@router.post("/mcp/optimization/circuit-breaker/{server_id}/success")
async def record_success(server_id: str):
    return mcp_optimization_service.record_success(server_id)


@router.post("/mcp/optimization/circuit-breaker/{server_id}/reset")
async def reset_circuit_breaker(server_id: str):
    return mcp_optimization_service.reset_circuit_breaker(server_id)


# ---- 连接池 ----
@router.get("/mcp/optimization/pool")
async def get_pool_stats():
    return mcp_optimization_service.get_pool_stats()


# ---- 负载均衡 ----
@router.get("/mcp/optimization/load-balancer")
async def get_load_balancer():
    return mcp_optimization_service.get_load_balancer_status()


@router.post("/mcp/optimization/load-balancer/servers")
async def set_load_balancer_servers(server_ids: list[str] = Body(..., embed=True)):
    return mcp_optimization_service.set_load_balancer_servers(server_ids)


@router.get("/mcp/optimization/load-balancer/next")
async def get_next_server(strategy: str = Query("round-robin")):
    return mcp_optimization_service.get_next_server(strategy)


# ---- 安全 ----
@router.get("/mcp/optimization/security")
async def get_security():
    return mcp_optimization_service.get_security_config()


@router.post("/mcp/optimization/security")
async def update_security(config: dict = Body(...)):
    return mcp_optimization_service.update_security_config(config)