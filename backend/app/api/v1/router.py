"""
API v1 路由注册
"""
from fastapi import APIRouter

from app.api.v1 import auth, agents, conversations, models, workspaces

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(agents.router, prefix="/agents", tags=["Agent Management"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["Conversation Management"])
api_router.include_router(models.router, prefix="/models", tags=["Model Management"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["Workspace Management"])
