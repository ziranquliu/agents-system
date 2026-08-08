"""
模型在线市场服务 - 列表/分类/详情/安装（一键配置）
"""
import json
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import ModelConfigTemplate
from app.core.encryption import encrypt_secret

_DATA_DIR = Path(__file__).parent.parent / "data"
_MARKET_FILE = _DATA_DIR / "model_market.json"


def _load_market_data() -> list[dict]:
    if not _MARKET_FILE.exists():
        return []
    with open(_MARKET_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


async def list_models(
    page: int = 1,
    page_size: int = 12,
    category: Optional[str] = None,
    search: Optional[str] = None,
) -> tuple[list[dict], int]:
    items = _load_market_data()
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
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], total


async def list_categories() -> list[str]:
    items = _load_market_data()
    return sorted(set(i.get("category", "") for i in items if i.get("category")))


async def get_model_detail(model_id: str) -> Optional[dict]:
    items = _load_market_data()
    for item in items:
        if item["id"] == model_id:
            return item
    return None


async def install_model(
    db: AsyncSession,
    model_id: str,
    user_id: str,
    workspace_id: str,
    name: Optional[str] = None,
    config: Optional[dict] = None,
) -> ModelConfigTemplate:
    """从市场安装（配置）模型

    读取预置数据，合并用户配置（如 API Key），创建 ModelConfigTemplate ORM 记录。
    """
    item = await get_model_detail(model_id)
    if not item:
        raise ValueError(f"Model template not found: {model_id}")

    merged = dict(config or {})
    model_name = name or merged.pop("name", None) or item["name"]

    # 提取配置项
    api_key = merged.pop("api_key", None)
    api_base = merged.pop("api_base", item.get("api_base"))
    temperature = merged.pop("temperature", item.get("temperature"))
    max_tokens = merged.pop("max_tokens", item.get("max_tokens"))
    context_window = merged.pop("context_window", item.get("context_window"))

    # 构建 config JSON
    config_json = {
        "endpoint": api_base or item.get("api_base"),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "context_window": context_window,
    }
    if api_key:
        config_json["api_key"] = encrypt_secret(api_key)

    # 更新安装计数
    _increment_install_count(model_id)

    record = ModelConfigTemplate(
        id=str(uuid.uuid4()),
        name=model_name,
        description=item.get("description"),
        provider=item.get("provider", "openai"),
        model=item.get("model_name", ""),
        config=json.dumps(config_json),
        is_default=False,
        workspace_id=workspace_id,
        created_by=user_id,
    )
    db.add(record)
    await db.flush()
    return record


def _increment_install_count(model_id: str) -> None:
    items = _load_market_data()
    for item in items:
        if item["id"] == model_id:
            item["install_count"] = item.get("install_count", 0) + 1
            break
    with open(_MARKET_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
