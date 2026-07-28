"""
模型配置模板 API
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.schemas.model import (
    ModelConfigCreate,
    ModelConfigUpdate,
    ModelConfigResponse,
    ModelTestRequest,
    ModelTestResponse,
)
from app.services.auth_service import get_current_user
from app.services import model_service

router = APIRouter()


def mask_api_key(api_key: str) -> str:
    """脱敏 API Key"""
    if not api_key:
        return None
    if len(api_key) <= 8:
        return api_key[:2] + "***" + api_key[-1:]
    return api_key[:4] + "***" + api_key[-4:]


def template_to_response(t) -> ModelConfigResponse:
    """ORM → Response，自动脱敏 API Key"""
    resp = ModelConfigResponse.model_validate(t)
    resp.api_key_masked = mask_api_key(t.api_key) if t.api_key else None
    return resp


@router.get("/", response_model=dict)
async def list_templates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    provider: str = Query(None),
    search: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取模型配置模板列表"""
    templates, total = await model_service.list_templates(
        db=db, page=page, page_size=page_size,
        provider=provider, search=search,
        created_by=current_user.id,
    )
    return {
        "items": [template_to_response(t) for t in templates],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/", response_model=ModelConfigResponse, status_code=201)
async def create_template(
    data: ModelConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建模型配置模板"""
    template = await model_service.create_template(db, data, current_user.id)
    return template_to_response(template)


@router.get("/{template_id}", response_model=ModelConfigResponse)
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取模板详情"""
    template = await model_service.get_template(db, template_id)
    if not template:
        raise HTTPException(404, detail="Model config template not found")
    return template_to_response(template)


@router.put("/{template_id}", response_model=ModelConfigResponse)
async def update_template(
    template_id: str,
    data: ModelConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新模板"""
    template = await model_service.update_template(db, template_id, data)
    if not template:
        raise HTTPException(404, detail="Model config template not found")
    return template_to_response(template)


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除模板"""
    success = await model_service.delete_template(db, template_id)
    if not success:
        raise HTTPException(404, detail="Model config template not found")
    return None


@router.post("/{template_id}/test", response_model=ModelTestResponse)
async def test_template(
    template_id: str,
    data: ModelTestRequest = ModelTestRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """测试模型连接"""
    result = await model_service.test_template_connection(db, template_id, data.messages)
    return ModelTestResponse(**result)
