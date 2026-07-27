"""
Agent 管理 API
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_agents():
    """获取 Agent 列表 (占位)"""
    return {"agents": []}


@router.post("/")
async def create_agent():
    """创建 Agent (占位)"""
    return {"message": "待实现"}
