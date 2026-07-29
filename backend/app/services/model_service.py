"""
模型配置模板服务
"""
import json
import time
import uuid
from typing import Optional

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import ModelConfigTemplate
from app.schemas.model import ModelConfigCreate, ModelConfigUpdate
from app.services.llm import create_adapter


# ── 辅助: config JSON ↔ 字段映射 ──────────────────────────────

CONFIG_FIELDS = [
    "endpoint", "api_key", "temperature",
    "max_tokens", "context_window", "embedding_model",
]


def _config_to_dict(template: ModelConfigTemplate) -> dict:
    """将 ORM 的 model/config 字段展开为完整 dict（供 response 使用）"""
    cfg = {}
    if template.config:
        try:
            cfg = json.loads(template.config)
        except (json.JSONDecodeError, TypeError):
            cfg = {}
    return {
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "provider": template.provider,
        "model_name": template.model,  # ORM 字段名叫 model，schema 叫 model_name
        "endpoint": cfg.get("endpoint", ""),
        "api_key_masked": _mask_api_key(cfg.get("api_key", "")),
        "temperature": cfg.get("temperature"),
        "max_tokens": cfg.get("max_tokens"),
        "context_window": cfg.get("context_window"),
        "embedding_model": cfg.get("embedding_model"),
        "is_default": template.is_default or False,
        "created_by": template.created_by,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }


def _mask_api_key(api_key: str) -> Optional[str]:
    """脱敏 API Key"""
    if not api_key:
        return None
    if len(api_key) <= 8:
        return api_key[:2] + "***" + api_key[-1:]
    return api_key[:4] + "***" + api_key[-4:]


def _build_config_json(data) -> str:
    """从 schema 中提取 config 字段并序列化为 JSON"""
    cfg = {}
    for field in CONFIG_FIELDS:
        val = getattr(data, field, None)
        if val is not None:
            cfg[field] = val
    return json.dumps(cfg, ensure_ascii=False)


# ── CRUD ──────────────────────────────────────────────────────

async def list_templates(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    provider: Optional[str] = None,
    search: Optional[str] = None,
    created_by: Optional[str] = None,
) -> tuple[list[ModelConfigTemplate], int]:
    """获取模型配置模板列表"""
    query = select(ModelConfigTemplate)

    if provider:
        query = query.where(ModelConfigTemplate.provider == provider)
    if search:
        query = query.where(
            or_(
                ModelConfigTemplate.name.ilike(f"%{search}%"),
                ModelConfigTemplate.model.ilike(f"%{search}%"),
            )
        )
    if created_by:
        query = query.where(ModelConfigTemplate.created_by == created_by)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(
        ModelConfigTemplate.is_default.desc(),
        ModelConfigTemplate.created_at.desc(),
    )
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    templates = list(result.scalars().all())
    return templates, total


async def get_template(
    db: AsyncSession, template_id: str
) -> Optional[ModelConfigTemplate]:
    """获取模板详情"""
    result = await db.execute(
        select(ModelConfigTemplate).where(ModelConfigTemplate.id == template_id)
    )
    return result.scalar_one_or_none()


async def create_template(
    db: AsyncSession,
    data: ModelConfigCreate,
    user_id: str,
) -> ModelConfigTemplate:
    """创建模板"""
    template = ModelConfigTemplate(
        id=str(uuid.uuid4()),
        name=data.name,
        provider=data.provider,
        model=data.model_name,  # schema → orm 字段名映射
        config=_build_config_json(data),
        is_default=data.is_default,
        description=data.description,
        created_by=user_id,
    )
    db.add(template)
    await db.flush()
    return template


async def update_template(
    db: AsyncSession,
    template_id: str,
    data: ModelConfigUpdate,
) -> Optional[ModelConfigTemplate]:
    """更新模板"""
    template = await get_template(db, template_id)
    if not template:
        return None

    update_data = data.model_dump(exclude_unset=True)

    # 处理直接字段映射
    if "model_name" in update_data:
        template.model = update_data.pop("model_name")

    # 处理 config JSON 字段
    config_dict = {}
    if template.config:
        try:
            config_dict = json.loads(template.config)
        except (json.JSONDecodeError, TypeError):
            config_dict = {}

    has_config_change = False
    for field in CONFIG_FIELDS:
        if field in update_data:
            config_dict[field] = update_data.pop(field)
            has_config_change = True

    if has_config_change:
        template.config = json.dumps(config_dict, ensure_ascii=False)

    # 剩余的直接字段
    for field, value in update_data.items():
        if field == "api_key" and not value:
            continue
        setattr(template, field, value)

    await db.flush()
    return template


async def delete_template(db: AsyncSession, template_id: str) -> bool:
    """删除模板"""
    template = await get_template(db, template_id)
    if not template:
        return False
    await db.delete(template)
    await db.flush()
    return True


async def test_template_connection(
    db: AsyncSession,
    template_id: str,
    test_messages: Optional[list[dict]] = None,
) -> dict:
    """测试模型连接"""
    template = await get_template(db, template_id)
    if not template:
        return {"success": False, "error": "Template not found"}

    config_dict = {}
    if template.config:
        try:
            config_dict = json.loads(template.config)
        except (json.JSONDecodeError, TypeError):
            pass

    config = {
        "provider": template.provider,
        "endpoint": config_dict.get("endpoint", ""),
        "api_key": config_dict.get("api_key", ""),
        "model_name": template.model,
    }

    try:
        adapter = create_adapter(template.provider, config)
        messages = test_messages or [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello in one sentence."},
        ]

        start = time.time()
        result = await adapter.chat(
            messages=messages,
            temperature=0.1,
            max_tokens=50,
        )
        latency = int((time.time() - start) * 1000)

        return {
            "success": True,
            "response": result.content,
            "model": result.model,
            "latency_ms": latency,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
