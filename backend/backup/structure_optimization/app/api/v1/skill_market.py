"""Skill 在线市场 API"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.models.user import User
from app.api.v1.auth import get_current_user
from app.services import skill_market_service

router = APIRouter(tags=["Skill 在线市场"])


class RateBody(BaseModel):
    rating: int


@router.get("/skills/market")
async def list_market_skills(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """列出 Skill 市场"""
    return await skill_market_service.list_market_skills(
        page=page, page_size=page_size, category=category, search=search
    )


@router.get("/skills/market/categories")
async def list_skill_categories(
    current_user: User = Depends(get_current_user),
):
    """获取 Skill 分类列表"""
    cats = await skill_market_service.list_categories()
    return {"categories": cats}


@router.get("/skills/market/{item_id}")
async def get_market_skill(
    item_id: str,
    current_user: User = Depends(get_current_user),
):
    """获取 Skill 市场详情"""
    item = await skill_market_service.get_market_skill(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    return item


@router.post("/skills/market/{item_id}/install")
async def install_market_skill(
    item_id: str,
    current_user: User = Depends(get_current_user),
):
    """安装 Skill 到当前用户"""
    try:
        result = await skill_market_service.install_market_skill(
            user_id=current_user.id, item_id=item_id
        )
        return {"message": "安装成功", "skill": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/skills/market/{item_id}/rating")
async def rate_market_skill(
    item_id: str,
    body: RateBody,
    current_user: User = Depends(get_current_user),
):
    """评分 Skill 市场项"""
    try:
        result = await skill_market_service.rate_market_skill(
            user_id=current_user.id, item_id=item_id, rating=body.rating
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
