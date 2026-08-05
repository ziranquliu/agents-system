"""
协作服务 - 创建、管理、执行多Agent协作
"""
import asyncio
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collaboration import Collaboration, CollaborationTask
from app.models.agent import Agent, ModelConfigTemplate
from app.services.llm import create_adapter

logger = logging.getLogger(__name__)


class CollaborationService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def create_collaboration(
        self, data: dict, user_id: str
    ) -> Collaboration:
        collab = Collaboration(
            id=str(uuid.uuid4()),
            name=data["name"],
            description=data.get("description", ""),
            mode=data.get("mode", "sequential"),
            config=json.dumps(data.get("config", {})),
            status="draft",
            created_by=user_id,
        )
        self.db.add(collab)
        await self.db.flush()
        return collab

    async def get_collaboration(self, collab_id: str) -> Optional[Collaboration]:
        result = await self.db.execute(
            select(Collaboration).where(Collaboration.id == collab_id)
        )
        return result.scalar_one_or_none()

    async def update_collaboration(
        self, collab_id: str, data: dict
    ) -> Optional[Collaboration]:
        collab = await self.get_collaboration(collab_id)
        if not collab:
            return None
        for key in ("name", "description", "mode", "config"):
            if key in data:
                if key == "config":
                    collab.config = json.dumps(data[key])
                else:
                    setattr(collab, key, data[key])
        collab.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return collab

    async def delete_collaboration(self, collab_id: str) -> bool:
        collab = await self.get_collaboration(collab_id)
        if not collab:
            return False
        await self.db.delete(collab)
        await self.db.flush()
        return True

    async def list_collaborations(
        self, offset: int = 0, limit: int = 20, user_id: Optional[str] = None
    ) -> tuple[list[Collaboration], int]:
        q = select(Collaboration)
        if user_id:
            q = q.where(Collaboration.created_by == user_id)
        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0
        q = q.order_by(Collaboration.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all()), total

    # ------------------------------------------------------------------
    # 任务管理
    # ------------------------------------------------------------------

    async def add_task(self, collab_id: str, data: dict) -> CollaborationTask:
        task = CollaborationTask(
            id=str(uuid.uuid4()),
            collaboration_id=collab_id,
            name=data["name"],
            agent_id=data["agent_id"],
            input_template=data.get("input_template", ""),
            order=data.get("order", 0),
            depends_on=json.dumps(data.get("depends_on", [])),
            timeout=data.get("timeout", 300),
        )
        self.db.add(task)
        await self.db.flush()
        return task

    async def list_tasks(self, collab_id: str) -> list[CollaborationTask]:
        result = await self.db.execute(
            select(CollaborationTask)
            .where(CollaborationTask.collaboration_id == collab_id)
            .order_by(CollaborationTask.order)
        )
        return list(result.scalars().all())

    async def remove_task(self, task_id: str) -> bool:
        result = await self.db.execute(
            select(CollaborationTask).where(CollaborationTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return False
        await self.db.delete(task)
        await self.db.flush()
        return True

    # ------------------------------------------------------------------
    # LLM 适配器构建
    # ------------------------------------------------------------------

    async def _build_adapter(self, agent_id: str):
        """根据 Agent 的模型配置构建 LLM 适配器"""
        result = await self.db.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise ValueError(f"Agent {agent_id} 不存在")

        provider = agent.model_provider or "openai"
        model_name = agent.model_name

        # 优先从模板配置获取 endpoint/api_key
        config = {}
        if agent.model_config_template_id:
            tpl_result = await self.db.execute(
                select(ModelConfigTemplate).where(
                    ModelConfigTemplate.id == agent.model_config_template_id
                )
            )
            tpl = tpl_result.scalar_one_or_none()
            if tpl:
                try:
                    config = json.loads(tpl.config) if tpl.config else {}
                except (json.JSONDecodeError, TypeError):
                    config = {}
                if not model_name and tpl.model:
                    model_name = tpl.model

        if model_name:
            config["model_name"] = model_name
        if not config.get("endpoint") and provider == "openai":
            config.setdefault("endpoint", "https://api.openai.com/v1")

        return create_adapter(provider, config), agent

    async def _call_agent(
        self, agent_id: str, messages: list[dict], task_context: str = ""
    ) -> dict:
        """调用单个 Agent 并返回结果"""
        adapter, agent = await self._build_adapter(agent_id)

        system_prompt = agent.system_prompt or ""
        if task_context:
            system_prompt = f"{system_prompt}\n\n任务上下文: {task_context}" if system_prompt else f"任务上下文: {task_context}"

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        try:
            result = await adapter.chat(
                messages=full_messages,
                temperature=agent.temperature or 0.7,
                max_tokens=agent.max_tokens,
            )
            return {
                "agent_id": agent_id,
                "agent_name": agent.name,
                "content": result.content,
                "model": result.model,
                "usage": result.usage,
                "finish_reason": result.finish_reason,
                "success": True,
            }
        except Exception as e:
            logger.warning("Agent %s 调用失败: %s", agent.name, str(e))
            return {
                "agent_id": agent_id,
                "agent_name": agent.name,
                "content": "",
                "error": "Agent 调用失败",
                "success": False,
            }

    # ------------------------------------------------------------------
    # 协作模式执行器
    # ------------------------------------------------------------------

    async def start_collaboration(
        self, collab_id: str, input_text: str
    ) -> dict:
        collab = await self.get_collaboration(collab_id)
        if not collab:
            raise ValueError("协作不存在")
        if collab.status == "running":
            raise ValueError("协作正在运行中")

        collab.status = "running"
        collab.started_at = datetime.now(timezone.utc)
        collab.input_text = input_text
        await self.db.flush()

        tasks = await self.list_tasks(collab_id)
        if not tasks:
            collab.status = "completed"
            collab.output_text = "无任务可执行"
            await self.db.flush()
            return {"status": "completed", "output": "无任务可执行"}

        try:
            mode = collab.mode or "sequential"
            config = {}
            try:
                config = json.loads(collab.config) if collab.config else {}
            except (json.JSONDecodeError, TypeError):
                config = {}

            if mode == "sequential":
                output = await self._execute_sequential(tasks, input_text, config)
            elif mode == "parallel":
                output = await self._execute_parallel(tasks, input_text, config)
            elif mode == "broadcast":
                output = await self._execute_broadcast(tasks, input_text, config)
            elif mode == "supervisor":
                output = await self._execute_supervisor(tasks, input_text, config)
            elif mode == "debate":
                output = await self._execute_debate(tasks, input_text, config)
            elif mode == "team":
                output = await self._execute_team(tasks, input_text, config)
            elif mode == "pipeline":
                output = await self._execute_pipeline(tasks, input_text, config)
            elif mode == "market":
                output = await self._execute_market(tasks, input_text, config)
            elif mode == "vote":
                output = await self._execute_vote(tasks, input_text, config)
            else:
                output = await self._execute_sequential(tasks, input_text, config)

            collab.status = "completed"
            collab.output_text = json.dumps(output, ensure_ascii=False) if isinstance(output, dict) else str(output)
            collab.completed_at = datetime.now(timezone.utc)

        except Exception as e:
            logger.error("协作执行失败: %s", str(e))
            collab.status = "failed"
            collab.output_text = json.dumps({"error": "协作执行失败"}, ensure_ascii=False)

        collab.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return {"status": collab.status, "output": collab.output_text}

    # ------------------------------------------------------------------
    # 模式实现: 顺序执行
    # ------------------------------------------------------------------

    async def _execute_sequential(
        self, tasks: list[CollaborationTask], input_text: str, config: dict
    ) -> dict:
        """顺序执行: 每个Agent的输出作为下一个Agent的输入"""
        results = []
        current_input = input_text

        for task in sorted(tasks, key=lambda t: t.order or 0):
            result = await self._call_agent(
                task.agent_id,
                [{"role": "user", "content": current_input}],
                task_context=task.input_template or "",
            )
            results.append({"task": task.name, **result})
            if result["success"]:
                current_input = result["content"]
            else:
                break

        return {
            "mode": "sequential",
            "results": results,
            "final_output": current_input,
        }

    # ------------------------------------------------------------------
    # 模式实现: 并行执行
    # ------------------------------------------------------------------

    async def _execute_parallel(
        self, tasks: list[CollaborationTask], input_text: str, config: dict
    ) -> dict:
        """并行执行: 所有Agent同时处理相同输入"""
        async def run_task(task):
            return {
                "task": task.name,
                **await self._call_agent(
                    task.agent_id,
                    [{"role": "user", "content": input_text}],
                    task_context=task.input_template or "",
                ),
            }

        results = await asyncio.gather(
            *[run_task(t) for t in tasks], return_exceptions=True
        )
        processed = []
        for r in results:
            if isinstance(r, Exception):
                processed.append({"task": "unknown", "success": False, "error": str(r)})
            else:
                processed.append(r)

        return {"mode": "parallel", "results": processed}

    # ------------------------------------------------------------------
    # 模式实现: 广播
    # ------------------------------------------------------------------

    async def _execute_broadcast(
        self, tasks: list[CollaborationTask], input_text: str, config: dict
    ) -> dict:
        """广播: 所有Agent接收消息并独立处理"""
        summaries = []
        for task in sorted(tasks, key=lambda t: t.order or 0):
            result = await self._call_agent(
                task.agent_id,
                [{"role": "user", "content": input_text}],
                task_context=task.input_template or "",
            )
            summaries.append({
                "task": task.name,
                "agent_name": result.get("agent_name", ""),
                "success": result["success"],
                "summary": result["content"][:200] if result["success"] else "失败",
            })

        return {"mode": "broadcast", "total": len(tasks), "summaries": summaries}

    # ------------------------------------------------------------------
    # 模式实现: 监督者
    # ------------------------------------------------------------------

    async def _execute_supervisor(
        self, tasks: list[CollaborationTask], input_text: str, config: dict
    ) -> dict:
        """监督者模式: 第一个Agent为监督者,其余为工作者"""
        if len(tasks) < 2:
            return await self._execute_sequential(tasks, input_text, config)

        sorted_tasks = sorted(tasks, key=lambda t: t.order or 0)
        supervisor_task = sorted_tasks[0]
        worker_tasks = sorted_tasks[1:]

        # 监督者分解任务
        worker_names = [t.name for t in worker_tasks]
        decompose_prompt = (
            f"你是一个任务协调者。请根据以下用户需求,为每个工作者分配具体任务。\n\n"
            f"用户需求: {input_text}\n\n"
            f"可用工作者: {', '.join(worker_names)}\n\n"
            f"请以JSON格式返回每个工作者的具体任务描述,格式: "
            f'{{"tasks": {{"工作者名": "具体任务描述", ...}}}}'
        )
        supervisor_result = await self._call_agent(
            supervisor_task.agent_id,
            [{"role": "user", "content": decompose_prompt}],
        )

        # 解析任务分配
        task_assignments = {}
        if supervisor_result["success"]:
            try:
                parsed = json.loads(supervisor_result["content"])
                task_assignments = parsed.get("tasks", {})
            except (json.JSONDecodeError, TypeError):
                # 解析失败时给所有工作者分配相同任务
                task_assignments = {t.name: input_text for t in worker_tasks}

        # 并行执行工作者任务
        async def run_worker(worker_task):
            assigned_input = task_assignments.get(worker_task.name, input_text)
            return {
                "task": worker_task.name,
                **await self._call_agent(
                    worker_task.agent_id,
                    [{"role": "user", "content": assigned_input}],
                ),
            }

        worker_results = await asyncio.gather(
            *[run_worker(t) for t in worker_tasks], return_exceptions=True
        )
        workers_output = []
        for r in worker_results:
            if isinstance(r, Exception):
                workers_output.append(f"任务异常: {str(r)}")
            elif r.get("success"):
                workers_output.append(f"[{r['task']}] {r['content']}")
            else:
                workers_output.append(f"[{r['task']}] 执行失败")

        # 监督者汇总
        summary_prompt = (
            f"用户需求: {input_text}\n\n"
            f"各工作者的执行结果:\n" + "\n".join(workers_output) +
            f"\n\n请汇总以上结果,给出最终结论。"
        )
        summary_result = await self._call_agent(
            supervisor_task.agent_id,
            [{"role": "user", "content": summary_prompt}],
        )

        return {
            "mode": "supervisor",
            "supervisor": {
                "task": supervisor_task.name,
                "decomposition": task_assignments,
                "summary": summary_result["content"] if summary_result["success"] else "汇总失败",
            },
            "workers": [
                {"task": t.name, **r} if isinstance(r, dict) else {"task": "unknown", "error": str(r)}
                for t, r in zip(worker_tasks, worker_results)
            ],
        }

    # ------------------------------------------------------------------
    # 模式实现: 辩论
    # ------------------------------------------------------------------

    async def _execute_debate(
        self, tasks: list[CollaborationTask], input_text: str, config: dict
    ) -> dict:
        """辩论模式: 多Agent轮流发言,最终达成共识"""
        rounds = config.get("rounds", 3)
        sorted_tasks = sorted(tasks, key=lambda t: t.order or 0)

        debate_history: list[dict] = []  # [{agent_name, content}, ...]
        all_results = []

        for round_num in range(rounds):
            for task in sorted_tasks:
                # 构建辩论上下文
                context_parts = [f"辩题: {input_text}"]
                if debate_history:
                    context_parts.append("之前的发言:")
                    for entry in debate_history:
                        context_parts.append(f"[{entry['agent_name']}]: {entry['content']}")
                context_parts.append(
                    f"这是第{round_num + 1}轮发言。请给出你的观点和论据。"
                    f"如果是最后一轮,请尝试总结共识。"
                )

                result = await self._call_agent(
                    task.agent_id,
                    [{"role": "user", "content": "\n".join(context_parts)}],
                )
                if result["success"]:
                    debate_history.append({
                        "agent_name": result.get("agent_name", task.name),
                        "content": result["content"],
                        "round": round_num + 1,
                    })
                all_results.append({
                    "task": task.name,
                    "round": round_num + 1,
                    **result,
                })

        # 最终投票/总结
        consensus_prompt = (
            f"辩题: {input_text}\n\n"
            f"经过{rounds}轮辩论:\n"
            + "\n".join(
                f"[{e['agent_name']}] 第{e['round']}轮: {e['content'][:300]}"
                for e in debate_history
            )
            + "\n\n请尝试给出辩论的最终共识或主要分歧。"
        )
        final_result = await self._call_agent(
            sorted_tasks[0].agent_id,
            [{"role": "user", "content": consensus_prompt}],
        )

        return {
            "mode": "debate",
            "rounds": rounds,
            "history": debate_history,
            "consensus": final_result["content"] if final_result["success"] else "共识提取失败",
            "all_results": all_results,
        }

    # ------------------------------------------------------------------
    # 模式实现: 团队协作
    # ------------------------------------------------------------------

    async def _execute_team(
        self, tasks: list[CollaborationTask], input_text: str, config: dict
    ) -> dict:
        """团队协作: 角色分工,leader分配+汇总"""
        sorted_tasks = sorted(tasks, key=lambda t: t.order or 0)
        leader_task = sorted_tasks[0] if sorted_tasks else None
        member_tasks = sorted_tasks[1:] if len(sorted_tasks) > 1 else []

        if not leader_task or not member_tasks:
            return await self._execute_sequential(tasks, input_text, config)

        # Leader 分配角色
        member_names = [t.name for t in member_tasks]
        role_prompt = (
            f"你是一个团队负责人。团队成员: {', '.join(member_names)}\n"
            f"项目目标: {input_text}\n\n"
            f"请为每个成员分配具体的角色和任务,JSON格式:\n"
            f'{{"roles": {{"成员名": {{"role": "角色", "task": "具体任务"}}, ...}}}}'
        )
        leader_result = await self._call_agent(
            leader_task.agent_id,
            [{"role": "user", "content": role_prompt}],
        )

        # 解析角色分配
        roles = {}
        if leader_result["success"]:
            try:
                parsed = json.loads(leader_result["content"])
                roles = parsed.get("roles", {})
            except (json.JSONDecodeError, TypeError):
                roles = {t.name: {"role": "执行者", "task": input_text} for t in member_tasks}

        # 并行执行
        async def run_member(member_task):
            role_info = roles.get(member_task.name, {"role": "执行者", "task": input_text})
            task_desc = role_info.get("task", input_text) if isinstance(role_info, dict) else input_text
            result = await self._call_agent(
                member_task.agent_id,
                [{"role": "user", "content": task_desc}],
            )
            return {"task": member_task.name, "role": role_info, **result}

        member_results = await asyncio.gather(
            *[run_member(t) for t in member_tasks], return_exceptions=True
        )

        # Leader 汇总
        outputs = []
        for r in member_results:
            if isinstance(r, Exception):
                outputs.append(f"成员执行异常: {str(r)}")
            elif r.get("success"):
                outputs.append(f"[{r['task']}] {r['content']}")
            else:
                outputs.append(f"[{r['task']}] 执行失败")

        summary_prompt = (
            f"项目目标: {input_text}\n\n"
            f"团队成员产出:\n" + "\n".join(outputs) +
            f"\n\n请汇总团队成果,给出最终交付物。"
        )
        summary_result = await self._call_agent(
            leader_task.agent_id,
            [{"role": "user", "content": summary_prompt}],
        )

        return {
            "mode": "team",
            "leader": {
                "task": leader_task.name,
                "roles": roles,
                "summary": summary_result["content"] if summary_result["success"] else "汇总失败",
            },
            "members": [
                {"task": t.name, **r} if isinstance(r, dict) else {"task": "unknown", "error": str(r)}
                for t, r in zip(member_tasks, member_results)
            ],
        }

    # ------------------------------------------------------------------
    # 模式实现: 流水线
    # ------------------------------------------------------------------

    async def _execute_pipeline(
        self, tasks: list[CollaborationTask], input_text: str, config: dict
    ) -> dict:
        """流水线: 每个Agent在上一步产出基础上加工,保留中间产物"""
        stages = []
        current_data = input_text

        for task in sorted(tasks, key=lambda t: t.order or 0):
            result = await self._call_agent(
                task.agent_id,
                [{"role": "user", "content": current_data}],
                task_context=task.input_template or "",
            )
            stage = {
                "stage": task.name,
                "input": current_data[:500],
                "output": result["content"] if result["success"] else "",
                "success": result["success"],
            }
            stages.append(stage)
            if result["success"]:
                current_data = result["content"]

        return {
            "mode": "pipeline",
            "stages": stages,
            "final_output": current_data,
        }

    # ------------------------------------------------------------------
    # 模式实现: 市场竞争
    # ------------------------------------------------------------------

    async def _execute_market(
        self, tasks: list[CollaborationTask], input_text: str, config: dict
    ) -> dict:
        """市场竞争: 多个Agent独立提交方案,由评审Agent评判"""
        proposals = []
        for task in sorted(tasks, key=lambda t: t.order or 0):
            result = await self._call_agent(
                task.agent_id,
                [{"role": "user", "content": f"请针对以下需求提供你的解决方案:\n\n{input_text}"}],
            )
            if result["success"]:
                proposals.append({
                    "agent_name": result.get("agent_name", task.name),
                    "proposal": result["content"],
                })

        if not proposals:
            return {"mode": "market", "proposals": [], "winner": "无有效方案"}

        # 评审 (使用第一个Agent作为评审,或用配置的评审Agent)
        judge_id = config.get("judge_agent_id", tasks[0].agent_id)
        proposals_text = "\n\n".join(
            f"方案{i+1} [{p['agent_name']}]:\n{p['proposal'][:500]}"
            for i, p in enumerate(proposals)
        )
        judge_prompt = (
            f"需求: {input_text}\n\n"
            f"以下是各Agent提交的方案:\n\n{proposals_text}\n\n"
            f"请评审以上方案,给出评分(1-10)和推荐理由,JSON格式:\n"
            f'{{"evaluations": [{{"agent": "名称", "score": 8, "reason": "理由"}}], '
            f'"winner": "推荐的Agent名称"}}'
        )
        judge_result = await self._call_agent(
            judge_id,
            [{"role": "user", "content": judge_prompt}],
        )

        evaluations = []
        winner = ""
        if judge_result["success"]:
            try:
                parsed = json.loads(judge_result["content"])
                evaluations = parsed.get("evaluations", [])
                winner = parsed.get("winner", "")
            except (json.JSONDecodeError, TypeError):
                winner = proposals[0]["agent_name"] if proposals else ""

        return {
            "mode": "market",
            "proposals": proposals,
            "evaluations": evaluations,
            "winner": winner,
        }

    # ------------------------------------------------------------------
    # 模式实现: 投票
    # ------------------------------------------------------------------

    async def _execute_vote(
        self, tasks: list[CollaborationTask], input_text: str, config: dict
    ) -> dict:
        """投票模式: 多Agent独立回答,按多数或置信度选择"""
        responses = []
        for task in sorted(tasks, key=lambda t: t.order or 0):
            result = await self._call_agent(
                task.agent_id,
                [{"role": "user", "content": input_text}],
            )
            if result["success"]:
                responses.append({
                    "agent_name": result.get("agent_name", task.name),
                    "content": result["content"],
                })

        if not responses:
            return {"mode": "vote", "responses": [], "consensus": "无有效投票"}

        # 汇总投票
        vote_prompt = (
            f"问题: {input_text}\n\n"
            f"以下是各Agent的回答:\n"
            + "\n".join(
                f"[{r['agent_name']}]: {r['content'][:300]}"
                for r in responses
            )
            + "\n\n请分析以上回答的一致性和分歧,给出最终结论。"
        )
        synthesize_result = await self._call_agent(
            tasks[0].agent_id,
            [{"role": "user", "content": vote_prompt}],
        )

        return {
            "mode": "vote",
            "total_votes": len(responses),
            "responses": responses,
            "consensus": synthesize_result["content"] if synthesize_result["success"] else "投票汇总失败",
        }

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    async def get_collaboration_stats(self) -> dict:
        """获取协作统计"""
        total_q = select(func.count()).select_from(Collaboration)
        total = (await self.db.execute(total_q)).scalar() or 0

        running_q = select(func.count()).select_from(Collaboration).where(
            Collaboration.status == "running"
        )
        running = (await self.db.execute(running_q)).scalar() or 0

        completed_q = select(func.count()).select_from(Collaboration).where(
            Collaboration.status == "completed"
        )
        completed = (await self.db.execute(completed_q)).scalar() or 0

        return {
            "total": total,
            "running": running,
            "completed": completed,
            "failed": total - running - completed,
        }

    def list_modes(self) -> list[dict]:
        """列出所有支持的协作模式"""
        return [
            {"mode": "sequential", "name": "顺序执行", "description": "Agent按顺序依次处理,前一个Agent的输出作为下一个的输入"},
            {"mode": "parallel", "name": "并行执行", "description": "所有Agent同时处理相同输入,各自独立产出"},
            {"mode": "broadcast", "name": "广播模式", "description": "将消息广播给所有Agent,各自独立处理"},
            {"mode": "supervisor", "name": "监督者模式", "description": "监督者Agent分解任务,分配给工作者Agent执行,最终汇总"},
            {"mode": "debate", "name": "辩论模式", "description": "多Agent轮流发言辩论,最终尝试达成共识"},
            {"mode": "team", "name": "团队协作", "description": "Leader分配角色,团队成员分工执行,Leader汇总"},
            {"mode": "pipeline", "name": "流水线", "description": "每个Agent在上一步产出基础上加工,保留所有中间产物"},
            {"mode": "market", "name": "市场竞争", "description": "多Agent独立提交方案,评审Agent评判选出最优"},
            {"mode": "vote", "name": "投票模式", "description": "多Agent独立回答,汇总分析得出共识"},
        ]
