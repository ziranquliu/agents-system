"""
模型配置模板增强 API — 版本管理 / 绑定复用 / 灰度同步
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.auth_service import get_current_user
from app.services.model_template_service import ModelTemplateService

router = APIRouter(prefix="/api/v1/model-templates", tags=["模型配置模板"], dependencies=[Depends(get_current_user)])


def _safe_json(s, default=None):
    """安全解析 JSON 字符串，失败返回默认值"""
    if not s:
        return default or {}
    try:
        return json.loads(s) if isinstance(s, str) else s
    except (json.JSONDecodeError, TypeError):
        return default or {}


def _version_to_dict(v) -> dict:
    return {
        "id": v.id,
        "template_id": v.template_id,
        "version": v.version,
        "change_log": v.change_log,
        "name": v.name,
        "provider": v.provider,
        "model": v.model,
        "config": _safe_json(v.config),
        "description": v.description,
        "created_by": v.created_by,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }


def _binding_to_dict(b) -> dict:
    return {
        "id": b.id,
        "template_id": b.template_id,
        "agent_id": b.agent_id,
        "override_config": _safe_json(b.override_config),
        "override_model": b.override_model,
        "override_provider": b.override_provider,
        "sync_mode": b.sync_mode,
        "gray_percentage": b.gray_percentage,
        "gray_status": b.gray_status,
        "gray_synced_version": b.gray_synced_version,
        "gray_error": b.gray_error,
        "last_synced_at": b.last_synced_at.isoformat() if b.last_synced_at else None,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "updated_at": b.updated_at.isoformat() if b.updated_at else None,
    }


# ----------------------------------------------------------
# 版本管理
# ----------------------------------------------------------

@router.post("/{template_id}/versions", summary="创建版本快照")
async def create_version(template_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    svc = ModelTemplateService(db)
    try:
        version = await svc.create_version(template_id, data.get("change_log", ""), data.get("user_id", ""))
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"success": True, "data": _version_to_dict(version)}


@router.get("/{template_id}/versions", summary="版本列表")
async def list_versions(template_id: str, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                        db: AsyncSession = Depends(get_db)):
    svc = ModelTemplateService(db)
    items, total = await svc.list_versions(template_id, offset, limit)
    return {"success": True, "data": [_version_to_dict(v) for v in items], "total": total}


@router.post("/{template_id}/rollback", summary="回滚到指定版本")
async def rollback_version(template_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    svc = ModelTemplateService(db)
    template = await svc.rollback_to_version(template_id, data["version_id"], data.get("user_id", ""))
    if not template:
        raise HTTPException(404, "模板或版本不存在")
    return {"success": True, "message": f"已回滚到版本 {data['version_id']}"}


# ----------------------------------------------------------
# 绑定管理
# ----------------------------------------------------------

@router.post("/{template_id}/bindings", summary="绑定智能体到模板")
async def bind_agent(template_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    svc = ModelTemplateService(db)
    binding = await svc.bind_agent(
        template_id=template_id,
        agent_id=data["agent_id"],
        override_config=data.get("override_config"),
        sync_mode=data.get("sync_mode", "auto"),
        gray_percentage=data.get("gray_percentage", 100),
    )
    return {"success": True, "data": _binding_to_dict(binding)}


@router.delete("/{template_id}/bindings/{agent_id}", summary="解除绑定")
async def unbind_agent(template_id: str, agent_id: str, db: AsyncSession = Depends(get_db)):
    svc = ModelTemplateService(db)
    ok = await svc.unbind_agent(template_id, agent_id)
    if not ok:
        raise HTTPException(404, "绑定关系不存在")
    return {"success": True, "message": "已解除绑定"}


@router.get("/{template_id}/bindings", summary="查询模板的绑定列表")
async def list_bindings(template_id: str, status: Optional[str] = Query(None),
                        offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
                        db: AsyncSession = Depends(get_db)):
    svc = ModelTemplateService(db)
    items, total = await svc.list_bindings(template_id=template_id, status=status, offset=offset, limit=limit)
    return {"success": True, "data": [_binding_to_dict(b) for b in items], "total": total}


@router.put("/bindings/{binding_id}", summary="更新绑定配置")
async def update_binding(binding_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    svc = ModelTemplateService(db)
    binding = await svc.update_binding(binding_id, data)
    if not binding:
        raise HTTPException(404, "绑定不存在")
    return {"success": True, "data": _binding_to_dict(binding)}


# ----------------------------------------------------------
# 同步
# ----------------------------------------------------------

@router.post("/{template_id}/sync", summary="同步模板配置到绑定的智能体")
async def sync_template(template_id: str, data: dict = {}, db: AsyncSession = Depends(get_db)):
    svc = ModelTemplateService(db)
    result = await svc.sync_template_to_agents(template_id, force_all=data.get("force_all", False))
    return {"success": True, "data": result}


@router.post("/{template_id}/rollback-bindings", summary="回滚所有绑定的配置到历史版本")
async def rollback_bindings(template_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    svc = ModelTemplateService(db)
    result = await svc.rollback_binding(template_id, data["target_version"])
    if "error" in result:
        raise HTTPException(404, result["error"])
    return {"success": True, "data": result}


# ----------------------------------------------------------
# 综合查询
# ----------------------------------------------------------

@router.get("/{template_id}/detail", summary="获取模板详情（含绑定和版本信息）")
async def get_template_detail(template_id: str, db: AsyncSession = Depends(get_db)):
    svc = ModelTemplateService(db)
    detail = await svc.get_template_with_bindings(template_id)
    if not detail:
        raise HTTPException(404, "模板不存在")
    return {"success": True, "data": detail}