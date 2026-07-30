"""
模型在线市场 API - 列表/分类/详情/安装（一键配置）
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services import model_market_service

router = APIRouter(tags=["模型在线市场"])


class MarketModelItem(BaseModel):
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
    provider: str
    model_name: str
    api_base: str | None = None
    features: list[str] | None = None
    pricing: dict | None = None
    context_window: int | None = None
    max_tokens: int | None = None
    config_schema: dict | None = None


class MarketModelDetail(MarketModelItem):
    pass


class MarketListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[MarketModelItem]


class CategoriesResponse(BaseModel):
    categories: list[str]


class InstallRequest(BaseModel):
    name: str | None = Field(None, description="自定义配置名称")
    config: dict | None = Field(None, description="自定义配置（如 api_key, temperature 等）")


class InstallResponse(BaseModel):
    message: str = "配置成功"
    model_id: str


@router.get("/models/market")
async def list_market_models(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    category: str | None = None,
    search: str | None = None,
):
    """获取模型市场列表"""
    items, total = await model_market_service.list_models(
        page=page, page_size=page_size, category=category, search=search,
    )
    return {
        "items": [MarketModelItem(**i).model_dump() for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/models/market/categories")
async def list_model_categories():
    """获取所有模型分类"""
    categories = await model_market_service.list_categories()
    return {"categories": categories}


@router.get("/models/market/{model_id}")
async def get_market_model(model_id: str):
    """获取模型详情"""
    item = await model_market_service.get_model_detail(model_id)
    if not item:
        raise HTTPException(status_code=404, detail="Model template not found")
    return MarketModelDetail(**item).model_dump()


@router.post("/models/market/{model_id}/install")
async def install_market_model(
    model_id: str,
    data: InstallRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """安装（配置）模型"""
    try:
        record = await model_market_service.install_model(
            db=db,
            model_id=model_id,
            user_id=current_user.id,
            workspace_id=f"default_{current_user.id}",
            name=data.name,
            config=data.config,
        )
        return {"message": "配置成功", "model_id": record.id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
