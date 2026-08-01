"""
模型模板版本管理服务
负责版本历史管理、回滚、绑定同步等核心逻辑
"""
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from app.models.agent import ModelConfigTemplate
from app.models.model_template import ModelTemplateVersion, ModelTemplateBinding
from app.schemas.model import (
    ModelConfigCreate,
    ModelConfigUpdate,
)
from app.schemas.model_version import (
    ModelVersionResponse,
    ModelBindingResponse,
)


class ModelVersionService:
    """模型模板版本管理服务"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def list_versions(
        self, 
        template_id: str, 
        page: int = 1, 
        page_size: int = 20
    ) -> tuple[List[ModelTemplateVersion], int]:
        """获取模板版本历史列表"""
        # 验证模板存在
        template = await self._get_template(template_id)
        if not template:
            raise ValueError(f"模板 {template_id} 不存在")
        
        # 查询版本列表
        query = select(ModelTemplateVersion).where(
            ModelTemplateVersion.template_id == template_id
        ).order_by(
            ModelTemplateVersion.version.desc()
        )
        
        # 分页
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        # 总数查询
        count_query = select(func.count()).select_from(
            ModelTemplateVersion.where(ModelTemplateVersion.template_id == template_id)
        )
        
        versions = (await self.db.execute(query)).scalars().all()
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        
        return list(versions), total
    
    async def get_version(
        self, 
        template_id: str, 
        version: int
    ) -> Optional[ModelTemplateVersion]:
        """获取指定版本的详情"""
        result = await self.db.execute(
            select(ModelTemplateVersion).where(
                and_(
                    ModelTemplateVersion.template_id == template_id,
                    ModelTemplateVersion.version == version
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def create_version(
        self,
        template: ModelConfigTemplate,
        change_log: str = "",
        user_id: str = None
    ) -> ModelTemplateVersion:
        """创建新版本（在更新配置时调用）"""
        # 获取当前最大版本号
        max_version_result = await self.db.execute(
            select(func.max(ModelTemplateVersion.version)).where(
                ModelTemplateVersion.template_id == template.id
            )
        )
        max_version = max_version_result.scalar() or 0
        new_version = max_version + 1
        
        # 创建版本快照
        version_record = ModelTemplateVersion(
            id=f"version_{template.id}_{new_version}",
            template_id = template.id,
            version = new_version,
            name=template.name,
            provider=template.provider,
            model=template.model,
            config=template.config or "{}",
            description=template.description,
            change_log=change_log,
            created_by=user_id,
            created_at=datetime.utcnow()
        )
        
        self.db.add(version_record)
        await self.db.flush()
        
        return version_record
    
    async def rollback_to_version(
        self,
        template_id: str,
        target_version: int,
        user_id: str = None
    ) -> Dict[str, Any]:
        """回滚到指定版本"""
        # 获取目标版本
        target_version_record = await self.get_version(template_id, target_version)
        if not target_version_record:
            raise ValueError(f"版本 {target_version} 不存在")
        
        # 获取当前模板
        template = await self._get_template(template_id)
        if not template:
            raise ValueError(f"模板 {template_id} 不存在")
        
        # 保存当前状态作为新版本
        current_config = template.config or "{}"
        await self.create_version(
            template=template,
            change_log=f"自动保存：回滚至v{target_version}前的状态",
            user_id=user_id
        )
        
        # 应用目标版本的配置
        template.config = target_version_record.config
        template.updated_at = datetime.utcnow()
        
        await self.db.flush()
        
        # 通知绑定的Agent需要同步
        await self._notify_binding_agents_sync(template_id)
        
        return {
            "success": True,
            "rolled_back_to": target_version,
            "previous_version": target_version + 1,
            "message": f"已成功回滚到版本 {target_version}"
        }
    
    async def get_bound_agents(
        self,
        template_id: str,
        status_filter: Optional[str] = None
    ) -> List[ModelTemplateBinding]:
        """获取绑定到该模板的Agent列表"""
        query = select(ModelTemplateBinding).where(
            ModelTemplateBinding.template_id == template_id
        ).options(
            selectinload(ModelTemplateBinding.agent)
        )
        
        if status_filter:
            query = query.where(ModelTemplateBinding.binding_status == status_filter)
        
        query = query.order_by(ModelTemplateBinding.created_at.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def trigger_sync(
        self,
        template_id: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """触发模板同步到所有绑定的Agent"""
        # 获取模板
        template = await self._get_template(template_id)
        if not template:
            raise ValueError(f"模板 {template_id} 不存在")
        
        # 获取所有绑定
        bindings = await self.get_bound_agents(template_id)
        
        sync_results = []
        for binding in bindings:
            result = await self._sync_agent_with_template(binding, force=force)
            sync_results.append({
                "agent_id": binding.agent_id,
                "status": result["status"],
                "error": result.get("error")
            })
        
        return {
            "template_id": template_id,
            "total": len(bindings),
            "synced": sum(1 for r in sync_results if r["status"] == "synced"),
            "failed": sum(1 for r in sync_results if r["status"] == "failed"),
            "results": sync_results
        }
    
    async def _sync_agent_with_template(
        self,
        binding: ModelTemplateBinding,
        force: bool = False
    ) -> Dict[str, Any]:
        """将单个Agent与模板同步"""
        try:
            # 获取模板最新配置
            template = await self._get_template(binding.template_id)
            if not template:
                return {"status": "failed", "error": "模板不存在"}
            
            # 检查是否需要同步
            if not force and binding.binding_status == "synced":
                # 检查是否有新binding或override变更
                pass
            
            # 更新Agent的模型配置
            agent = await self._get_agent(binding.agent_id)
            if not agent:
                return {"status": "failed", "error": "Agent不存在"}
            
            # 应用覆盖参数
            override_config = json.loads(binding.override_config or "{}")
            template_config = json.loads(template.config or "{}")
            
            # 合并配置：override优先
            merged_config = {**template_config, **override_config}
            
            # 更新Agent
            agent.temperature = merged_config.get("temperature", agent.temperature)
            agent.max_tokens = merged_config.get("max_tokens", agent.max_tokens)
            agent.context_window = merged_config.get("context_window", agent.context_window)
            
            # 更新binding状态
            binding.binding_status = "synced"
            binding.last_synced_at = datetime.utcnow()
            binding.gray_status = "synced"
            
            await self.db.flush()
            
            return {"status": "synced"}
            
        except Exception as e:
            binding.binding_status = "failed"
            binding.gray_status = "failed"
            binding.gray_error = str(e)
            await self.db.flush()
            return {"status": "failed", "error": str(e)}
    
    async def _notify_binding_agents_sync(self, template_id: str):
        """通知绑定的Agent需要同步"""
        # TODO: 实现消息队列通知机制
        pass
    
    async def _get_template(self, template_id: str) -> Optional[ModelConfigTemplate]:
        """获取模板"""
        result = await self.db.execute(
            select(ModelConfigTemplate).where(ModelConfigTemplate.id == template_id)
        )
        return result.scalar_one_or_none()
    
    async def _get_agent(self, agent_id: str) -> Optional[Any]:
        """获取Agent"""
        from app.models.agent import Agent
        result = await self.db.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        return result.scalar_one_or_none()
