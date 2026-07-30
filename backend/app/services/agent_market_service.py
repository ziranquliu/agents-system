"""
Agent 在线市场服务 - 列表/分类/详情/安装
"""
import json
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent

_DATA_DIR = Path(__file__).parent.parent / "data"
_MARKET_FILE = _DATA_DIR / "agent_market.json"


def _load_market_data() -> list[dict]:
    """加载 Agent 市场预置数据"""
    if not _MARKET_FILE.exists():
        return []
    with open(_MARKET_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


async def list_agents(
    page: int = 1,
    page_size: int = 12,
    category: Optional[str] = None,
    search: Optional[str] = None,
) -> tuple[list[dict], int]:
    """获取 Agent 市场列表（分页 + 筛选）"""
    items = _load_market_data()

    # 筛选
    if category:
        items = [i for i in items if i.get("category") == category]
    if search:
        q = search.lower()
        items = [
            i for i in items
            if q in i.get("name", "").lower()
            or q in i.get("description", "").lower()
            or q in " ".join(i.get("tags", [])).lower()
        ]

    total = len(items)

    # 分页
    start = (page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]

    return page_items, total


async def list_categories() -> list[str]:
    """获取所有分类"""
    items = _load_market_data()
    cats = sorted(set(i.get("category", "") for i in items if i.get("category")))
    return cats


async def get_agent_detail(agent_id: str) -> Optional[dict]:
    """获取 Agent 详情"""
    items = _load_market_data()
    for item in items:
        if item["id"] == agent_id:
            return item
    return None


async def install_agent(
    db: AsyncSession,
    agent_id: str,
    user_id: str,
    name: Optional[str] = None,
    config: Optional[dict] = None,
) -> Agent:
    """从市场安装 Agent

    从 JSON 数据中读取模板，合并用户配置后创建 Agent ORM 记录。
    """
    item = await get_agent_detail(agent_id)
    if not item:
        raise ValueError(f"Agent template not found: {agent_id}")

    # 合并用户配置
    merged_config = dict(config or {})

    # 使用用户提供的名称或默认名称或模板名称
    agent_name = name or merged_config.pop("name", None) or item["name"]

    temperature = merged_config.pop("temperature", item.get("temperature"))
    max_tokens = merged_config.pop("max_tokens", item.get("max_tokens"))
    context_window = merged_config.pop("context_window", item.get("context_window"))

    # 构建 Agent 数据
    agent = Agent(
        id=str(uuid.uuid4()),
        name=agent_name,
        description=item.get("description"),
        avatar=item.get("icon"),
        system_prompt=item.get("system_prompt"),
        welcome_message=merged_config.pop("welcome_message", item.get("welcome_message")),
        status="draft",
        model_provider=item.get("model_provider"),
        model_name=item.get("model_name"),
        temperature=temperature,
        max_tokens=max_tokens,
        context_window=context_window,
        enabled_skills=json.dumps(item.get("enabled_skills", [])) if item.get("enabled_skills") else None,
        enabled_mcp_servers=json.dumps(item.get("enabled_mcp_servers", [])) if item.get("enabled_mcp_servers") else None,
        workspace_id=f"default_{user_id}",
        created_by=user_id,
    )
    db.add(agent)
    await db.flush()

    # 更新安装计数
    _increment_install_count(agent_id)

    return agent


def _increment_install_count(agent_id: str) -> None:
    """增加安装计数（持久化到 JSON）"""
    items = _load_market_data()
    for item in items:
        if item["id"] == agent_id:
            item["install_count"] = item.get("install_count", 0) + 1
            break
    with open(_MARKET_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
