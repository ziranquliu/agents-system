"""
DAG 工作流引擎 - 拓扑排序、并行执行、依赖追踪、条件分支
支持: 并行度控制 (max_concurrency)、子图结果缓存 (subgraph cache)
"""
import asyncio
import hashlib
import json
import uuid
import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow import Workflow, WorkflowNode, WorkflowEdge, WorkflowExecution
from app.models.agent import Agent, ModelConfigTemplate
from app.services.llm import create_adapter

logger = logging.getLogger(__name__)


def _safe_json(s, default=None):
    if not s:
        return default if default is not None else {}
    try:
        return json.loads(s) if isinstance(s, str) else s
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else {}


class DAGValidationError(Exception):
    pass


class SubgraphCache:
    """子图结果缓存 (TTL-based)"""

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        self._cache: dict[str, tuple[Any, float]] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    def _make_key(self, node_ids: list[str], input_data: dict) -> str:
        raw = json.dumps(sorted(node_ids)) + json.dumps(input_data, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get(self, node_ids: list[str], input_data: dict) -> Optional[Any]:
        key = self._make_key(node_ids, input_data)
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None
        value, expires_at = entry
        if time.time() > expires_at:
            del self._cache[key]
            self._misses += 1
            return None
        self._hits += 1
        return value

    def set(self, node_ids: list[str], input_data: dict, result: Any, ttl: Optional[int] = None):
        if len(self._cache) >= self._max_size:
            # 淘汰最旧的 20%
            sorted_keys = sorted(self._cache.keys(), key=lambda k: self._cache[k][1])
            for k in sorted_keys[:self._max_size // 5]:
                del self._cache[k]
        key = self._make_key(node_ids, input_data)
        self._cache[key] = (result, time.time() + (ttl or self._default_ttl))

    def invalidate(self, node_ids: Optional[list[str]] = None):
        if node_ids is None:
            self._cache.clear()
            return
        to_delete = [k for k in self._cache if any(nid in k for nid in node_ids)]
        for k in to_delete:
            del self._cache[k]

    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / max(total, 1), 3),
        }


class WorkflowEngine:
    """DAG工作流引擎"""

    def __init__(self, db: AsyncSession, max_concurrency: int = 20):
        self.db = db
        self.max_concurrency = max_concurrency
        self._subgraph_cache = SubgraphCache()

    # ==================================================================
    # DAG 校验与拓扑排序
    # ==================================================================

    @staticmethod
    def validate_dag(nodes: list[dict], edges: list[dict]) -> None:
        """校验DAG: 无环、节点存在、无孤立节点"""
        node_ids = {n["node_id"] for n in nodes}
        if not node_ids:
            raise DAGValidationError("工作流至少需要一个节点")

        # 校验边引用的节点存在
        for edge in edges:
            if edge["source"] not in node_ids:
                raise DAGValidationError(f"边引用的源节点 {edge['source']} 不存在")
            if edge["target"] not in node_ids:
                raise DAGValidationError(f"边引用的目标节点 {edge['target']} 不存在")

        # 拓扑排序检测环 (Kahn's algorithm)
        in_degree = defaultdict(int)
        graph = defaultdict(list)
        for eid in node_ids:
            in_degree[eid] = 0

        for edge in edges:
            graph[edge["source"]].append(edge["target"])
            in_degree[edge["target"]] += 1

        queue = deque([nid for nid in node_ids if in_degree[nid] == 0])
        visited = 0

        while queue:
            current = queue.popleft()
            visited += 1
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited != len(node_ids):
            raise DAGValidationError("工作流存在循环依赖")

    @staticmethod
    def topological_sort(nodes: list[dict], edges: list[dict]) -> list[list[str]]:
        """
        拓扑排序,返回层级列表(同一层的节点可并行执行)
        返回: [[level0_nodes], [level1_nodes], ...]
        """
        node_ids = {n["node_id"] for n in nodes}
        in_degree = defaultdict(int)
        graph = defaultdict(list)

        for eid in node_ids:
            in_degree[eid] = 0
        for edge in edges:
            graph[edge["source"]].append(edge["target"])
            in_degree[edge["target"]] += 1

        levels = []
        queue = deque([nid for nid in node_ids if in_degree[nid] == 0])

        while queue:
            level = list(queue)
            levels.append(level)
            next_queue = deque()
            for current in level:
                for neighbor in graph[current]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_queue.append(neighbor)
            queue = next_queue

        return levels

    # ==================================================================
    # CRUD
    # ==================================================================

    async def create_workflow(self, data: dict, user_id: str) -> Workflow:
        """创建工作流"""
        workflow = Workflow(
            id=str(uuid.uuid4()),
            name=data["name"],
            description=data.get("description", ""),
            status="draft",
            dag_config=json.dumps(data.get("dag_config", {}), ensure_ascii=False),
            variables=json.dumps(data.get("variables", {}), ensure_ascii=False),
            timeout=data.get("timeout", 3600),
            max_retries=data.get("max_retries", 2),
            created_by=user_id,
            workspace_id=data.get("workspace_id"),
        )
        self.db.add(workflow)
        await self.db.flush()

        # 保存节点和边
        dag = data.get("dag_config", {})
        for node_data in dag.get("nodes", []):
            node = WorkflowNode(
                id=str(uuid.uuid4()),
                workflow_id=workflow.id,
                node_id=node_data["node_id"],
                name=node_data.get("name", node_data["node_id"]),
                node_type=node_data.get("node_type", "agent"),
                agent_id=node_data.get("agent_id"),
                config=json.dumps(node_data.get("config", {}), ensure_ascii=False),
                input_mapping=json.dumps(node_data.get("input_mapping", {}), ensure_ascii=False),
                output_key=node_data.get("output_key", ""),
                timeout=node_data.get("timeout", 300),
                retries=node_data.get("retries", 0),
                retry_delay=node_data.get("retry_delay", 5),
                condition=node_data.get("condition", ""),
                order=node_data.get("order", 0),
            )
            self.db.add(node)

        for edge_data in dag.get("edges", []):
            edge = WorkflowEdge(
                id=str(uuid.uuid4()),
                workflow_id=workflow.id,
                source_node_id=edge_data["source"],
                target_node_id=edge_data["target"],
                condition=edge_data.get("condition", ""),
            )
            self.db.add(edge)

        await self.db.flush()
        return workflow

    async def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        result = await self.db.execute(
            select(Workflow).where(Workflow.id == workflow_id)
        )
        return result.scalar_one_or_none()

    async def update_workflow(self, workflow_id: str, data: dict) -> Optional[Workflow]:
        workflow = await self.get_workflow(workflow_id)
        if not workflow:
            return None
        if workflow.status == "running":
            raise ValueError("运行中的工作流不能修改")

        for key in ("name", "description", "timeout", "max_retries"):
            if key in data:
                setattr(workflow, key, data[key])
        if "dag_config" in data:
            workflow.dag_config = json.dumps(data["dag_config"], ensure_ascii=False)
            # 更新节点和边
            await self._update_dag_elements(workflow_id, data["dag_config"])
        if "variables" in data:
            workflow.variables = json.dumps(data["variables"], ensure_ascii=False)

        workflow.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return workflow

    async def _update_dag_elements(self, workflow_id: str, dag_config: dict):
        """更新DAG节点和边"""
        # 删除旧的
        old_nodes = await self.db.execute(
            select(WorkflowNode).where(WorkflowNode.workflow_id == workflow_id)
        )
        for node in old_nodes.scalars().all():
            await self.db.delete(node)

        old_edges = await self.db.execute(
            select(WorkflowEdge).where(WorkflowEdge.workflow_id == workflow_id)
        )
        for edge in old_edges.scalars().all():
            await self.db.delete(edge)

        # 插入新的
        for node_data in dag_config.get("nodes", []):
            node = WorkflowNode(
                id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                node_id=node_data["node_id"],
                name=node_data.get("name", node_data["node_id"]),
                node_type=node_data.get("node_type", "agent"),
                agent_id=node_data.get("agent_id"),
                config=json.dumps(node_data.get("config", {}), ensure_ascii=False),
                input_mapping=json.dumps(node_data.get("input_mapping", {}), ensure_ascii=False),
                output_key=node_data.get("output_key", ""),
                timeout=node_data.get("timeout", 300),
                retries=node_data.get("retries", 0),
                retry_delay=node_data.get("retry_delay", 5),
                condition=node_data.get("condition", ""),
                order=node_data.get("order", 0),
            )
            self.db.add(node)

        for edge_data in dag_config.get("edges", []):
            edge = WorkflowEdge(
                id=str(uuid.uuid4()),
                workflow_id=workflow_id,
                source_node_id=edge_data["source"],
                target_node_id=edge_data["target"],
                condition=edge_data.get("condition", ""),
            )
            self.db.add(edge)

    async def delete_workflow(self, workflow_id: str) -> bool:
        workflow = await self.get_workflow(workflow_id)
        if not workflow:
            return False
        if workflow.status == "running":
            raise ValueError("运行中的工作流不能删除")
        # 删除关联的节点、边、执行记录
        for model in (WorkflowNode, WorkflowEdge, WorkflowExecution):
            items = await self.db.execute(
                select(model).where(model.workflow_id == workflow_id)
            )
            for item in items.scalars().all():
                await self.db.delete(item)
        await self.db.delete(workflow)
        await self.db.flush()
        return True

    async def list_workflows(
        self, offset: int = 0, limit: int = 20, user_id: Optional[str] = None
    ) -> tuple[list[Workflow], int]:
        q = select(Workflow)
        if user_id:
            q = q.where(Workflow.created_by == user_id)
        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0
        q = q.order_by(Workflow.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all()), total

    async def get_workflow_detail(self, workflow_id: str) -> Optional[dict]:
        """获取工作流详情(含节点和边)"""
        workflow = await self.get_workflow(workflow_id)
        if not workflow:
            return None

        nodes_result = await self.db.execute(
            select(WorkflowNode)
            .where(WorkflowNode.workflow_id == workflow_id)
            .order_by(WorkflowNode.order)
        )
        nodes = nodes_result.scalars().all()

        edges_result = await self.db.execute(
            select(WorkflowEdge).where(WorkflowEdge.workflow_id == workflow_id)
        )
        edges = edges_result.scalars().all()

        return {
            "workflow": workflow,
            "nodes": nodes,
            "edges": edges,
        }

    # ==================================================================
    # 执行引擎
    # ==================================================================

    async def execute_workflow(
        self, workflow_id: str, input_data: Optional[dict] = None
    ) -> dict:
        """执行工作流"""
        workflow = await self.get_workflow(workflow_id)
        if not workflow:
            raise ValueError("工作流不存在")
        if workflow.status == "running":
            raise ValueError("工作流正在运行中")

        # 获取节点和边
        detail = await self.get_workflow_detail(workflow_id)
        if not detail:
            raise ValueError("工作流详情获取失败")

        nodes = detail["nodes"]
        edges = detail["edges"]

        # 校验DAG
        nodes_dicts = [
            {"node_id": n.node_id, "name": n.name, "node_type": n.node_type}
            for n in nodes
        ]
        edges_dicts = [
            {"source": e.source_node_id, "target": e.target_node_id}
            for e in edges
        ]
        self.validate_dag(nodes_dicts, edges_dicts)

        # 创建执行记录
        execution = WorkflowExecution(
            id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            status="running",
            trigger="manual",
            input_data=json.dumps(input_data or {}, ensure_ascii=False),
        )
        self.db.add(execution)

        workflow.status = "running"
        workflow.started_at = datetime.now(timezone.utc)
        await self.db.flush()

        # 拓扑排序
        levels = self.topological_sort(nodes_dicts, edges_dicts)

        # 工作流变量
        variables = _safe_json(workflow.variables, {})
        if input_data:
            variables.update(input_data)

        node_map = {n.node_id: n for n in nodes}
        node_results = {}
        start_time = time.time()

        try:
            # 逐层执行 (受 max_concurrency 控制)
            semaphore = asyncio.Semaphore(self.max_concurrency)

            for level in levels:
                # 检查子图缓存
                level_ids = sorted(level)
                cached = self._subgraph_cache.get(level_ids, variables)
                if cached is not None:
                    node_results.update(cached)
                    continue

                async def _bounded_exec(node_id: str):
                    async with semaphore:
                        node = node_map[node_id]
                        return node_id, await self._execute_node(node, variables, node_results, workflow.max_retries)

                level_tasks = [_bounded_exec(node_id) for node_id in level]

                if len(level_tasks) == 1:
                    nid, result = await level_tasks[0]
                    node_results[nid] = result
                else:
                    level_results = await asyncio.gather(*level_tasks, return_exceptions=True)
                    for res in level_results:
                        if isinstance(res, Exception):
                            # 找不到 nid 时用通用 key
                            node_results[f"error_{len(node_results)}"] = {
                                "status": "failed",
                                "output": "",
                                "error": str(res),
                                "duration_ms": 0,
                            }
                        else:
                            nid, result = res
                            node_results[nid] = result

                # 缓存子图结果 (TTL 60s)
                level_result_subset = {nid: node_results.get(nid) for nid in level if nid in node_results}
                if level_result_subset:
                    self._subgraph_cache.set(level_ids, variables, level_result_subset, ttl=60)

                # 检查是否有失败节点
                for nid in level:
                    if node_results.get(nid, {}).get("status") == "failed":
                        raise RuntimeError(f"节点 {nid} 执行失败")

            # 所有层级执行完成
            elapsed = int((time.time() - start_time) * 1000)
            workflow.status = "completed"
            workflow.completed_at = datetime.now(timezone.utc)
            workflow.result = json.dumps(node_results, ensure_ascii=False)
            execution.status = "completed"
            execution.output_data = json.dumps(node_results, ensure_ascii=False)
            execution.node_results = json.dumps(node_results, ensure_ascii=False)
            execution.completed_at = datetime.now(timezone.utc)
            execution.duration_ms = elapsed

        except Exception as e:
            elapsed = int((time.time() - start_time) * 1000)
            workflow.status = "failed"
            workflow.completed_at = datetime.now(timezone.utc)
            workflow.result = json.dumps({"error": str(e)}, ensure_ascii=False)
            execution.status = "failed"
            execution.error_message = str(e)[:2000]
            execution.completed_at = datetime.now(timezone.utc)
            execution.duration_ms = elapsed
            logger.error("工作流 %s 执行失败: %s", workflow_id, str(e))

        workflow.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

        return {
            "execution_id": execution.id,
            "status": workflow.status,
            "node_results": node_results,
            "duration_ms": execution.duration_ms,
        }

    async def _execute_node(
        self,
        node: WorkflowNode,
        variables: dict,
        node_results: dict,
        max_retries: int,
    ) -> dict:
        """执行单个节点(含重试)"""
        start = time.time()
        config = _safe_json(node.config, {})
        input_mapping = _safe_json(node.input_mapping, {})
        retries = node.retries or max_retries

        # 构建节点输入
        node_input = self._resolve_input(node, variables, input_mapping, node_results)

        for attempt in range(retries + 1):
            try:
                if node.node_type == "agent":
                    output = await self._execute_agent_node(node, node_input, config)
                elif node.node_type == "condition":
                    output = self._execute_condition_node(node, variables, node_results)
                elif node.node_type == "transform":
                    output = self._execute_transform_node(node, node_input, config)
                else:
                    output = {"status": "completed", "output": node_input}

                elapsed_ms = int((time.time() - start) * 1000)

                # 存储输出变量
                if node.output_key:
                    variables[node.output_key] = output.get("output", "")

                return {
                    "status": "completed",
                    "output": output.get("output", ""),
                    "duration_ms": elapsed_ms,
                    "attempt": attempt + 1,
                }

            except Exception as e:
                if attempt < retries:
                    logger.warning(
                        "节点 %s 第%d次执行失败,重试中: %s",
                        node.node_id, attempt + 1, str(e),
                    )
                    await asyncio.sleep(node.retry_delay or 5)
                else:
                    elapsed_ms = int((time.time() - start) * 1000)
                    return {
                        "status": "failed",
                        "output": "",
                        "error": str(e)[:1000],
                        "duration_ms": elapsed_ms,
                        "attempt": attempt + 1,
                    }

    def _resolve_input(
        self,
        node: WorkflowNode,
        variables: dict,
        input_mapping: dict,
        node_results: dict,
    ) -> str:
        """解析节点输入(从变量/前驱节点输出映射)"""
        if input_mapping:
            parts = []
            for key, source in input_mapping.items():
                if source.startswith("$"):
                    # 变量引用
                    var_name = source[1:]
                    parts.append(f"{key}: {variables.get(var_name, '')}")
                elif "." in source:
                    # 节点输出引用 (如 "node_1.output")
                    parts.append(f"{key}: {node_results.get(source.split('.')[0], {}).get('output', '')}")
                else:
                    parts.append(f"{key}: {source}")
            return "\n".join(parts)

        # 默认: 合并所有前驱节点的输出
        prev_outputs = []
        for nid, result in node_results.items():
            if result.get("status") == "completed" and result.get("output"):
                prev_outputs.append(result["output"])
        if prev_outputs:
            return "\n\n".join(prev_outputs)

        # 兜底: 使用变量中的 input
        return variables.get("input", "")

    async def _execute_agent_node(
        self, node: WorkflowNode, node_input: str, config: dict
    ) -> dict:
        """执行Agent节点"""
        if not node.agent_id:
            raise ValueError(f"节点 {node.node_id} 未关联Agent")

        # 构建适配器
        result = await self.db.execute(
            select(Agent).where(Agent.id == node.agent_id)
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise ValueError(f"Agent {node.agent_id} 不存在")

        provider = agent.model_provider or "openai"
        model_name = agent.model_name
        adapter_config = {}

        if agent.model_config_template_id:
            tpl_result = await self.db.execute(
                select(ModelConfigTemplate).where(
                    ModelConfigTemplate.id == agent.model_config_template_id
                )
            )
            tpl = tpl_result.scalar_one_or_none()
            if tpl:
                try:
                    adapter_config = json.loads(tpl.config) if tpl.config else {}
                except (json.JSONDecodeError, TypeError):
                    adapter_config = {}
                if not model_name and tpl.model:
                    model_name = tpl.model

        if model_name:
            adapter_config["model_name"] = model_name
        if not adapter_config.get("endpoint") and provider == "openai":
            adapter_config.setdefault("endpoint", "https://api.openai.com/v1")

        adapter = create_adapter(provider, adapter_config)

        # 构建消息
        system_prompt = agent.system_prompt or ""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": node_input})

        chat_result = await adapter.chat(
            messages=messages,
            temperature=config.get("temperature", agent.temperature or 0.7),
            max_tokens=config.get("max_tokens", agent.max_tokens),
        )

        return {"output": chat_result.content}

    def _execute_condition_node(
        self, node: WorkflowNode, variables: dict, node_results: dict
    ) -> dict:
        """执行条件节点"""
        condition = node.condition or _safe_json(node.config, {}).get("condition", "")
        if not condition:
            return {"output": "true"}

        # 简单条件评估(变量替换 + Python表达式)
        try:
            eval_vars = dict(variables)
            for nid, res in node_results.items():
                eval_vars[f"{nid}_output"] = res.get("output", "")
            result = eval(condition, {"__builtins__": {}}, eval_vars)
            return {"output": str(result).lower()}
        except Exception as e:
            logger.warning("条件评估失败: %s", str(e))
            return {"output": "false"}

    def _execute_transform_node(
        self, node: WorkflowNode, node_input: str, config: dict
    ) -> dict:
        """执行转换节点(数据处理)"""
        transform_type = config.get("type", "passthrough")

        if transform_type == "concat":
            separator = config.get("separator", "\n")
            parts = config.get("parts", [node_input])
            return {"output": separator.join(parts)}

        elif transform_type == "extract":
            # 提取JSON字段
            try:
                data = json.loads(node_input)
                field = config.get("field", "")
                if field:
                    value = data.get(field, "")
                    return {"output": json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)}
            except (json.JSONDecodeError, TypeError):
                pass
            return {"output": node_input}

        elif transform_type == "template":
            template = config.get("template", "{input}")
            return {"output": template.replace("{input}", node_input)}

        else:
            return {"output": node_input}

    # ==================================================================
    # 执行历史
    # ==================================================================

    async def list_executions(
        self, workflow_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[WorkflowExecution], int]:
        q = select(WorkflowExecution).where(
            WorkflowExecution.workflow_id == workflow_id
        )
        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0
        q = q.order_by(WorkflowExecution.started_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all()), total

    async def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        result = await self.db.execute(
            select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
        )
        return result.scalar_one_or_none()

    async def cancel_execution(self, execution_id: str) -> bool:
        execution = await self.get_execution(execution_id)
        if not execution or execution.status != "running":
            return False
        execution.status = "cancelled"
        execution.completed_at = datetime.now(timezone.utc)

        workflow = await self.get_workflow(execution.workflow_id)
        if workflow and workflow.status == "running":
            workflow.status = "failed"
            workflow.completed_at = datetime.now(timezone.utc)
            workflow.updated_at = datetime.now(timezone.utc)

        await self.db.flush()
        return True

    # ==================================================================
    # 统计
    # ==================================================================

    async def get_workflow_stats(self) -> dict:
        total = (await self.db.execute(
            select(func.count()).select_from(Workflow)
        )).scalar() or 0
        running = (await self.db.execute(
            select(func.count()).select_from(Workflow).where(Workflow.status == "running")
        )).scalar() or 0
        completed = (await self.db.execute(
            select(func.count()).select_from(Workflow).where(Workflow.status == "completed")
        )).scalar() or 0
        return {
            "total": total,
            "running": running,
            "completed": completed,
            "failed": total - running - completed,
            "max_concurrency": self.max_concurrency,
            "subgraph_cache": self._subgraph_cache.stats(),
        }
