"""
Agent 在线市场 API - 列表/分类/详情/安装
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.schemas.agent import AgentResponse
from app.services.auth_service import get_current_user
from app.services import agent_market_service

router = APIRouter(tags=["Agent 在线市场"])


class MarketAgentItem(BaseModel):
    """市场 Agent 列表项"""
    id: str
    name: str
    description: str
    category: str
    version: str
    author: str
    icon: str
    tags: list[str]
    install_count: int
    rating: int
    config_schema: dict


class MarketAgentDetail(MarketAgentItem):
    """市场 Agent 详情（含完整配置）"""
    system_prompt: str | None = None
    welcome_message: str | None = None
    model_provider: str | None = None
    model_name: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    context_window: int | None = None
    enabled_skills: list[str] | None = None
    enabled_mcp_servers: list[str] | None = None


class MarketListResponse(BaseModel):
    """市场列表响应（分页）"""
    total: int
    page: int
    page_size: int
    items: list[MarketAgentItem]


class CategoriesResponse(BaseModel):
    """分类列表响应"""
    categories: list[str]


class InstallRequest(BaseModel):
    """安装请求"""
    name: str | None = Field(None, description="自定义 Agent 名称")
    config: dict | None = Field(None, description="自定义配置")


@router.get("/agents/market")
async def list_market_agents(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    category: str | None = None,
    search: str | None = None,
):
    """获取 Agent 市场列表"""
    items, total = await agent_market_service.list_agents(
        page=page,
        page_size=page_size,
        category=category,
        search=search,
    )
    return {
        "items": [MarketAgentItem(**i).model_dump() for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/agents/market/categories")
async def list_agent_categories():
    """获取所有 Agent 分类"""
    categories = await agent_market_service.list_categories()
    return {"categories": categories}


@router.get("/agents/market/{agent_id}")
async def get_market_agent(agent_id: str):
    """获取 Agent 详情"""
    item = await agent_market_service.get_agent_detail(agent_id)
    if not item:
        raise HTTPException(status_code=404, detail="Agent template not found")
    return MarketAgentDetail(**item).model_dump()


@router.post("/agents/market/{agent_id}/install")
async def install_market_agent(
    agent_id: str,
    data: InstallRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """安装 Agent（从市场创建 Agent）"""
    try:
        agent = await agent_market_service.install_agent(
            db=db,
            agent_id=agent_id,
            user_id=current_user.id,
            name=data.name,
            config=data.config,
        )
        return {"message": "安装成功", "agent": AgentResponse.model_validate(agent).model_dump()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
