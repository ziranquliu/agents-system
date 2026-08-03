"""MCP Server 服务 - CRUD 操作、健康检测、状态管理"""
import json
import uuid
from typing import Optional

import httpx
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import MCPServer
from app.schemas.mcp import MCPServerCreate, MCPServerUpdate, MCPServerResponse
from app.core.encryption import encrypt_secret


# 状态映射：DB ↔ API
_STATUS_DB_TO_API = {
    "active": "online",
    "inactive": "offline",
    "error": "error",
}
_STATUS_API_TO_DB = {
    "online": "active",
    "offline": "inactive",
    "error": "error",
}


def _db_status_to_api(db_status: str) -> str:
    """将数据库状态转换为 API 状态"""
    return _STATUS_DB_TO_API.get(db_status, "offline")


def _api_status_to_db(api_status: str) -> str:
    """将 API 状态转换为数据库状态"""
    return _STATUS_API_TO_DB.get(api_status, "inactive")


def server_to_response(server: MCPServer) -> MCPServerResponse:
    """将 MCPServer ORM 转换为响应对象"""
    return MCPServerResponse(
        id=server.id,
        name=server.name,
        endpoint=server.url,
        protocol=server.protocol or "sse",
        status=_db_status_to_api(server.status or "inactive"),
        health_status=server.health_status or "unknown",
        version=server.version,
        description=server.description,
        created_at=server.created_at,
    )


async def list_servers(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    protocol: Optional[str] = None,
    search: Optional[str] = None,
) -> tuple[list[MCPServer], int]:
    """获取 MCP Server 列表（分页 + 状态筛选 + 协议筛选 + 搜索）"""
    query = select(MCPServer)

    # 筛选条件
    if status:
        db_status = _api_status_to_db(status)
        query = query.where(MCPServer.status == db_status)
    if protocol:
        query = query.where(MCPServer.protocol == protocol)
    if search:
        query = query.where(
            or_(
                MCPServer.name.ilike(f"%{search}%"),
                MCPServer.description.ilike(f"%{search}%"),
            )
        )

    # 总数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页
    query = query.order_by(MCPServer.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    servers = list(result.scalars().all())

    return servers, total


async def get_server(db: AsyncSession, server_id: str) -> Optional[MCPServer]:
    """根据 ID 获取 MCP Server"""
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    return result.scalar_one_or_none()


async def create_server(db: AsyncSession, data: MCPServerCreate) -> MCPServer:
    """创建 MCP Server"""
    # 处理 API 密钥 → auth 字段
    auth_type = None
    auth_config = None
    if data.api_key:
        auth_type = "api_key"
        auth_config = json.dumps({"api_key": encrypt_secret(data.api_key)})

    server = MCPServer(
        id=str(uuid.uuid4()),
        name=data.name,
        url=data.endpoint,
        protocol=data.protocol or "sse",
        status="active",
        description=data.description,
        auth_type=auth_type,
        auth_config=auth_config,
        config=json.dumps(data.config) if data.config else None,
        health_status="unknown",
    )
    db.add(server)
    await db.flush()
    return server


async def update_server(db: AsyncSession, server_id: str, data: MCPServerUpdate) -> Optional[MCPServer]:
    """更新 MCP Server"""
    server = await get_server(db, server_id)
    if not server:
        return None

    update_data = data.model_dump(exclude_unset=True)

    # 字段映射
    if "endpoint" in update_data:
        update_data["url"] = update_data.pop("endpoint")

    # API 密钥 → auth 字段
    if "api_key" in update_data:
        api_key = update_data.pop("api_key")
        if api_key is not None:
            update_data["auth_type"] = "api_key"
            update_data["auth_config"] = json.dumps({"api_key": encrypt_secret(api_key)})

    # config → JSON
    if "config" in update_data:
        config_val = update_data.pop("config")
        update_data["config"] = json.dumps(config_val) if config_val else None

    for field, value in update_data.items():
        setattr(server, field, value)

    await db.flush()
    return server


async def delete_server(db: AsyncSession, server_id: str) -> bool:
    """删除 MCP Server（硬删除）"""
    server = await get_server(db, server_id)
    if not server:
        return False
    await db.delete(server)
    await db.flush()
    return True


async def update_server_status(
    db: AsyncSession, server_id: str, new_status: str
) -> Optional[MCPServer]:
    """更新 MCP Server 状态（online / offline / error）"""
    server = await get_server(db, server_id)
    if not server:
        return None

    server.status = _api_status_to_db(new_status)
    await db.flush()
    return server


async def health_check_server(db: AsyncSession, server_id: str) -> Optional[MCPServer]:
    """对 MCP Server 执行健康检测

    尝试访问 endpoint 的 /healthz 和 /ping 路径，
    更新 health_status 和 last_health_check。
    """
    server = await get_server(db, server_id)
    if not server:
        return None

    # 构造健康检测 URL
    base_url = server.url.rstrip("/")
    health_urls = [
        f"{base_url}/healthz",
        f"{base_url}/ping",
        f"{base_url}/health",
    ]
    if server.health_check_url:
        health_urls.insert(0, server.health_check_url)

    # 尝试健康检测
    is_healthy = False
    async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
        for url in health_urls:
            try:
                resp = await client.get(url)
                if resp.status_code < 500:
                    is_healthy = True
                    break
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RequestError):
                continue

    # 更新结果
    from datetime import datetime, timezone
    server.health_status = "healthy" if is_healthy else "unhealthy"
    server.last_health_check = datetime.now(timezone.utc)

    # 如果健康检测失败且状态为 active，标记为 error
    if not is_healthy and server.status == "active":
        server.status = "error"

    await db.flush()
    return server
