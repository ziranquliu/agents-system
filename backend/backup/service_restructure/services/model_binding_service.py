"""
模型模板服务增强 - 自动绑定同步触发
"""
import json
from typing import Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.agent import ModelConfigTemplate, Agent
from app.models.model_template import ModelTemplateVersion, ModelTemplateBinding


async def trigger_auto_sync(
# TODO: Consider splitting this function into smaller sub-functions
    db: AsyncSession,
    template_id: str,
    user_id: Optional[str] = None
) -> dict:
    """
    当模板更新时，自动触发绑定Agent的同步
    
    Args:
        db: 数据库会话
        template_id: 模板ID
        user_id: 操作用户ID（用于审计）
    
    Returns:
        同步结果统计
    """
    # 获取模板
    result = await db.execute(
        select(ModelConfigTemplate).where(ModelConfigTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        return {"success": False, "error": "模板不存在"}
    
    # 保存新版本记录
    max_version_result = await db.execute(
        select(ModelTemplateVersion.version)
        .where(ModelTemplateVersion.template_id == template_id)
        .order_by(ModelTemplateVersion.version.desc())
        .limit(1)
    )
    max_version = max_version_result.scalar() or 0
    
    new_version = ModelTemplateVersion(
        id=f"version_{template_id}_{max_version + 1}",
        template_id=template_id,
        version=max_version + 1,
        name=template.name,
        provider=template.provider,
        model=template.model,
        config=template.config or "{}",
        description=template.description,
        change_log=f"自动保存：模板更新触发版本 {max_version + 1}",
        created_by=user_id,
        created_at=datetime.utcnow(),
    )
    db.add(new_version)
    await db.flush()
    
    # 查询所有绑定此模板的Agent
    bindings_result = await db.execute(
        select(ModelTemplateBinding).where(
            ModelTemplateBinding.template_id == template_id
        )
    )
    bindings = bindings_result.scalars().all()
    
    synced_count = 0
    failed_count = 0
    pending_count = 0
    
    for binding in bindings:
        if binding.sync_mode == "manual":
            binding.binding_status = "outdated"
            pending_count += 1
            continue
        
        # 获取绑定的Agent
        agent_result = await db.execute(
            select(Agent).where(Agent.id == binding.agent_id)
        )
        agent = agent_result.scalar_one_or_none()
        
        if not agent:
            binding.binding_status = "failed"
            binding.gray_status = "failed"
            binding.gray_error = "Agent不存在"
            failed_count += 1
            continue
        
        try:
            # 合并配置
            template_config = json.loads(template.config or "{}")
            override_config = json.loads(binding.override_config or "{}")
            merged_config = {**template_config, **override_config}
            
            # 更新Agent参数
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
            
        except Exception as e:
            binding.binding_status = "failed"
            binding.gray_status = "failed"
            binding.gray_error = str(e)
            failed_count += 1
    
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    
    return {
        "success": True,
        "template_id": template_id,
        "new_version": max_version + 1,
        "total_bindings": len(bindings),
        "synced": synced_count,
        "failed": failed_count,
        "pending_manual": pending_count,
    }


async def create_binding(
# TODO: Consider splitting this function into smaller sub-functions
    db: AsyncSession,
    template_id: str,
    agent_id: str,
    sync_mode: str = "auto",
    override_config: Optional[dict] = None,
) -> ModelTemplateBinding:
    """创建Agent与模板的绑定关系"""
    # 验证模板存在
    template_result = await db.execute(
        select(ModelConfigTemplate).where(ModelConfigTemplate.id == template_id)
    )
    template = template_result.scalar_one_or_none()
    if not template:
        raise ValueError(f"模板 {template_id} 不存在")
    
    # 验证Agent存在
    agent_result = await db.execute(
        select(Agent).where(Agent.id == agent_id)
    )
    agent = agent_result.scalar_one_or_none()
    if not agent:
        raise ValueError(f"Agent {agent_id} 不存在")
    
    # 检查是否已存在绑定
    existing = await db.execute(
        select(ModelTemplateBinding).where(
            ModelTemplateBinding.template_id == template_id,
            ModelTemplateBinding.agent_id == agent_id,
        )
    )
    existing_binding = existing.scalar_one_or_none()
    
    if existing_binding:
        # 更新现有绑定
        existing_binding.sync_mode = sync_mode
        if override_config:
            existing_binding.override_config = json.dumps(override_config)
        existing_binding.updated_at = datetime.utcnow()
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        await db.refresh(existing_binding)
        return existing_binding
    
    # 创建新绑定
    binding = ModelTemplateBinding(
        id=f"binding_{template_id}_{agent_id}",
        template_id=template_id,
        agent_id=agent_id,
        sync_mode=sync_mode,
        override_config=json.dumps(override_config) if override_config else None,
        binding_status="synced",
        gray_status="synced",
        gray_percentage=100,
        last_synced_at=datetime.utcnow(),
    )
    db.add(binding)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(binding)
    return binding


async def remove_binding(
    db: AsyncSession,
    template_id: str,
    agent_id: str,
) -> bool:
    """移除Agent与模板的绑定"""
    result = await db.execute(
        select(ModelTemplateBinding).where(
            ModelTemplateBinding.template_id == template_id,
            ModelTemplateBinding.agent_id == agent_id,
        )
    )
    binding = result.scalar_one_or_none()
    
    if not binding:
        return False
    
    await db.delete(binding)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return True
