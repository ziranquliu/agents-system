"""
对话管理 API
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_conversations():
    """获取对话列表 (占位)"""
    return {"conversations": []}


@router.post("/")
async def create_conversation():
    """创建对话 (占位)"""
    return {"message": "待实现"}
