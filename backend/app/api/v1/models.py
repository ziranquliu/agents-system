"""
模型配置模板 API
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.db.session import get_db
from app.schemas.model import (
    ModelConfigCreate,
    ModelConfigResponse,
    ModelConfigUpdate,
    ModelTestRequest,
    ModelTestResponse,
)
from app.services import model_service
from app.api.v1.auth import get_current_user

router = APIRouter(tags=["模型配置"])


def _template_to_response(t) -> ModelConfigResponse:
    """ORM → Response Schema（含 config JSON 展开）"""
    cfg = {}
    if t.config:
        try:
            cfg = json.loads(t.config)
        except (json.JSONDecodeError, TypeError):
            cfg = {}

    api_key = cfg.get("api_key", "")
    if api_key and len(api_key) > 8:
        api_key_masked = api_key[:4] + "***" + api_key[-4:]
    elif api_key:
        api_key_masked = api_key[:2] + "***" + api_key[-1:] if len(api_key) > 2 else "***"
    else:
        api_key_masked = None

    return ModelConfigResponse(
        id=t.id,
        name=t.name,
        provider=t.provider,
        model_name=t.model,
        endpoint=cfg.get("endpoint", ""),
        api_key_masked=api_key_masked,
        temperature=cfg.get("temperature"),
        max_tokens=cfg.get("max_tokens"),
        context_window=cfg.get("context_window"),
        embedding_model=cfg.get("embedding_model"),
        is_default=t.is_default or False,
        description=t.description,
        created_by=t.created_by,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


@router.get("/", response_model=dict)
async def list_models(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    provider: Optional[str] = None,
    search: Optional[str] = None,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取模型配置模板列表"""
    templates, total = await model_service.list_templates(
        db, page=page, page_size=page_size,
        provider=provider, search=search,
    )
    return {
        "items": [_template_to_response(t) for t in templates],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{template_id}", response_model=ModelConfigResponse)
async def get_model(
    template_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取模板详情"""
    template = await model_service.get_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    return _template_to_response(template)


@router.post("/", response_model=ModelConfigResponse, status_code=201)
async def create_model(
    data: ModelConfigCreate,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """创建模板"""
    template = await model_service.create_template(db, data, current_user.id)
    return _template_to_response(template)


@router.put("/{template_id}", response_model=ModelConfigResponse)
async def update_model(
    template_id: str,
    data: ModelConfigUpdate,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """更新模板"""
    template = await model_service.update_template(db, template_id, data)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    return _template_to_response(template)


@router.delete("/{template_id}", status_code=204)
async def delete_model(
    template_id: str,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """删除模板"""
    ok = await model_service.delete_template(db, template_id)
    if not ok:
        raise HTTPException(status_code=404, detail="模板不存在")


@router.post("/{template_id}/test", response_model=ModelTestResponse)
async def test_model(
    template_id: str,
    req: ModelTestRequest,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """测试模型连接"""
    result = await model_service.test_template_connection(
        db, template_id, req.messages
    )
    return result
