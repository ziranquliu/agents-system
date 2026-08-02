"""
本地 Agent 发现与注册 API
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.db.session import get_db
from app.models.user import User
from app.schemas.agent import AgentResponse
from app.services import discovery_service
from app.services.auth_service import get_current_user

router = APIRouter(tags=["Agent发现"])


@router.post("/agents")
async def discover_agents(
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """扫描本地 AI 服务，发现可用的 Agent 模型"""
    agents = await discovery_service.discover_agents(db)
    return {
        "items": agents,
        "total": len(agents),
        "message": f"发现 {len(agents)} 个可用模型"
        if agents
        else "未发现本地运行的 AI 模型，请确认 Ollama 等服务已启动",
    }


@router.post("/agents/register")
async def register_discovered_agent(
    model_name: str = Query(..., description="模型名称"),
    provider: str = Query("ollama", description="模型提供商"),
    endpoint: str = Query("http://localhost:11434", description="API 端点地址"),
    workspace_id: str = Query("ws_personal", description="所属工作区"),
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """将发现的模型注册为 Agent"""
    agent = await discovery_service.register_discovered_agent(
        db=db,
        model_name=model_name,
        provider=provider,
        endpoint=endpoint,
        user_id=current_user.id,
        workspace_id=workspace_id,
    )
    return {
        "success": True,
        "agent": AgentResponse.model_validate(agent),
        "message": f"Agent '{agent.name}' 创建成功",
    }
