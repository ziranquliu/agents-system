"""
批量 Skill 分配与安装服务 - 依赖预检 / 安装队列 / 报告
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, func as sa_func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill, SkillBinding
from app.models.batch_install import BatchInstallQueue, BatchInstallItem

from sqlalchemy.orm import selectinload, joinedload


class BatchInstallService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ----------------------------------------------------------
    # 依赖预检
    # ----------------------------------------------------------

    async def check_dependencies(self, skill: Skill) -> dict[str, Any]:
        """
        检查 Skill 的依赖项。
        依赖格式: ["python:requests>=2.0", "node:axios", "system:git"]
        返回: { "status": "passed"|"warning"|"blocked", "checks": [...] }
        """
        deps_raw = skill.dependencies
        if not deps_raw:
            return {"status": "passed", "checks": []}

        try:
            deps = json.loads(deps_raw) if isinstance(deps_raw, str) else deps_raw
        except (json.JSONDecodeError, TypeError):
            deps = []

        if not isinstance(deps, list):
            return {"status": "passed", "checks": []}

        checks = []
        statuses = set()

        for dep in deps:
            dep_str = str(dep).strip()
            check = {"dependency": dep_str, "status": "unknown", "detail": "", "level": "info"}

            if dep_str.startswith("python:"):
                pkg = dep_str[7:]
                check["detail"] = f"Python 包: {pkg}"
                # 模拟检查 — 实际应调用 pip show
                import importlib
                pkg_name = pkg.split(">=")[0].split("==")[0].split("<")[0].strip()
                try:
                    importlib.import_module(pkg_name.replace("-", "_"))
                    check["status"] = "installed"
                    check["level"] = "info"
                except ImportError:
                    check["status"] = "missing"
                    check["detail"] = f"Python 包未安装: {pkg}"
                    check["level"] = "warning"
                    statuses.add("warning")

            elif dep_str.startswith("node:"):
                pkg_name = dep_str[5:]
                check["detail"] = f"Node 包: {pkg_name}"
                check["status"] = "unknown"
                check["level"] = "warning"
                statuses.add("warning")

            elif dep_str.startswith("system:"):
                cmd = dep_str[7:]
                check["detail"] = f"系统命令: {cmd}"
                # 模拟检查
                import shutil
                if shutil.which(cmd.split()[0]):
                    check["status"] = "available"
                    check["level"] = "info"
                else:
                    check["status"] = "missing"
                    check["detail"] = f"系统命令未找到: {cmd}"
                    check["level"] = "blocked"
                    statuses.add("blocked")

            else:
                check["detail"] = f"未知依赖类型: {dep_str}"
                check["status"] = "unknown"
                check["level"] = "warning"
                statuses.add("warning")

            checks.append(check)

        if "blocked" in statuses:
            final_status = "blocked"
        elif "warning" in statuses:
            final_status = "warning"
        else:
            final_status = "passed"

        return {"status": final_status, "checks": checks}

    async def batch_precheck(self, skill_ids: list[str],
                             agent_ids: list[str]) -> dict[str, Any]:
        """
        对批量安装进行预检。
        返回每个 skill 在每个 agent 上的依赖检查结果。
        """
        results = []
        statuses = set()

        for skill_id in skill_ids:
            r = await self.db.execute(
                select(Skill).where(Skill.id == skill_id)
            )
            skill = r.scalar_one_or_none()
            if not skill:
                dep_check = {"status": "blocked", "checks": [{"dependency": skill_id, "status": "missing", "level": "blocked"}]}
            else:
                dep_check = await self.check_dependencies(skill)

            statuses.add(dep_check["status"])

            for agent_id in agent_ids:
                results.append({
                    "skill_id": skill_id,
                    "skill_name": skill.name if skill else "未知",
                    "agent_id": agent_id,
                    "dep_check_status": dep_check["status"],
                    "dep_check_detail": dep_check["checks"],
                })

        # 合并状态
        if "blocked" in statuses:
            summary_status = "blocked"
        elif "warning" in statuses:
            summary_status = "warning"
        else:
            summary_status = "passed"

        return {
            "status": summary_status,
            "items": results,
            "total": len(results),
            "passed_count": sum(1 for r in results if r["dep_check_status"] == "passed"),
            "warning_count": sum(1 for r in results if r["dep_check_status"] == "warning"),
            "blocked_count": sum(1 for r in results if r["dep_check_status"] == "blocked"),
            "summary": self._precheck_summary_text(summary_status, results),
        }

    @staticmethod
    def _precheck_summary_text(status: str, items: list[dict]) -> str:
        total = len(items)
        blocked = sum(1 for r in items if r["dep_check_status"] == "blocked")
        w = sum(1 for r in items if r["dep_check_status"] == "warning")
        passed = total - blocked - w

        if status == "blocked":
            return f"预检未通过: {blocked}/{total} 项存在阻塞性依赖缺失，无法安装"
        elif status == "warning":
            return f"预检通过（有警告）: {w}/{total} 项存在可选依赖缺失，可以安装但部分功能受限"
        else:
            return f"预检通过: 所有 {total} 项依赖检查均通过"

    # ----------------------------------------------------------
    # 批量安装
    # ----------------------------------------------------------

    async def create_batch_install(
        self,
        skill_ids: list[str],
        agent_ids: list[str],
        operation: str = "install",
        created_by: str = "",
    ) -> BatchInstallQueue:
        """创建批量安装任务并执行预检"""
        # 创建队列
        queue = BatchInstallQueue(
            operation=operation,
            status="prechecking",
            total_items=len(skill_ids) * len(agent_ids),
            created_by=created_by,
        )
        self.db.add(queue)
        await self.db.flush()

        # 预检
        precheck = await self.batch_precheck(skill_ids, agent_ids)

        queue.precheck_status = precheck["status"]
        queue.precheck_summary = json.dumps(precheck, ensure_ascii=False)
        queue.status = "pending"
        await self.db.flush()

        # 创建各个安装项
        for item in precheck["items"]:
            install_item = BatchInstallItem(
                queue_id=queue.id,
                skill_id=item["skill_id"],
                skill_name=item["skill_name"],
                agent_id=item["agent_id"],
                agent_name=item["agent_id"],
                dep_check_status=item["dep_check_status"],
                dep_check_detail=json.dumps(item["dep_check_detail"], ensure_ascii=False),
                status="pending",
            )
            self.db.add(install_item)

        await self.db.flush()
        return queue

    async def execute_batch(self, queue_id: str) -> BatchInstallQueue:
        """执行批量安装"""
        r = await self.db.execute(
            select(BatchInstallQueue).where(BatchInstallQueue.id == queue_id)
        )
        queue = r.scalar_one_or_none()
        if not queue:
            raise ValueError("队列不存在")
        if queue.status != "pending":
            raise ValueError(f"队列状态异常: {queue.status}")

        queue.status = "running"
        await self.db.flush()

        r = await self.db.execute(
            select(BatchInstallItem).where(BatchInstallItem.queue_id == queue_id)
        )
        items = list(r.scalars().all())
        now = datetime.now(timezone.utc)

        for item in items:
            if item.status != "pending":
                continue

            if item.dep_check_status == "blocked":
                item.status = "skipped"
                item.error_message = "依赖预检未通过，跳过安装"
                item.completed_at = now
                queue.fail_count = (queue.fail_count or 0) + 1
                continue

            item.status = "running"
            item.started_at = now
            await self.db.flush()

            try:
                if queue.operation in ("install", "bind"):
                    await self._do_bind(item.skill_id, item.agent_id)
                elif queue.operation in ("uninstall", "unbind"):
                    await self._do_unbind(item.skill_id, item.agent_id)

                item.status = "success"
                queue.success_count = (queue.success_count or 0) + 1

                if item.dep_check_status == "warning":
                    queue.warn_count = (queue.warn_count or 0) + 1

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

    async def _do_bind(self, skill_id: str, agent_id: str):
        """执行单个绑定"""
        result = await self.db.execute(
            select(SkillBinding).where(
                SkillBinding.skill_id == skill_id,
                SkillBinding.agent_id == agent_id,
            )
        )
        existing = result.scalar_one_or_none()
        if not existing:
            binding = SkillBinding(
                id=str(uuid.uuid4()),
                skill_id=skill_id,
                agent_id=agent_id,
                enabled=True,
            )
            self.db.add(binding)
            # 更新安装计数
            from sqlalchemy import update as sa_update
            await self.db.execute(
                sa_update(Skill).where(Skill.id == skill_id).values(
                    installed_count=Skill.installed_count + 1
                )
            )
        await self.db.flush()

    async def _do_unbind(self, skill_id: str, agent_id: str):
        """执行单个解绑"""
        from sqlalchemy import delete as sa_delete
        await self.db.execute(
            sa_delete(SkillBinding).where(
                SkillBinding.skill_id == skill_id,
                SkillBinding.agent_id == agent_id,
            )
        )
        await self.db.flush()

    # ----------------------------------------------------------
    # 查询
    # ----------------------------------------------------------

    async def get_queue(self, queue_id: str) -> Optional[BatchInstallQueue]:
        r = await self.db.execute(
            select(BatchInstallQueue).where(BatchInstallQueue.id == queue_id)
        )
        return r.scalar_one_or_none()

    async def get_queue_items(self, queue_id: str, offset: int = 0, limit: int = 100
                             ) -> tuple[list[BatchInstallItem], int]:
        count_q = select(sa_func.count()).select_from(BatchInstallItem).where(
            BatchInstallItem.queue_id == queue_id)
        total = (await self.db.execute(count_q)).scalar() or 0

        r = await self.db.execute(
            select(BatchInstallItem).where(BatchInstallItem.queue_id == queue_id)
            .order_by(BatchInstallItem.created_at).offset(offset).limit(limit)
        )
        return list(r.scalars().all()), total

    async def list_queues(self, status: Optional[str] = None,
                          offset: int = 0, limit: int = 20
                         ) -> tuple[list[BatchInstallQueue], int]:
        conditions = []
        if status:
            conditions.append(BatchInstallQueue.status == status)

        where = and_(*conditions) if conditions else True
        count_q = select(sa_func.count()).select_from(BatchInstallQueue).where(where)
        total = (await self.db.execute(count_q)).scalar() or 0

        r = await self.db.execute(
            select(BatchInstallQueue).where(where)
            .order_by(BatchInstallQueue.created_at.desc())
            .offset(offset).limit(limit)
        )
        return list(r.scalars().all()), total

    async def generate_report(self, queue_id: str) -> dict[str, Any]:
        """生成安装报告"""
        queue = await self.get_queue(queue_id)
        if not queue:
            return {"error": "队列不存在"}
        items, _ = await self.get_queue_items(queue_id)
        precheck = json.loads(queue.precheck_summary) if queue.precheck_summary else {}

        return {
            "queue_id": queue.id,
            "operation": queue.operation,
            "status": queue.status,
            "total": queue.total_items,
            "success": queue.success_count or 0,
            "failed": queue.fail_count or 0,
            "warnings": queue.warn_count or 0,
            "precheck_status": queue.precheck_status,
            "precheck_summary": precheck.get("summary", ""),
            "created_by": queue.created_by,
            "created_at": queue.created_at.isoformat() if queue.created_at else None,
            "completed_at": queue.completed_at.isoformat() if queue.completed_at else None,
            "duration": str(queue.completed_at - queue.created_at) if queue.completed_at and queue.created_at else None,
            "items": [
                {
                    "skill_id": i.skill_id,
                    "skill_name": i.skill_name,
                    "agent_id": i.agent_id,
                    "dep_check_status": i.dep_check_status,
                    "status": i.status,
                    "error_message": i.error_message,
                }
                for i in items
            ],
        }
