"""
Skill 跨 Agent 复用服务 — 复用关系管理、同步、统计
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, func as sa_func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill, SkillBinding
from app.models.skill_reuse import SkillReuseRelation


class SkillReuseService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ----------------------------------------------------------
    # 复用关系 CRUD
    # ----------------------------------------------------------

    async def create_reuse(
        self,
        source_skill_id: str,
        target_agent_id: str,
        reuse_mode: str = "direct_ref",
        sync_mode: str = "manual",
        source_agent_id: str = "",
    ) -> SkillReuseRelation:
        """
        创建 Skill 复用关系。
        reuse_mode:
          - direct_ref: 直接引用源 Skill，变更影响所有引用者
          - copy: 独立复制一份新 Skill
          - template: 从模板派生，模板更新可通知派生实例
        """
        # 获取源 Skill
        r = await self.db.execute(
            select(Skill).where(Skill.id == source_skill_id)
        )
        source = r.scalar_one_or_none()
        if not source:
            raise ValueError("源 Skill 不存在")

        target_skill_id = source_skill_id
        target_skill_name = source.name

        if reuse_mode == "copy":
            # 复制创建新 Skill
            new_skill = Skill(
                id=str(uuid.uuid4()),
                name=f"{source.name} (副本)",
                version=source.version,
                description=source.description,
                type=source.type,
                category=source.category,
                source="local",
                entry_point=source.entry_point,
                parameters=source.parameters,
                dependencies=source.dependencies,
                enabled=True,
                workspace_id=source.workspace_id,
                created_by=target_agent_id,
            )
            self.db.add(new_skill)
            await self.db.flush()
            target_skill_id = new_skill.id
            target_skill_name = new_skill.name

        # 创建绑定
        r2 = await self.db.execute(
            select(SkillBinding).where(
                SkillBinding.skill_id == target_skill_id,
                SkillBinding.agent_id == target_agent_id,
            )
        )
        if not r2.scalar_one_or_none():
            binding = SkillBinding(
                id=str(uuid.uuid4()),
                agent_id=target_agent_id,
                skill_id=target_skill_id,
                enabled=True,
            )
            self.db.add(binding)
            source.installed_count = (source.installed_count or 0) + 1

        # 创建复用关系
        relation = SkillReuseRelation(
            source_skill_id=source_skill_id,
            source_skill_name=source.name,
            source_agent_id=source_agent_id,
            target_skill_id=target_skill_id,
            target_skill_name=target_skill_name,
            target_agent_id=target_agent_id,
            reuse_mode=reuse_mode,
            sync_mode=sync_mode,
            status="active",
            source_version=source.version,
            target_version=source.version,
            synced_version=source.version,
        )
        self.db.add(relation)
        await self.db.flush()
        return relation

    async def remove_reuse(self, relation_id: str) -> bool:
        """删除复用关系（不解绑 Skill，仅删除关系记录）"""
        r = await self.db.execute(
            select(SkillReuseRelation).where(SkillReuseRelation.id == relation_id)
        )
        rel = r.scalar_one_or_none()
        if not rel:
            return False
        await self.db.delete(rel)
        await self.db.flush()
        return True

    async def get_reuse(self, relation_id: str) -> Optional[SkillReuseRelation]:
        r = await self.db.execute(
            select(SkillReuseRelation).where(SkillReuseRelation.id == relation_id)
        )
        return r.scalar_one_or_none()

    async def list_reuses(
        self,
        source_skill_id: Optional[str] = None,
        target_agent_id: Optional[str] = None,
        target_skill_id: Optional[str] = None,
        reuse_mode: Optional[str] = None,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[SkillReuseRelation], int]:
        conditions = []
        if source_skill_id:
            conditions.append(SkillReuseRelation.source_skill_id == source_skill_id)
        if target_agent_id:
            conditions.append(SkillReuseRelation.target_agent_id == target_agent_id)
        if target_skill_id:
            conditions.append(SkillReuseRelation.target_skill_id == target_skill_id)
        if reuse_mode:
            conditions.append(SkillReuseRelation.reuse_mode == reuse_mode)
        if status:
            conditions.append(SkillReuseRelation.status == status)

        where = and_(*conditions) if conditions else True

        count_q = select(sa_func.count()).select_from(SkillReuseRelation).where(where)
        total = (await self.db.execute(count_q)).scalar() or 0

        r = await self.db.execute(
            select(SkillReuseRelation).where(where)
            .order_by(SkillReuseRelation.created_at.desc())
            .offset(offset).limit(limit)
        )
        return list(r.scalars().all()), total

    # ----------------------------------------------------------
    # 同步与变更检测
    # ----------------------------------------------------------

    async def check_updates(self, source_skill_id: str) -> list[dict]:
        """
        检查源 Skill 是否有更新。
        返回需要通知的复用关系列表。
        """
        r = await self.db.execute(
            select(Skill).where(Skill.id == source_skill_id)
        )
        source = r.scalar_one_or_none()
        if not source:
            return []

        r2 = await self.db.execute(
            select(SkillReuseRelation).where(
                SkillReuseRelation.source_skill_id == source_skill_id,
                SkillReuseRelation.status.in_(["active", "outdated"]),
            )
        )
        relations = list(r2.scalars().all())

        updates = []
        for rel in relations:
            is_outdated = rel.synced_version != source.version
            if is_outdated or rel.status == "outdated":
                updates.append({
                    "relation_id": rel.id,
                    "target_agent_id": rel.target_agent_id,
                    "target_skill_id": rel.target_skill_id,
                    "target_skill_name": rel.target_skill_name,
                    "reuse_mode": rel.reuse_mode,
                    "sync_mode": rel.sync_mode,
                    "current_version": rel.synced_version,
                    "new_version": source.version,
                    "status": "outdated",
                })
                if is_outdated:
                    rel.status = "outdated"
                    rel.updated_at = datetime.now(timezone.utc)

        await self.db.flush()
        return updates

    async def sync_reuse(self, relation_id: str) -> dict[str, Any]:
        """执行单条复用关系的同步"""
        r = await self.db.execute(
            select(SkillReuseRelation).where(SkillReuseRelation.id == relation_id)
        )
        rel = r.scalar_one_or_none()
        if not rel:
            return {"error": "关系不存在"}

        r2 = await self.db.execute(
            select(Skill).where(Skill.id == rel.source_skill_id)
        )
        source = r2.scalar_one_or_none()
        if not source:
            return {"error": "源 Skill 不存在"}

        if rel.reuse_mode == "copy":
            # 复制模式下：更新目标 Skill 的配置
            r3 = await self.db.execute(
                select(Skill).where(Skill.id == rel.target_skill_id)
            )
            target = r3.scalar_one_or_none()
            if target:
                target.version = source.version
                target.description = source.description
                target.entry_point = source.entry_point
                target.parameters = source.parameters
                target.dependencies = source.dependencies
        elif rel.reuse_mode == "template":
            # 模板模式下：更新目标 Skill
            r3 = await self.db.execute(
                select(Skill).where(Skill.id == rel.target_skill_id)
            )
            target = r3.scalar_one_or_none()
            if target:
                target.version = source.version
                target.parameters = source.parameters
                target.entry_point = source.entry_point
        # direct_ref 模式下：目标就是引用源，无需更新

        rel.synced_version = source.version
        rel.status = "active"
        rel.last_synced_at = datetime.now(timezone.utc)
        rel.reuse_count = (rel.reuse_count or 0) + 1
        await self.db.flush()

        return {
            "relation_id": rel.id,
            "source_skill_id": rel.source_skill_id,
            "target_skill_id": rel.target_skill_id,
            "target_agent_id": rel.target_agent_id,
            "new_version": source.version,
            "status": "synced",
        }

    async def sync_all_for_source(self, source_skill_id: str) -> list[dict]:
        """同步源 Skill 的所有复用关系"""
        updates = await self.check_updates(source_skill_id)
        results = []
        for upd in updates:
            result = await self.sync_reuse(upd["relation_id"])
            results.append(result)
        return results

    # ----------------------------------------------------------
    # 统计与排行
    # ----------------------------------------------------------

    async def get_reuse_stats(self, skill_id: str) -> dict[str, Any]:
        """获取指定 Skill 的复用统计"""
        r = await self.db.execute(
            select(SkillReuseRelation).where(
                SkillReuseRelation.source_skill_id == skill_id,
            )
        )
        relations = list(r.scalars().all())

        by_mode: dict[str, int] = {}
        by_status: dict[str, int] = {}
        agents = set()

        for rel in relations:
            by_mode[rel.reuse_mode] = by_mode.get(rel.reuse_mode, 0) + 1
            by_status[rel.status] = by_status.get(rel.status, 0) + 1
            agents.add(rel.target_agent_id)

        return {
            "skill_id": skill_id,
            "total_reuses": len(relations),
            "unique_agents": len(agents),
            "by_mode": by_mode,
            "by_status": by_status,
        }

    async def get_reuse_ranking(self, limit: int = 10) -> list[dict]:
        """获取复用排行 Top N"""
        r = await self.db.execute(
            select(
                SkillReuseRelation.source_skill_id,
                SkillReuseRelation.source_skill_name,
                sa_func.count().label("count"),
                sa_func.count(sa_func.distinct(SkillReuseRelation.target_agent_id)).label("agent_count"),
            )
            .group_by(SkillReuseRelation.source_skill_id, SkillReuseRelation.source_skill_name)
            .order_by(sa_func.count().desc())
            .limit(limit)
        )
        rows = r.all()
        return [
            {
                "skill_id": row[0],
                "skill_name": row[1],
                "reuse_count": row[2],
                "agent_count": row[3],
            }
            for row in rows
        ]

    async def get_reuse_graph(self, source_skill_id: str) -> dict[str, Any]:
        """获取复用关系图数据（用于可视化）"""
        r = await self.db.execute(
            select(SkillReuseRelation).where(
                SkillReuseRelation.source_skill_id == source_skill_id,
            )
        )
        relations = list(r.scalars().all())

        nodes = []
        edges = []

        # 源节点
        r2 = await self.db.execute(
            select(Skill).where(Skill.id == source_skill_id)
        )
        source = r2.scalar_one_or_none()
        if source:
            nodes.append({
                "id": source.id,
                "name": source.name,
                "type": "source",
                "mode": "source",
            })

        for rel in relations:
            # 目标 Agent 节点
            agent_node_id = f"agent_{rel.target_agent_id}"
            if not any(n["id"] == agent_node_id for n in nodes):
                nodes.append({
                    "id": agent_node_id,
                    "name": rel.target_agent_id,
                    "type": "agent",
                    "mode": rel.reuse_mode,
                })

            # 目标 Skill 节点
            if rel.target_skill_id != source_skill_id:
                if not any(n["id"] == rel.target_skill_id for n in nodes):
                    r3 = await self.db.execute(
                        select(Skill).where(Skill.id == rel.target_skill_id)
                    )
                    target_skill = r3.scalar_one_or_none()
                    nodes.append({
                        "id": rel.target_skill_id,
                        "name": target_skill.name if target_skill else rel.target_skill_name,
                        "type": "skill",
                        "mode": rel.reuse_mode,
                    })

            # 边
            edges.append({
                "source": source_skill_id,
                "target": rel.target_skill_id if rel.reuse_mode == "copy" else agent_node_id,
                "label": rel.reuse_mode,
                "status": rel.status,
            })
            edges.append({
                "source": agent_node_id,
                "target": rel.target_skill_id if rel.reuse_mode == "copy" else source_skill_id,
                "label": "uses",
                "status": rel.status,
            })

        return {"nodes": nodes, "edges": edges}
