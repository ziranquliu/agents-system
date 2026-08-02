#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复所有 API 文件的导入问题"""
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent
API_DIR = BASE_DIR / "app" / "api" / "v1"

def fix_agents_py():
    """修复 agents.py"""
    filepath = API_DIR / "agents.py"
    
    content = '''"""
Agent 管理 API - 完整 CRUD + 状态管理
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.models.user import User
from app.schemas.agent import (
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    AgentListResponse,
    AgentStatusUpdate,
)
from app.services.auth_service import get_current_user
from app.services import agent_service

router = APIRouter()


@router.get("/", response_model=AgentListResponse)
async def list_agents(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: str = Query(None, description="按状态筛选"),
    search: str = Query(None, description="搜索关键词"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 Agent 列表（分页 + 筛选）"""
    agents, total = await agent_service.list_agents(
        db=db,
        page=page,
        page_size=page_size,
        status=status,
        search=search,
        created_by=current_user.id,
    )
    return AgentListResponse(
        items=[AgentResponse.model_validate(a) for a in agents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=AgentResponse, status_code=201)
async def create_agent(
    data: AgentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建新的 Agent"""
    if not data.workspace_id:
        data.workspace_id = f"default_{current_user.id}"

    agent = await agent_service.create_agent(db, data, current_user.id)
    return AgentResponse.model_validate(agent)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 Agent 详情"""
    agent = await agent_service.get_agent(db, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse.model_validate(agent)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    data: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新 Agent 配置"""
    agent = await agent_service.update_agent(db, agent_id, data)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse.model_validate(agent)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除 Agent"""
    success = await agent_service.delete_agent(db, agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")
    return None


@router.patch("/{agent_id}/status", response_model=AgentResponse)
async def update_agent_status(
    agent_id: str,
    data: AgentStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """变更 Agent 状态（draft/running/stopped/error/archived）"""
    try:
        agent = await agent_service.update_agent_status(db, agent_id, data.status)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return AgentResponse.model_validate(agent)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
'''
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"[OK] Fixed: agents.py")

def main():
    print("=" * 70)
    print("Fixing API Files - agents.py")
    print("=" * 70)
    
    fix_agents_py()
    
    # 验证
    import ast
    filepath = API_DIR / "agents.py"
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            ast.parse(f.read())
        print(f"[OK] Syntax check passed for agents.py")
    except SyntaxError as e:
        print(f"[ERROR] Syntax error in agents.py: {e}")

if __name__ == "__main__":
    main()
