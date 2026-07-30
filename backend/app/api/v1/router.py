"""API v1 路由聚合"""
from fastapi import APIRouter
from app.api.v1 import auth, agents, models, chat, conversations, skills, workspaces, mcp_servers, discovery, operation_logs, users, mcp_market, skill_market, agent_market, model_market, scanner

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(agents.router, prefix="/agents", tags=["Agent管理"])
api_router.include_router(models.router, prefix="/models", tags=["模型配置"])
api_router.include_router(chat.router, prefix="/chat", tags=["对话补全"])
api_router.include_router(skills.router, prefix="/skills", tags=["Skill管理"])
api_router.include_router(mcp_servers.router, prefix="/mcp-servers", tags=["MCP Server管理"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["对话历史"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["工作区管理"])
api_router.include_router(discovery.router, prefix="/discover", tags=["Agent发现"])
api_router.include_router(operation_logs.router, prefix="/operation-logs", tags=["操作日志"])
api_router.include_router(users.router, prefix="/users", tags=["用户管理"])
api_router.include_router(mcp_market.router, prefix="/mcp/market", tags=["MCP 在线市场"])
api_router.include_router(skill_market.router, tags=["Skill 在线市场"])
api_router.include_router(agent_market.router, tags=["Agent 在线市场"])
api_router.include_router(model_market.router, tags=["模型在线市场"])
api_router.include_router(scanner.router, tags=["组件扫描器"])
