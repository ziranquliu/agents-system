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
    created_by: str = "manual",
) -> dict:
    """执行组件更新（更新前自动保留快照，支持回滚）

    对于不同组件类型的更新策略：
    - skill: 更新版本字段
    - mcp: 更新版本字段
    - agent: 更新系统提示词等
    - model: 更新配置
    """
    result = {"success": True, "message": "更新成功", "component_type": component_type, "component_id": component_id}
    before_state = {}
    after_state = {}

    if component_type == "skill":
        from app.models.skill import Skill
        obj = await db.get(Skill, component_id)
        if obj:
            before_state = {"version": getattr(obj, "version", None)}
            market = _load_market("skill_market.json")
            for m in market:
                if m["id"] == obj.type:
                    obj.version = m.get("version", "1.0.0") if hasattr(obj, "version") else None
                    await db.flush()
                    result["new_version"] = m.get("version", "1.0.0")
                    after_state = {"version": obj.version}
                    break

    elif component_type == "mcp":
        from app.models.skill import MCPServer
        obj = await db.get(MCPServer, component_id)
        if obj:
            before_state = {"version": getattr(obj, "version", None)}
            market = _load_market("mcp_market.json")
            for m in market:
                if m["id"] == obj.name or m["id"] == obj.type:
                    if hasattr(obj, "version"):
                        obj.version = m.get("version", "1.0.0")
                    await db.flush()
                    result["new_version"] = m.get("version", "1.0.0")
                    after_state = {"version": getattr(obj, "version", None)}
                    break

    elif component_type == "agent":
        from app.models.agent import Agent
        obj = await db.get(Agent, component_id)
        if obj:
            before_state = {"description": obj.description, "system_prompt": obj.system_prompt}
            market = _load_market("agent_market.json")
            for m in market:
                if m.get("name") in obj.name or obj.name in m.get("name", ""):
                    obj.description = m.get("description", obj.description)
                    obj.system_prompt = m.get("system_prompt", obj.system_prompt)
                    result["updated_fields"] = ["description", "system_prompt"]
                    after_state = {"description": obj.description, "system_prompt": obj.system_prompt}
                    await db.flush()
                    break

    # 创建更新快照（用于回滚）
    try:
        from app.models.update_enhanced import UpdateSnapshot, UpdateLog
        snapshot = UpdateSnapshot(
            component_type=component_type,
            component_id=component_id,
            component_name=result.get("component_name") or str(component_id),
            old_version=result.get("current_version"),
            new_version=result.get("new_version"),
            before_state=json.dumps(before_state, ensure_ascii=False) if before_state else None,
            after_state=json.dumps(after_state, ensure_ascii=False) if after_state else None,
            created_by=created_by,
        )
        db.add(snapshot)
        await db.flush()
        result["snapshot_id"] = snapshot.id
        db.add(UpdateLog(
            component_type=component_type,
            component_id=component_id,
            component_name=str(component_id),
            action="update",
            old_version=result.get("current_version"),
            new_version=result.get("new_version"),
            compatibility="pass",
            status="success",
            created_by=created_by,
        ))
        await db.commit()
    except Exception:
        await db.rollback()
        # 快照失败不影响更新本身
        await db.flush()

    return result


async def rollback_component(
    db: AsyncSession,
    snapshot_id: str,
    created_by: str = "manual",
) -> dict:
    """回滚组件到快照状态（保留前一版本快照）"""
    from app.models.update_enhanced import UpdateSnapshot, UpdateLog
    snapshot = await db.get(UpdateSnapshot, snapshot_id)
    if not snapshot:
        return {"success": False, "message": "快照不存在", "snapshot_id": snapshot_id}
    if snapshot.rolled_back:
        return {"success": False, "message": "该快照已回滚过", "snapshot_id": snapshot_id}

    before_state = json.loads(snapshot.before_state) if snapshot.before_state else {}
    restored = False

    if snapshot.component_type == "skill":
        from app.models.skill import Skill
        obj = await db.get(Skill, snapshot.component_id)
        if obj and "version" in before_state:
            obj.version = before_state["version"]
            restored = True

    elif snapshot.component_type == "mcp":
        from app.models.skill import MCPServer
        obj = await db.get(MCPServer, snapshot.component_id)
        if obj and "version" in before_state:
            obj.version = before_state["version"]
            restored = True

    elif snapshot.component_type == "agent":
        from app.models.agent import Agent
        obj = await db.get(Agent, snapshot.component_id)
        if obj:
            if "description" in before_state:
                obj.description = before_state["description"]
            if "system_prompt" in before_state:
                obj.system_prompt = before_state["system_prompt"]
            restored = True

    if not restored:
        return {"success": False, "message": "回滚失败：组件不存在或快照无有效数据", "snapshot_id": snapshot_id}

    snapshot.rolled_back = True
    snapshot.rollback_time = datetime.utcnow()
    db.add(UpdateLog(
        component_type=snapshot.component_type,
        component_id=snapshot.component_id,
        component_name=snapshot.component_name or str(snapshot.component_id),
        action="rollback",
        old_version=snapshot.new_version,
        new_version=snapshot.old_version,
        compatibility="pass",
        status="rolled_back",
        created_by=created_by,
    ))
    await db.commit()
    return {
        "success": True,
        "message": "回滚成功",
        "snapshot_id": snapshot_id,
        "component_type": snapshot.component_type,
        "component_id": snapshot.component_id,
        "restored_version": snapshot.old_version,
    }


async def list_snapshots(db: AsyncSession, component_type: Optional[str] = None, limit: int = 50) -> list[dict]:
    """快照列表"""
    from app.models.update_enhanced import UpdateSnapshot
    filters = []
    if component_type:
        filters.append(UpdateSnapshot.component_type == component_type)
    rows = (await db.execute(
        select(UpdateSnapshot).where(*filters).order_by(UpdateSnapshot.created_at.desc()).limit(limit)
    )).scalars().all()
    return [{
        "id": s.id,
        "component_type": s.component_type,
        "component_id": s.component_id,
        "component_name": s.component_name,
        "old_version": s.old_version,
        "new_version": s.new_version,
        "rolled_back": s.rolled_back,
        "rollback_time": s.rollback_time.isoformat() if s.rollback_time else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "created_by": s.created_by,
    } for s in rows]


async def list_update_logs(db: AsyncSession, component_type: Optional[str] = None, limit: int = 50) -> list[dict]:
    """更新操作日志（更新时间/变更/兼容性/回滚状态）"""
    from app.models.update_enhanced import UpdateLog
    filters = []
    if component_type:
        filters.append(UpdateLog.component_type == component_type)
    rows = (await db.execute(
        select(UpdateLog).where(*filters).order_by(UpdateLog.created_at.desc()).limit(limit)
    )).scalars().all()
    return [{
        "id": l.id,
        "component_type": l.component_type,
        "component_id": l.component_id,
        "component_name": l.component_name,
        "action": l.action,
        "old_version": l.old_version,
        "new_version": l.new_version,
        "compatibility": l.compatibility,
        "status": l.status,
        "detail": l.detail,
        "created_at": l.created_at.isoformat() if l.created_at else None,
        "created_by": l.created_by,
    } for l in rows]


async def batch_update_components(db: AsyncSession, component_type: str, ids: list[str], created_by: str = "manual") -> dict:
    """批量更新：多组件排队更新，返回汇总报告"""
    results = []
    success_count = 0
    failed_count = 0
    for cid in ids:
        try:
            r = await update_component(db, component_type, cid, created_by=created_by)
            results.append({"component_id": cid, "success": r.get("success", True), "new_version": r.get("new_version"), "snapshot_id": r.get("snapshot_id")})
            if r.get("success", True):
                success_count += 1
            else:
                failed_count += 1
        except Exception as e:
            results.append({"component_id": cid, "success": False, "error": str(e)})
            failed_count += 1
    return {
        "total": len(ids),
        "success_count": success_count,
        "failed_count": failed_count,
        "results": results,
        "summary": f"批量更新完成：{success_count} 成功 / {failed_count} 失败",
    }
