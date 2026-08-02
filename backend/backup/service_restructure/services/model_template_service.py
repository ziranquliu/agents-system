"""
模型配置模板增强服务 - 版本管理、绑定复用、灰度同步
"""
import json
import math
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, func as sa_func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import ModelConfigTemplate
from app.models.model_template import ModelTemplateVersion, ModelTemplateBinding

from sqlalchemy.orm import selectinload, joinedload


class ModelTemplateService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ----------------------------------------------------------
    # 版本管理
    # ----------------------------------------------------------

    async def create_version(self, template_id: str, change_log: str = "",
                             user_id: str = "") -> ModelTemplateVersion:
        """基于当前模板创建新版本快照"""
        result = await self.db.execute(
            select(ModelConfigTemplate).where(ModelConfigTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        if not template:
            raise ValueError("模板不存在")

        # 计算下一个版本号
        r = await self.db.execute(
            select(sa_func.ifnull(sa_func.max(ModelTemplateVersion.version), 0))
            .where(ModelTemplateVersion.template_id == template_id)
        )
        next_version = (r.scalar() or 0) + 1

        version = ModelTemplateVersion(
            template_id=template_id,
            version=next_version,
            change_log=change_log or f"版本 {next_version}",
            name=template.name,
            provider=template.provider,
            model=template.model,
            config=template.config,
            description=template.description,
            created_by=user_id,
        )
        self.db.add(version)
        await self.db.flush()
        return version

    async def list_versions(self, template_id: str, offset: int = 0, limit: int = 20
                           ) -> tuple[list[ModelTemplateVersion], int]:
        """列出模板的所有版本"""
        q = select(ModelTemplateVersion).where(
            ModelTemplateVersion.template_id == template_id
        ).order_by(ModelTemplateVersion.version.desc())

        count_q = select(sa_func.count()).select_from(q.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0

        result = await self.db.execute(q.offset(offset).limit(limit))
        return list(result.scalars().all()), total

    async def get_version(self, version_id: str) -> Optional[ModelTemplateVersion]:
        result = await self.db.execute(
            select(ModelTemplateVersion).where(ModelTemplateVersion.id == version_id)
        )
        return result.scalar_one_or_none()

    async def rollback_to_version(self, template_id: str, version_id: str,
                                  user_id: str = "") -> Optional[ModelConfigTemplate]:
        """回滚模板到指定版本（创建新版本 + 恢复配置）"""
        version = await self.get_version(version_id)
        if not version or version.template_id != template_id:
            return None

        result = await self.db.execute(
            select(ModelConfigTemplate).where(ModelConfigTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        if not template:
            return None

        # 先保存当前状态作为新版本（回滚前的备份）
        await self.create_version(template_id,
                                  f"回滚前自动备份（版本 {version.version}）",
                                  user_id)

        # 恢复配置
        template.name = version.name
        template.provider = version.provider
        template.model = version.model
        template.config = version.config
        template.description = version.description

        await self.db.flush()

        # 创建回滚版本记录
        await self.create_version(template_id,
                                  f"回滚到版本 {version.version}",
                                  user_id)

        return template

    # ----------------------------------------------------------
    # 绑定管理
    # ----------------------------------------------------------

    async def bind_agent(self, template_id: str, agent_id: str,
                         override_config: Optional[dict] = None,
                         sync_mode: str = "auto",
                         gray_percentage: int = 100) -> ModelTemplateBinding:
        """绑定模板到智能体"""
        existing = await self.get_binding(template_id, agent_id)
        if existing:
            # 更新已有绑定
            existing.override_config = json.dumps(override_config or {}, ensure_ascii=False)
            existing.sync_mode = sync_mode
            existing.gray_percentage = gray_percentage
            await self.db.flush()
            return existing

        # 获取模板当前版本
        r = await self.db.execute(
            select(sa_func.max(ModelTemplateVersion.version))
            .where(ModelTemplateVersion.template_id == template_id)
        )
        current_ver = r.scalar() or 1

        binding = ModelTemplateBinding(
            template_id=template_id,
            agent_id=agent_id,
            override_config=json.dumps(override_config or {}, ensure_ascii=False),
            override_model=None,
            override_provider=None,
            sync_mode=sync_mode,
            gray_percentage=gray_percentage,
            gray_status="synced",
            gray_synced_version=current_ver,
        )
        self.db.add(binding)
        await self.db.flush()
        return binding

    async def unbind_agent(self, template_id: str, agent_id: str) -> bool:
        """解除绑定"""
        from sqlalchemy import delete as sa_delete
        result = await self.db.execute(
            sa_delete(ModelTemplateBinding).where(
                ModelTemplateBinding.template_id == template_id,
                ModelTemplateBinding.agent_id == agent_id,
            )
        )
        return result.rowcount > 0

    async def get_binding(self, template_id: str, agent_id: str
                         ) -> Optional[ModelTemplateBinding]:
        result = await self.db.execute(
            select(ModelTemplateBinding).where(
                ModelTemplateBinding.template_id == template_id,
                ModelTemplateBinding.agent_id == agent_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_bindings(self, template_id: Optional[str] = None,
                            agent_id: Optional[str] = None,
                            status: Optional[str] = None,
                            offset: int = 0, limit: int = 50
                           ) -> tuple[list[ModelTemplateBinding], int]:
        """查询绑定列表"""
        conditions = []
        if template_id:
            conditions.append(ModelTemplateBinding.template_id == template_id)
        if agent_id:
            conditions.append(ModelTemplateBinding.agent_id == agent_id)
        if status:
            conditions.append(ModelTemplateBinding.gray_status == status)

        where = and_(*conditions) if conditions else True

        count_q = select(sa_func.count()).select_from(ModelTemplateBinding).where(where)
        total = (await self.db.execute(count_q)).scalar() or 0

        result = await self.db.execute(
            select(ModelTemplateBinding).where(where)
            .order_by(ModelTemplateBinding.created_at.desc())
            .offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def update_binding(self, binding_id: str, data: dict[str, Any]
                            ) -> Optional[ModelTemplateBinding]:
        """更新绑定配置（覆盖参数）"""
        result = await self.db.execute(
            select(ModelTemplateBinding).where(ModelTemplateBinding.id == binding_id)
        )
        binding = result.scalar_one_or_none()
        if not binding:
            return None

        if "override_config" in data:
            binding.override_config = json.dumps(data["override_config"], ensure_ascii=False)
        if "sync_mode" in data:
            binding.sync_mode = data["sync_mode"]
        if "gray_percentage" in data:
            binding.gray_percentage = data["gray_percentage"]
        if "override_model" in data:
            binding.override_model = data["override_model"]
        if "override_provider" in data:
            binding.override_provider = data["override_provider"]

        await self.db.flush()
        return binding

    # ----------------------------------------------------------
    # 灰度同步
    # ----------------------------------------------------------

    async def sync_template_to_agents(self, template_id: str,
                                      force_all: bool = False
                                     ) -> dict[str, Any]:
        """
        将模板当前配置同步到所有绑定的智能体。
        灰度模式：根据 gray_percentage 随机决定是否同步。
        """
        result = await self.db.execute(
            select(ModelTemplateBinding).where(
                ModelTemplateBinding.template_id == template_id,
                ModelTemplateBinding.gray_status.in_(["synced", "pending", "failed"]),
            )
        )
        bindings = list(result.scalars().all())

        r = await self.db.execute(
            select(sa_func.max(ModelTemplateVersion.version))
            .where(ModelTemplateVersion.template_id == template_id)
        )
        current_version = r.scalar() or 1

        result = await self.db.execute(
            select(ModelConfigTemplate).where(ModelConfigTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        if not template:
            return {"synced": 0, "skipped": 0, "failed": 0, "error": "模板不存在"}

        synced = 0
        skipped = 0
        failed = 0

        for binding in bindings:
            # 灰度判定
            if not force_all and binding.sync_mode == "gray":
                if binding.gray_percentage < 100:
                    if random.randint(1, 100) > binding.gray_percentage:
                        skipped += 1
                        continue

            try:
                # 合并配置：模板配置 + 覆盖配置
                template_config = json.loads(template.config) if template.config else {}
                override_config = json.loads(binding.override_config) if binding.override_config else {}

                merged_config = {**template_config, **override_config}

                # 更新 Agent 的模型配置
                from app.models.agent import Agent
                agent_result = await self.db.execute(
                    select(Agent).where(Agent.id == binding.agent_id)
                )
                agent = agent_result.scalar_one_or_none()
                if agent:
                    agent.model_config_template_id = template_id
                    agent.model_provider = binding.override_provider or template.provider
                    agent.model_name = binding.override_model or template.model
                    agent.temperature = merged_config.get("temperature", agent.temperature)
                    agent.max_tokens = merged_config.get("max_tokens", agent.max_tokens)
                    agent.context_window = merged_config.get("context_window", agent.context_window)

                binding.gray_synced_version = current_version
                binding.gray_status = "synced"
                binding.last_synced_at = datetime.now(timezone.utc)
                binding.gray_error = None
                synced += 1
            except Exception as e:
                binding.gray_status = "failed"
                binding.gray_error = str(e)
                failed += 1

        await self.db.flush()
        return {"synced": synced, "skipped": skipped, "failed": failed}

    async def rollback_binding(self, template_id: str, target_version: int) -> dict[str, Any]:
        """将所有绑定的配置回滚到指定版本"""
        # 找到目标版本的快照
        r = await self.db.execute(
            select(ModelTemplateVersion).where(
                ModelTemplateVersion.template_id == template_id,
                ModelTemplateVersion.version == target_version,
            )
        )
        version = r.scalar_one_or_none()
        if not version:
            return {"error": f"版本 {target_version} 不存在"}

        # 先回滚模板本身
        template_result = await self.db.execute(
            select(ModelConfigTemplate).where(ModelConfigTemplate.id == template_id)
        )
        template = template_result.scalar_one_or_none()
        if template:
            template.config = version.config
            template.model = version.model
            template.provider = version.provider

        # 回滚所有绑定
        result = await self.db.execute(
            select(ModelTemplateBinding).where(
                ModelTemplateBinding.template_id == template_id,
            )
        )
        bindings = list(result.scalars().all())
        count = 0
        for binding in bindings:
            binding.gray_synced_version = target_version
            binding.gray_status = "synced"
            binding.gray_error = None
            count += 1

        await self.db.flush()
        return {"rolled_back": count, "target_version": target_version}

    # ----------------------------------------------------------
    # 查询辅助
    # ----------------------------------------------------------

    async def get_template_with_bindings(self, template_id: str) -> Optional[dict]:
        """获取模板详情并附带绑定信息"""
        result = await self.db.execute(
            select(ModelConfigTemplate).where(ModelConfigTemplate.id == template_id)
        )
        template = result.scalar_one_or_none()
        if not template:
            return None

        bindings, total = await self.list_bindings(template_id=template_id)
        r = await self.db.execute(
            select(sa_func.count()).select_from(ModelTemplateVersion)
            .where(ModelTemplateVersion.template_id == template_id)
        )
        version_count = r.scalar() or 0

        return {
            "id": template.id,
            "name": template.name,
            "provider": template.provider,
            "model": template.model,
            "config": json.loads(template.config) if template.config else {},
            "description": template.description,
            "is_default": template.is_default,
            "workspace_id": template.workspace_id,
            "created_by": template.created_by,
            "created_at": template.created_at.isoformat() if template.created_at else None,
            "updated_at": template.updated_at.isoformat() if template.updated_at else None,
            "binding_count": total,
            "version_count": version_count,
            "bindings": [
                {
                    "id": b.id,
                    "agent_id": b.agent_id,
                    "sync_mode": b.sync_mode,
                    "gray_percentage": b.gray_percentage,
                    "gray_status": b.gray_status,
                    "gray_synced_version": b.gray_synced_version,
                    "override_config": json.loads(b.override_config) if b.override_config else {},
                    "last_synced_at": b.last_synced_at.isoformat() if b.last_synced_at else None,
                }
                for b in bindings
            ],
        }
