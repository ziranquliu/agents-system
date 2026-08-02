import json
import os
from typing import Optional, List
from app.db.session import async_session_factory as AsyncSessionLocal
from app.models.skill import Skill

"""Skill 在线市场服务"""


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
MARKET_FILE = os.path.join(DATA_DIR, "skill_market.json")


def _load_market_data() -> List[dict]:
    if not os.path.exists(MARKET_FILE):
        return []
    with open(MARKET_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_market_data(data: List[dict]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(MARKET_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def list_market_skills(
    page: int = 1,
    page_size: int = 20,
    category: Optional[str] = None,
    search: Optional[str] = None,
) -> dict:
    """分页列出技能市场"""
    items = _load_market_data()

    if category:
        items = [i for i in items if i["category"] == category]
    if search:
        q = search.lower()
        items = [
            i for i in items
            if q in i["name"].lower() or q in i["description"].lower()
        ]

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items[start:end],
    }


async def list_categories() -> list:
    """获取所有分类"""
    items = _load_market_data()
    return sorted(set(i["category"] for i in items))


async def get_market_skill(item_id: str) -> Optional[dict]:
    """获取技能市场项详情"""
    for item in _load_market_data():
        if item["id"] == item_id:
            return item
    return None


async def install_market_skill(user_id: str, item_id: str) -> dict:
    """从市场安装技能：创建 Skill 记录"""
    item = await get_market_skill(item_id)
    if not item:
        raise ValueError(f"技能 {item_id} 不存在")

    async with AsyncSessionLocal() as db:
        skill = Skill(
            name=item["name"],
            type=item.get("type", "tool"),
            version=item.get("version", "1.0.0"),
            category=item.get("category", ""),
            description=item.get("description", ""),
            enabled=True,
            status="active",
            config=item.get("config_schema", {}),
        )
        db.add(skill)
        await db.commit()
        await db.refresh(skill)

        # 更新安装量
        data = _load_market_data()
        for d in data:
            if d["id"] == item_id:
                d["install_count"] = (d.get("install_count", 0) or 0) + 1
                break
        _save_market_data(data)

        return {
            "id": skill.id,
            "name": skill.name,
            "type": skill.type,
            "version": skill.version,
            "category": skill.category,
            "description": skill.description,
            "enabled": skill.enabled,
            "status": skill.status,
            "created_at": skill.created_at.isoformat() if skill.created_at else None,
        }


async def rate_market_skill(user_id: str, item_id: str, rating: int) -> dict:
    """为技能市场项评分"""
    if not 1 <= rating <= 5:
        raise ValueError("评分必须在 1-5 之间")

    data = _load_market_data()
    for item in data:
        if item["id"] == item_id:
            old = item.get("rating", 0) or 0
            count = item.get("rating_count", 0) or 0
            new_rating = round((old * count + rating) / (count + 1), 1)
            item["rating"] = new_rating
            item["rating_count"] = count + 1
            _save_market_data(data)
            return {"rating": new_rating, "rating_count": count + 1}

    raise ValueError(f"技能 {item_id} 不存在")
