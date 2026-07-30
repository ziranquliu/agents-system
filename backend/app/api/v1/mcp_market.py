"""MCP 在线市场 API"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from app.models.user import User
from app.api.v1.auth import get_current_user
from app.services import mcp_market_service

router = APIRouter(tags=["MCP 在线市场"])


@router.get("/mcp/market")
async def list_market_mcp(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """列出 MCP 市场服务"""
    return await mcp_market_service.list_market_items(
        page=page, page_size=page_size, category=category, search=search
    )


@router.get("/mcp/market/categories")
async def list_mcp_categories(
    current_user: User = Depends(get_current_user),
):
    """获取 MCP 分类列表"""
    cats = await mcp_market_service.list_categories()
    return {"categories": cats}


@router.get("/mcp/market/{item_id}")
async def get_market_mcp(
    item_id: str,
    current_user: User = Depends(get_current_user),
):
    """获取 MCP 市场服务详情"""
    item = await mcp_market_service.get_market_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="MCP 服务不存在")
    return item


@router.post("/mcp/market/{item_id}/install")
async def install_market_mcp(
    item_id: str,
    body: dict = {},
    current_user: User = Depends(get_current_user),
):
    """安装 MCP 市场服务到本地"""
    name_override = body.get("name")
    config_override = body.get("config")
    try:
        result = await mcp_market_service.install_market_item(
            user_id=current_user.id,
            item_id=item_id,
            name_override=name_override,
            config_override=config_override,
        )
        return {"message": "安装成功", "mcp_server": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
