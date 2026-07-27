"""
API v1 路由注册 — 聚合所有子路由
"""
from fastapi import APIRouter

from app.api.v1 import auth, agents, conversations, models, workspaces

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["认证管理"])
api_router.include_router(agents.router, prefix="/agents", tags=["Agent 管理"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["对话管理"])
api_router.include_router(models.router, prefix="/models", tags=["模型管理"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["工作空间管理"])
