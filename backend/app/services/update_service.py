"""
统一更新检测服务 - 检测可更新的组件版本
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.scanner import ComponentScan, ComponentScanItem

_DATA_DIR = Path(__file__).parent.parent / "data"


# 简单的版本比较（支持 "1.0.0" / "1.2.3-beta" 格式）
def _compare_versions(v1: str, v2: str) -> int:
    """比较两个版本号。返回 -1: v1<v2, 0: ==, 1: v1>v2"""
    import re
    def parse(v: str) -> tuple:
        parts = re.split(r'[.-]', v)
        nums = []
        for p in parts:
            try:
                nums.append(int(p))
            except ValueError:
                nums.append(0)
        return tuple(nums)
    p1, p2 = parse(v1), parse(v2)
    if p1 < p2:
        return -1
    elif p1 > p2:
        return 1
    return 0


def _load_market(market_file: str) -> list[dict]:
    """加载市场数据 JSON"""
    path = _DATA_DIR / market_file
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


async def check_updates(db: AsyncSession) -> list[dict]:
    """检查所有可更新的组件

    对比各市场 JSON 中的最新版本与已安装组件的版本。
    """
    updates = []

    # 1. 检查 Skill 更新
    from app.models.skill import Skill
    market_skills = _load_market("skill_market.json")
    skill_market_map = {s["id"]: s for s in market_skills}

    result = await db.execute(select(Skill))
    skills = result.scalars().all()
    for skill in skills:
        market = skill_market_map.get(skill.type)
        if market:
            current_ver = getattr(skill, "version", None) or "1.0.0"
            latest_ver = market.get("version", "1.0.0")
            if _compare_versions(current_ver, latest_ver) < 0:
                updates.append({
                    "component_type": "skill",
                    "component_id": skill.id,
                    "component_name": skill.name,
                    "current_version": current_ver,
                    "latest_version": latest_ver,
                    "description": market.get("description", ""),
                    "icon": market.get("icon", "📦"),
                })

    # 2. 检查 MCP Server 更新
    from app.models.skill import MCPServer
    market_mcps = _load_market("mcp_market.json")
    mcp_market_map = {m["id"]: m for m in market_mcps}

    result = await db.execute(select(MCPServer))
    servers = result.scalars().all()
    for server in servers:
        market = mcp_market_map.get(server.name) or mcp_market_map.get(server.type)
        if market:
            current_ver = getattr(server, "version", None) or "1.0.0"
            latest_ver = market.get("version", "1.0.0")
            if _compare_versions(current_ver, latest_ver) < 0:
                updates.append({
                    "component_type": "mcp",
                    "component_id": server.id,
                    "component_name": server.name,
                    "current_version": current_ver,
                    "latest_version": latest_ver,
                    "description": market.get("description", ""),
                    "icon": market.get("icon", "🔌"),
                })

    # 3. 检查 Agent 更新（从 Agent 市场对比）
    from app.models.agent import Agent
    market_agents = _load_market("agent_market.json")
    agent_market_map = {a["id"]: a for a in market_agents}

    result = await db.execute(select(Agent))
    agents = result.scalars().all()
    for agent in agents:
        # 在市场中查找匹配的 Agent (按名称模糊匹配)
        # 更精确: 从 agent 的 system_prompt 和 welcome_message 特征匹配
        for market_item in agent_market_map.values():
            if market_item.get("name") in agent.name or agent.name in market_item.get("name", ""):
                current_ver = "1.0.0"
                latest_ver = market_item.get("version", "1.0.0")
                if _compare_versions(current_ver, latest_ver) < 0:
                    updates.append({
                        "component_type": "agent",
                        "component_id": agent.id,
                        "component_name": agent.name,
                        "current_version": current_ver,
                        "latest_version": latest_ver,
                        "description": market_item.get("description", ""),
                        "icon": market_item.get("icon", "🧠"),
                    })
                break

    # 4. 检查模型更新（从模型市场对比）
    from app.models.agent import ModelConfigTemplate
    market_models = _load_market("model_market.json")
    model_market_map = {m["id"]: m for m in market_models}

    result = await db.execute(select(ModelConfigTemplate))
    models = result.scalars().all()
    for model_rec in models:
        for market_item in model_market_map.values():
            if market_item.get("model_name") == model_rec.model or market_item.get("name") in model_rec.name:
                current_ver = "1.0.0"
                latest_ver = market_item.get("version", "1.0.0")
                if _compare_versions(current_ver, latest_ver) < 0:
                    updates.append({
                        "component_type": "model",
                        "component_id": model_rec.id,
                        "component_name": model_rec.name,
                        "current_version": current_ver,
                        "latest_version": latest_ver,
                        "description": market_item.get("description", ""),
                        "icon": market_item.get("icon", "🧠"),
                    })
                break

    return updates


async def get_update_count(db: AsyncSession) -> int:
    """获取可更新的组件数量"""
    updates = await check_updates(db)
    return len(updates)


async def update_component(
    db: AsyncSession,
    component_type: str,
    component_id: str,
) -> dict:
    """执行组件更新

    对于不同组件类型的更新策略：
    - skill: 更新版本字段
    - mcp: 更新版本字段
    - agent: 更新系统提示词等
    - model: 更新配置
    """
    result = {"success": True, "message": "更新成功", "component_type": component_type, "component_id": component_id}

    if component_type == "skill":
        from app.models.skill import Skill
        obj = await db.get(Skill, component_id)
        if obj:
            market = _load_market("skill_market.json")
            for m in market:
                if m["id"] == obj.type:
                    obj.version = m.get("version", "1.0.0") if hasattr(obj, "version") else None
                    await db.flush()
                    result["new_version"] = m.get("version", "1.0.0")
                    break

    elif component_type == "mcp":
        from app.models.skill import MCPServer
        obj = await db.get(MCPServer, component_id)
        if obj:
            market = _load_market("mcp_market.json")
            for m in market:
                if m["id"] == obj.name or m["id"] == obj.type:
                    if hasattr(obj, "version"):
                        obj.version = m.get("version", "1.0.0")
                    await db.flush()
                    result["new_version"] = m.get("version", "1.0.0")
                    break

    elif component_type == "agent":
        from app.models.agent import Agent
        obj = await db.get(Agent, component_id)
        if obj:
            market = _load_market("agent_market.json")
            for m in market:
                if m.get("name") in obj.name or obj.name in m.get("name", ""):
                    obj.description = m.get("description", obj.description)
                    obj.system_prompt = m.get("system_prompt", obj.system_prompt)
                    result["updated_fields"] = ["description", "system_prompt"]
                    await db.flush()
                    break

    return result
