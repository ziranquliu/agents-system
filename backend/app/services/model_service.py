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
                ModelConfigTemplate.model_name.ilike(f"%{search}%"),
            )
        )
    if created_by:
        query = query.where(ModelConfigTemplate.created_by == created_by)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(ModelConfigTemplate.is_default.desc(), ModelConfigTemplate.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    templates = list(result.scalars().all())
    return templates, total


async def get_template(db: AsyncSession, template_id: str) -> Optional[ModelConfigTemplate]:
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
        model_name=data.model_name,
        endpoint=data.endpoint or "",
        api_key=data.api_key or "",
        temperature=data.temperature,
        max_tokens=data.max_tokens,
        context_window=data.context_window,
        embedding_model=data.embedding_model,
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
    for field, value in update_data.items():
        # api_key 如果为空字符串则不覆盖
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

    config = {
        "provider": template.provider,
        "endpoint": template.endpoint,
        "api_key": template.api_key,
        "model_name": template.model_name,
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
