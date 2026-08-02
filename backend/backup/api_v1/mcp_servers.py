"""MCP Server 管理 API - 完整的 CRUD + 健康检测"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.schemas.mcp import (
    MCPServerCreate,
    MCPServerUpdate,
    MCPServerResponse,
    MCPServerListResponse,
)
from app.services.auth_service import get_current_user
from app.services import mcp_service

router = APIRouter()


@router.get("/", response_model=MCPServerListResponse)
async def list_servers(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: str = Query(None, description="按状态筛选 (online/offline/error)"),
    protocol: str = Query(None, description="按协议筛选 (sse/stdio/streamable-http)"),
    search: str = Query(None, description="搜索关键词"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 MCP Server 列表（分页 + 状态筛选 + 协议筛选 + 搜索）"""
    servers, total = await mcp_service.list_servers(
        db=db,
        page=page,
        page_size=page_size,
        status=status,
        protocol=protocol,
        search=search,
    )

    return MCPServerListResponse(
        items=[mcp_service.server_to_response(s) for s in servers],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=MCPServerResponse, status_code=201)
async def create_server(
    data: MCPServerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建新的 MCP Server"""
    server = await mcp_service.create_server(db, data)
    return mcp_service.server_to_response(server)


@router.get("/{server_id}", response_model=MCPServerResponse)
async def get_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 MCP Server 详情"""
    server = await mcp_service.get_server(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP Server not found")
    return mcp_service.server_to_response(server)


@router.put("/{server_id}", response_model=MCPServerResponse)
async def update_server(
    server_id: str,
    data: MCPServerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新 MCP Server 配置"""
    server = await mcp_service.update_server(db, server_id, data)
    if not server:
        raise HTTPException(status_code=404, detail="MCP Server not found")
    return mcp_service.server_to_response(server)


@router.delete("/{server_id}", status_code=204)
async def delete_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除 MCP Server"""
    success = await mcp_service.delete_server(db, server_id)
    if not success:
        raise HTTPException(status_code=404, detail="MCP Server not found")
    return None


@router.post("/{server_id}/health-check", response_model=MCPServerResponse)
async def health_check_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """对 MCP Server 执行健康检测

    依次尝试 /healthz, /ping, /health 端点，更新 health_status。
    """
    server = await mcp_service.health_check_server(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="MCP Server not found")
    return mcp_service.server_to_response(server)
