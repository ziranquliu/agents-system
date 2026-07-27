"""
模型管理 API
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_models():
    """获取模型列表 (占位)"""
    return {"models": []}


@router.post("/")
async def create_model():
    """添加模型配置 (占位)"""
    return {"message": "待实现"}
