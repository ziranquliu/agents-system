"""
工作空间管理 API
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_workspaces():
    """获取工作空间列表 (占位)"""
    return {"workspaces": []}


@router.post("/")
async def create_workspace():
    """创建工作空间 (占位)"""
    return {"message": "待实现"}
