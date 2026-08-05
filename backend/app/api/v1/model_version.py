"""
模型模板版本管理 API
提供版本历史、回滚、绑定同步等功能
"""
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.db.session import get_db
from app.api.v1.auth import get_current_user
from app.models.model_template import ModelTemplateVersion, ModelTemplateBinding
from app.schemas.model_version import (
    ModelVersionResponse,
    RollbackRequest,
    SyncResult,
)
from app.services import model_service

router = APIRouter(tags=["模型版本管理"])


@router.get("/{template_id}/versions", response_model=dict)
async def list_versions(
    template_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取模板版本历史列表"""
    # 验证模板存在
    template = await model_service.get_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    # 查询版本列表
    query = select(ModelTemplateVersion).where(
        ModelTemplateVersion.template_id == template_id
    ).order_by(
        ModelTemplateVersion.version.desc()
    ).offset((page - 1) * page_size).limit(page_size)
    
    # 总数查询
    count_query = select(func.count()).select_from(
        ModelTemplateVersion.where(ModelTemplateVersion.template_id == template_id)
    )
    
    versions_result = await db.execute(query)
    count_result = await db.execute(count_query)
    
    versions = versions_result.scalars().all()
    total = count_result.scalar() or 0
    
    return {
        "items": [ModelVersionResponse.from_orm(v) for v in versions],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{template_id}/versions/{version}", response_model=ModelVersionResponse)
async def get_version(
    template_id: str,
    version: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取指定版本的详情"""
    result = await db.execute(
        select(ModelTemplateVersion).where(
            and_(
                ModelTemplateVersion.template_id == template_id,
                ModelTemplateVersion.version == version
            )
        )
    )
    version_record = result.scalar_one_or_none()
    
    if not version_record:
        raise HTTPException(
            status_code=404,
            detail=f"版本 {version} 不存在"
        )
    
    return ModelVersionResponse.from_orm(version_record)


@router.delete("/{template_id}/versions/{version}", response_model=dict)
async def delete_version(
    template_id: str,
    version: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """删除指定版本（不允许删除当前版本）"""
    # 验证模板存在
    template = await model_service.get_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    # 验证版本存在
    result = await db.execute(
        select(ModelTemplateVersion).where(
            and_(
                ModelTemplateVersion.template_id == template_id,
                ModelTemplateVersion.version == version
            )
        )
    )
    version_record = result.scalar_one_or_none()
    if not version_record:
        raise HTTPException(status_code=404, detail=f"版本 {version} 不存在")

    if version == template.version:
        raise HTTPException(status_code=400, detail="不允许删除当前版本")

    await db.delete(version_record)
    await db.commit()

    return {
        "success": True,
        "deleted_version": version,
        "message": f"版本 {version} 已删除",
    }


@router.post("/{template_id}/rollback", response_model=dict)
async def rollback_to_version(
    template_id: str,
    req: RollbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """回滚到指定版本"""
    # 验证模板存在
    template = await model_service.get_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    # 验证目标版本存在
    target_version_record = await db.execute(
        select(ModelTemplateVersion).where(
            and_(
                ModelTemplateVersion.template_id == template_id,
                ModelTemplateVersion.version == req.target_version
            )
        )
    )
    target = target_version_record.scalar_one_or_none()
    if not target:
        raise HTTPException(
            status_code=404,
            detail=f"版本 {req.target_version} 不存在"
        )
    
    # 验证目标版本小于当前版本
    if req.target_version >= template.version:
        raise HTTPException(
            status_code=400,
            detail="目标版本必须小于当前版本"
        )
    
    # 保存当前状态作为新版本（如果当前有未保存的变更）
    if template.config != target.config:
        # 创建新版本记录
        new_version = template.version + 1
        import uuid
        current_version = ModelTemplateVersion(
            id=str(uuid.uuid4()),
            template_id=template_id,
            version=new_version,
            name=template.name,
            provider=template.provider,
            model=template.model,
            config=template.config or "{}",
            description=template.description,
            change_log="自动保存：回滚至v{}前的状态".format(req.target_version),
            created_by=current_user.id,
            created_at=datetime.utcnow(),
        )
        db.add(current_version)
        await db.flush()
    
    # 应用目标版本的配置
    template.config = target.config
    template.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(template)
    
    # 通知绑定的Agent需要同步
    await _notify_binding_agents_sync(db, template_id)
    
    return {
        "success": True,
        "rolled_back_to": req.target_version,
        "current_version": template.version,
        "message": "已成功回滚到版本 {}".format(req.target_version)
    }


@router.get("/{template_id}/bound-agents", response_model=dict)
async def list_bound_agents(
    template_id: str,
    status_filter: Optional[str] = Query(None, description="按状态筛选: synced/outdated/pending/failed"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取绑定到该模板的Agent列表"""
    # 验证模板存在
    template = await model_service.get_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    from app.models.agent import Agent
    query = select(ModelTemplateBinding, Agent).join(
        Agent, ModelTemplateBinding.agent_id == Agent.id
    ).where(
        ModelTemplateBinding.template_id == template_id
    )
    
    if status_filter:
        query = query.where(ModelTemplateBinding.binding_status == status_filter)
    
    query = query.order_by(ModelTemplateBinding.created_at.desc())
    result = await db.execute(query)
    bindings = result.all()
    
    items = []
    for binding, agent in bindings:
        items.append({
            "id": binding.id,
            "template_id": binding.template_id,
            "agent_id": binding.agent_id,
            "sync_mode": binding.sync_mode,
            "override_config": binding.override_config,
            "override_model": binding.override_model,
            "override_provider": binding.override_provider,
            "gray_percentage": binding.gray_percentage,
            "gray_status": binding.gray_status,
            "last_synced_at": binding.last_synced_at,
            "created_at": binding.created_at,
            "updated_at": binding.updated_at,
            "agent_name": agent.name if agent else None,
            "agent_status": agent.status if agent else None,
            "binding_status": binding.binding_status,
        })
    
    return {
        "items": items,
        "total": len(items),
    }


@router.post("/{template_id}/sync", response_model=SyncResult)
async def trigger_sync(
    template_id: str,
    force: bool = Query(False, description="强制同步，忽略当前状态"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """触发模板同步到所有绑定的Agent"""
    # 验证模板存在
    template = await model_service.get_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    
    # 获取所有绑定
    result = await db.execute(
        select(ModelTemplateBinding).where(
            ModelTemplateBinding.template_id == template_id
        )
    )
    bindings = result.scalars().all()
    
    sync_results = []
    synced_count = 0
    failed_count = 0
    
    for binding in bindings:
        try:
            # 获取绑定的Agent
            from app.models.agent import Agent as AgentModel
            agent_query = await db.execute(
                select(AgentModel).where(AgentModel.id == binding.agent_id)
            )
            agent = agent_query.scalar_one_or_none()
            
            if not agent:
                sync_results.append({
                    "agent_id": binding.agent_id,
                    "status": "failed",
                    "error": "Agent不存在"
                })
                failed_count += 1
                continue
            
            # 合并配置
            import json
            try:
                template_config = json.loads(template.config or "{}")
            except (json.JSONDecodeError, TypeError):
                template_config = {}
            try:
                override_config = json.loads(binding.override_config or "{}")
            except (json.JSONDecodeError, TypeError):
                override_config = {}
            merged_config = {**template_config, **override_config}
            
            # 更新Agent
            if "temperature" in merged_config:
                agent.temperature = merged_config["temperature"]
            if "max_tokens" in merged_config:
                agent.max_tokens = merged_config["max_tokens"]
            if "context_window" in merged_config:
                agent.context_window = merged_config["context_window"]
            
            # 更新binding状态
            binding.binding_status = "synced"
            binding.last_synced_at = datetime.utcnow()
            binding.gray_status = "synced"
            binding.gray_error = None
            
            synced_count += 1
            sync_results.append({
                "agent_id": binding.agent_id,
                "status": "synced"
            })
            
        except Exception as e:
            logger.warning("Gray sync failed for agent %s: %s", binding.agent_id, e)
            binding.binding_status = "failed"
            binding.gray_status = "failed"
            binding.gray_error = "灰度同步失败"
            failed_count += 1
            sync_results.append({
                "agent_id": binding.agent_id,
                "status": "failed",
                "error": "灰度同步失败"
            })
    
    await db.commit()
    
    return SyncResult(
        template_id=template_id,
        total=len(bindings),
        synced=synced_count,
        failed=failed_count,
        results=sync_results
    )


async def _notify_binding_agents_sync(db: AsyncSession, template_id: str):
    """模板配置变更后标记所有绑定为outdated（Agent需重新同步）

    采用DB状态标记（A7：Redis事件总线为已知缺口，接入后可改为事件推送）
    """
    await db.execute(
        update(ModelTemplateBinding)
        .where(ModelTemplateBinding.template_id == template_id)
        .values(binding_status="outdated", updated_at=datetime.utcnow())
    )
    await db.commit()
