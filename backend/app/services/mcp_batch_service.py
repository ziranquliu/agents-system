"""
MCP 批量安装与跨 Agent 同步服务
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, func as sa_func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import MCPServer
from app.models.mcp_batch import MCPAgentBinding, MCPBatchInstallQueue, MCPBatchInstallItem


class MCPBatchService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ----------------------------------------------------------
    # 批量安装
    # ----------------------------------------------------------

    async def create_batch_install(
        self,
        mcp_ids: list[str],
        agent_ids: list[str],
        sync_mode: str = "shared",
        created_by: str = "",
    ) -> MCPBatchInstallQueue:
        """创建 MCP 批量安装任务"""
        queue = MCPBatchInstallQueue(
            status="pending",
            total_items=len(mcp_ids) * len(agent_ids),
            created_by=created_by,
        )
        self.db.add(queue)
        await self.db.flush()

        for mcp_id in mcp_ids:
            r = await self.db.execute(select(MCPServer).where(MCPServer.id == mcp_id))
            mcp = r.scalar_one_or_none()
            mcp_name = mcp.name if mcp else mcp_id[:8]

            for agent_id in agent_ids:
                item = MCPBatchInstallItem(
                    queue_id=queue.id,
                    mcp_server_id=mcp_id,
                    mcp_server_name=mcp_name,
                    agent_id=agent_id,
                    sync_mode=sync_mode,
                    status="pending",
                )
                self.db.add(item)

        await self.db.flush()
        return queue

    async def execute_batch(self, queue_id: str) -> MCPBatchInstallQueue:
        """执行 MCP 批量安装"""
        r = await self.db.execute(
            select(MCPBatchInstallQueue).where(MCPBatchInstallQueue.id == queue_id)
        )
        queue = r.scalar_one_or_none()
        if not queue:
            raise ValueError("队列不存在")
        if queue.status != "pending":
            raise ValueError(f"队列状态异常: {queue.status}")

        queue.status = "running"
        await self.db.flush()

        r = await self.db.execute(
            select(MCPBatchInstallItem).where(MCPBatchInstallItem.queue_id == queue_id)
        )
        items = list(r.scalars().all())
        now = datetime.now(timezone.utc)

        for item in items:
            if item.status != "pending":
                continue

            item.status = "running"
            item.started_at = now
            await self.db.flush()

            try:
                await self._do_bind(
                    mcp_server_id=item.mcp_server_id,
                    agent_id=item.agent_id,
                    sync_mode=item.sync_mode,
                )
                item.status = "success"
                queue.success_count = (queue.success_count or 0) + 1
            except Exception as e:
                item.status = "failed"
                item.error_message = str(e)
                queue.fail_count = (queue.fail_count or 0) + 1

            item.completed_at = datetime.now(timezone.utc)
            await self.db.flush()

        queue.status = "completed"
        queue.completed_at = datetime.now(timezone.utc)
        await self.db.flush()
        return queue

    async def _do_bind(self, mcp_server_id: str, agent_id: str, sync_mode: str = "shared"):
        """绑定 MCP 到 Agent"""
        # 获取 MCP 配置
        r = await self.db.execute(select(MCPServer).where(MCPServer.id == mcp_server_id))
        mcp = r.scalar_one_or_none()
        if not mcp:
            raise ValueError("MCP Server 不存在")

        # 检查是否已有绑定
        r2 = await self.db.execute(
            select(MCPAgentBinding).where(
                MCPAgentBinding.mcp_server_id == mcp_server_id,
                MCPAgentBinding.agent_id == agent_id,
            )
        )
        existing = r2.scalar_one_or_none()
        if existing:
            existing.sync_mode = sync_mode
            existing.status = "active"
            existing.updated_at = datetime.now(timezone.utc)
            await self.db.flush()
            return

        # 创建绑定
        binding = MCPAgentBinding(
            mcp_server_id=mcp_server_id,
            mcp_server_name=mcp.name,
            agent_id=agent_id,
            agent_name=agent_id,
            sync_mode=sync_mode,
            status="active",
            source_version=mcp.version or "1.0",
            synced_version=mcp.version or "1.0",
        )
        self.db.add(binding)

        # 更新 Agent 的 enabled_mcp_servers
        from app.models.agent import Agent
        r3 = await self.db.execute(select(Agent).where(Agent.id == agent_id))
        agent = r3.scalar_one_or_none()
        if agent:
            try:
                servers = json.loads(agent.enabled_mcp_servers) if agent.enabled_mcp_servers else []
            except (json.JSONDecodeError, TypeError):
                servers = []
            if mcp_server_id not in servers:
                servers.append(mcp_server_id)
                agent.enabled_mcp_servers = json.dumps(servers, ensure_ascii=False)

        # 独立模式：复制 MCP 配置到独立记录
        if sync_mode == "independent":
            # 创建独立 MCP 配置记录
            new_mcp = MCPServer(
                id=str(uuid.uuid4()),
                name=f"{mcp.name} @ {agent_id[:8]}",
                url=mcp.url,
                protocol=mcp.protocol,
                status="active",
                description=f"独立副本 - 源自 {mcp.id}",
                auth_type=mcp.auth_type,
                auth_config=mcp.auth_config,
                config=mcp.config,
                version=mcp.version,
                health_status="unknown",
            )
            self.db.add(new_mcp)
            await self.db.flush()
            # 更新绑定指向新 MCP
            binding.mcp_server_id = new_mcp.id
            binding.template_id = mcp_server_id  # 记录模板来源

        await self.db.flush()

    # ----------------------------------------------------------
    # 跨 Agent 同步管理
    # ----------------------------------------------------------

    async def get_binding(self, binding_id: str) -> Optional[MCPAgentBinding]:
        r = await self.db.execute(
            select(MCPAgentBinding).where(MCPAgentBinding.id == binding_id)
        )
        return r.scalar_one_or_none()

    async def list_bindings(
        self, mcp_server_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        sync_mode: Optional[str] = None,
        status: Optional[str] = None,
        offset: int = 0, limit: int = 50,
    ) -> tuple[list[MCPAgentBinding], int]:
        conditions = []
        if mcp_server_id:
            conditions.append(MCPAgentBinding.mcp_server_id == mcp_server_id)
        if agent_id:
            conditions.append(MCPAgentBinding.agent_id == agent_id)
        if sync_mode:
            conditions.append(MCPAgentBinding.sync_mode == sync_mode)
        if status:
            conditions.append(MCPAgentBinding.status == status)

        where = and_(*conditions) if conditions else True
        count_q = select(sa_func.count()).select_from(MCPAgentBinding).where(where)
        total = (await self.db.execute(count_q)).scalar() or 0

        r = await self.db.execute(
            select(MCPAgentBinding).where(where)
            .order_by(MCPAgentBinding.created_at.desc())
            .offset(offset).limit(limit)
        )
        return list(r.scalars().all()), total

    async def remove_binding(self, binding_id: str) -> bool:
        """删除绑定关系"""
        binding = await self.get_binding(binding_id)
        if not binding:
            return False
        # 从 Agent 的 enabled_mcp_servers 中移除
        from app.models.agent import Agent
        r = await self.db.execute(select(Agent).where(Agent.id == binding.agent_id))
        agent = r.scalar_one_or_none()
        if agent:
            try:
                servers = json.loads(agent.enabled_mcp_servers) if agent.enabled_mcp_servers else []
            except (json.JSONDecodeError, TypeError):
                servers = []
            mcp_id = binding.mcp_server_id
            if binding.sync_mode == "independent" and binding.template_id:
                mcp_id = binding.template_id
            if mcp_id in servers:
                servers.remove(mcp_id)
                agent.enabled_mcp_servers = json.dumps(servers, ensure_ascii=False)

        await self.db.delete(binding)
        await self.db.flush()
        return True

    async def update_binding(
        self, binding_id: str, data: dict[str, Any]
    ) -> Optional[MCPAgentBinding]:
        """更新绑定配置"""
        binding = await self.get_binding(binding_id)
        if not binding:
            return None

        updatable = ["sync_mode", "override_config", "override_protocol", "override_auth"]
        for key in updatable:
            if key in data:
                if key in ("override_config", "override_auth"):
                    setattr(binding, key, json.dumps(data[key], ensure_ascii=False))
                else:
                    setattr(binding, key, data[key])

        binding.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return binding

    # ----------------------------------------------------------
    # 同步
    # ----------------------------------------------------------

    async def sync_binding(self, binding_id: str) -> dict[str, Any]:
        """同步单条绑定"""
        binding = await self.get_binding(binding_id)
        if not binding:
            return {"error": "绑定不存在"}

        # 获取源 MCP 配置
        source_id = binding.template_id if binding.sync_mode == "independent" and binding.template_id else binding.mcp_server_id
        r = await self.db.execute(select(MCPServer).where(MCPServer.id == source_id))
        source = r.scalar_one_or_none()
        if not source:
            return {"error": "源 MCP 不存在"}

        if binding.sync_mode == "shared":
            # 共享模式：将 Agent 指向源 MCP
            from app.models.agent import Agent
            r2 = await self.db.execute(select(Agent).where(Agent.id == binding.agent_id))
            agent = r2.scalar_one_or_none()
            if agent:
                try:
                    servers = json.loads(agent.enabled_mcp_servers) if agent.enabled_mcp_servers else []
                except (json.JSONDecodeError, TypeError):
                    servers = []
                if source_id not in servers:
                    servers.append(source_id)
                # 移除旧的独立 MCP
                if binding.mcp_server_id != source_id and binding.mcp_server_id in servers:
                    servers.remove(binding.mcp_server_id)
                agent.enabled_mcp_servers = json.dumps(servers, ensure_ascii=False)
            binding.mcp_server_id = source_id

        elif binding.sync_mode == "independent":
            # 独立模式：更新独立副本的配置
            r3 = await self.db.execute(select(MCPServer).where(MCPServer.id == binding.mcp_server_id))
            target = r3.scalar_one_or_none()
            if target and source:
                target.url = source.url
                target.protocol = source.protocol
                target.config = source.config
                target.version = source.version

        elif binding.sync_mode == "template":
            # 模板模式：更新派生配置
            r3 = await self.db.execute(select(MCPServer).where(MCPServer.id == binding.mcp_server_id))
            target = r3.scalar_one_or_none()
            if target and source:
                try:
                    override = json.loads(binding.override_config) if binding.override_config else {}
                except (json.JSONDecodeError, TypeError):
                    override = {}
                target.url = override.get("url", source.url)
                target.protocol = override.get("protocol", source.protocol)
                target.version = source.version

        binding.synced_version = source.version
        binding.status = "active"
        binding.last_synced_at = datetime.now(timezone.utc)
        binding.sync_error = None
        await self.db.flush()

        return {
            "binding_id": binding.id,
            "agent_id": binding.agent_id,
            "sync_mode": binding.sync_mode,
            "status": "synced",
        }

    async def check_updates(self, mcp_server_id: str) -> list[dict]:
        """检查源 MCP 是否有更新"""
        r = await self.db.execute(select(MCPServer).where(MCPServer.id == mcp_server_id))
        source = r.scalar_one_or_none()
        if not source:
            return []

        target_id = mcp_server_id
        r2 = await self.db.execute(
            select(MCPAgentBinding).where(
                MCPAgentBinding.mcp_server_id == target_id,
            )
        )
        bindings = list(r2.scalars().all())

        # 也检查 template 模式（template_id 指向源）
        r3 = await self.db.execute(
            select(MCPAgentBinding).where(
                MCPAgentBinding.template_id == mcp_server_id,
                MCPAgentBinding.sync_mode == "independent",
            )
        )
        bindings.extend(list(r3.scalars().all()))

        updates = []
        for b in bindings:
            if b.synced_version != source.version:
                updates.append({
                    "binding_id": b.id,
                    "agent_id": b.agent_id,
                    "sync_mode": b.sync_mode,
                    "current_version": b.synced_version,
                    "new_version": source.version,
                })
                if b.status == "active":
                    b.status = "outdated"
        await self.db.flush()
        return updates

    async def sync_all_for_mcp(self, mcp_server_id: str) -> list[dict]:
        """同步源 MCP 的所有绑定"""
        updates = await self.check_updates(mcp_server_id)
        results = []
        for upd in updates:
            result = await self.sync_binding(upd["binding_id"])
            results.append(result)
        return results

    # ----------------------------------------------------------
    # 查询辅助
    # ----------------------------------------------------------

    async def get_queue(self, queue_id: str) -> Optional[MCPBatchInstallQueue]:
        r = await self.db.execute(
            select(MCPBatchInstallQueue).where(MCPBatchInstallQueue.id == queue_id)
        )
        return r.scalar_one_or_none()

    async def get_queue_items(self, queue_id: str, offset: int = 0, limit: int = 100
                             ) -> tuple[list[MCPBatchInstallItem], int]:
        count_q = select(sa_func.count()).select_from(MCPBatchInstallItem).where(
            MCPBatchInstallItem.queue_id == queue_id)
        total = (await self.db.execute(count_q)).scalar() or 0
        r = await self.db.execute(
            select(MCPBatchInstallItem).where(MCPBatchInstallItem.queue_id == queue_id)
            .order_by(MCPBatchInstallItem.created_at).offset(offset).limit(limit)
        )
        return list(r.scalars().all()), total

    async def list_queues(self, offset: int = 0, limit: int = 20
                         ) -> tuple[list[MCPBatchInstallQueue], int]:
        count_q = select(sa_func.count()).select_from(MCPBatchInstallQueue)
        total = (await self.db.execute(count_q)).scalar() or 0
        r = await self.db.execute(
            select(MCPBatchInstallQueue).order_by(MCPBatchInstallQueue.created_at.desc())
            .offset(offset).limit(limit)
        )
        return list(r.scalars().all()), total
