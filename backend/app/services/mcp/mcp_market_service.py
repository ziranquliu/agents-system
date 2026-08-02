import json
import os
from typing import Optional, List
from app.db.session import async_session_factory as AsyncSessionLocal
from app.models.skill import MCPServer

"""MCP 在线市场服务"""


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
MARKET_FILE = os.path.join(DATA_DIR, "mcp_market.json")


def _load_market_data() -> List[dict]:
    """从 JSON 文件加载 MCP 市场数据"""
    if not os.path.exists(MARKET_FILE):
        return []
    with open(MARKET_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_market_data(data: List[dict]) -> None:
    """保存 MCP 市场数据到 JSON（更新安装量、评分）"""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MARKET_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def list_market_items(
    page: int = 1,
    page_size: int = 20,
    category: Optional[str] = None,
    search: Optional[str] = None,
) -> dict:
    """分页列出市场中的 MCP 服务"""
    items = _load_market_data()

    # 筛选
    if category:
        items = [i for i in items if i["category"] == category]
    if search:
        q = search.lower()
        items = [i for i in items if q in i["name"].lower() or q in i["description"].lower() or q in i["tags"]]

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": page_items,
    }


async def list_categories() -> list:
    """获取所有分类列表"""
    items = _load_market_data()
    cats = sorted(set(i["category"] for i in items))
    return cats


async def get_market_item(item_id: str) -> Optional[dict]:
    """获取 MCP 市场项详情"""
    items = _load_market_data()
    for item in items:
        if item["id"] == item_id:
            return item
    return None


async def install_market_item(
# TODO: Consider splitting this function into smaller sub-functions
    user_id: str,
    item_id: str,
    name_override: Optional[str] = None,
    config_override: Optional[dict] = None,
) -> dict:
    """从市场安装 MCP 服务：创建对应的 MCPServer 记录"""
    item = await get_market_item(item_id)
    if not item:
        raise ValueError(f"市场项 {item_id} 不存在")

    # 构建 MCP Server 配置
    name = name_override or item["name"]
    config = config_override or {}
    # 合并 config_schema 的默认值
    schema = item.get("config_schema", {})
    props = schema.get("properties", {})
    for key, prop in props.items():
        if key not in config and "default" in prop:
            config[key] = prop["default"]

    # 创建 MCPServer 记录
    async with AsyncSessionLocal() as db:
        mcp = MCPServer(
            name=name,
            url=item.get("endpoint_template", ""),
            protocol=item.get("protocol", "stdio"),
            status="inactive",
            description=item.get("description", ""),
            config=config,
        )
        db.add(mcp)
        await db.commit()
        await db.refresh(mcp)

        # 更新安装量
        data = _load_market_data()
        for d in data:
            if d["id"] == item_id:
                d["install_count"] = (d.get("install_count", 0) or 0) + 1
                break
        _save_market_data(data)

        return {
            "id": mcp.id,
            "name": mcp.name,
            "url": mcp.url,
            "protocol": mcp.protocol,
            "status": mcp.status,
            "description": mcp.description,
            "config": mcp.config,
            "created_at": mcp.created_at.isoformat() if mcp.created_at else None,
        }
