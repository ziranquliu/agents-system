"""
API v1 路由聚合
"""
from fastapi import APIRouter
from app.api.v1 import auth, agents, models, chat

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(agents.router, prefix="/agents", tags=["Agent管理"])
api_router.include_router(models.router, prefix="/models", tags=["模型配置"])
api_router.include_router(chat.router, prefix="/chat", tags=["对话补全"])
