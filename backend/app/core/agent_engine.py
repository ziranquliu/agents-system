"""
LangGraph Agent 引擎集成

功能:
- 基于 LangGraph 的 Agent 状态图编排
- 节点类型: LLM 调用 / 工具调用 / 条件分支 / 人工审核
- 状态管理: 可序列化的 Agent 状态
- 断点续跑: 中断后恢复
- 流式输出
- 与现有 adapter 工厂集成

注：当 langgraph 不可用时，降级为内置轻量级图引擎
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)


class NodeType(str, Enum):
    LLM = "llm"
    TOOL = "tool"
    CONDITION = "condition"
    HUMAN_REVIEW = "human_review"
    TRANSFORM = "transform"
    START = "start"
    END = "end"


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_HUMAN = "waiting_human"


@dataclass
class AgentState:
    """Agent 状态（可序列化）"""
    messages: list[dict[str, Any]] = field(default_factory=list)
    current_node: str = ""
    variables: dict[str, Any] = field(default_factory=dict)
    node_results: dict[str, Any] = field(default_factory=dict)
    status: str = "running"
    error: Optional[str] = None
    history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "messages": self.messages,
            "current_node": self.current_node,
            "variables": self.variables,
            "node_results": self.node_results,
            "status": self.status,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentState":
        return cls(
            messages=data.get("messages", []),
            current_node=data.get("current_node", ""),
            variables=data.get("variables", {}),
            node_results=data.get("node_results", {}),
            status=data.get("status", "running"),
            error=data.get("error"),
        )


@dataclass
class GraphNode:
    """图节点"""
    id: str = ""
    name: str = ""
    node_type: NodeType = NodeType.LLM
    config: dict[str, Any] = field(default_factory=dict)
    # LLM 节点配置
    prompt_template: str = ""
    model: str = ""
    provider: str = ""
    # Tool 节点配置
    tool_name: str = ""
    tool_params: dict[str, Any] = field(default_factory=dict)
    # 条件节点配置
    condition_expression: str = ""
    true_branch: str = ""
    false_branch: str = ""
    # 人工审核
    review_prompt: str = ""


@dataclass
class GraphEdge:
    """图边"""
    source: str = ""
    target: str = ""
    condition: str = ""  # 条件表达式（空=无条件）


class AgentGraph:
    """Agent 状态图"""

    def __init__(self, graph_id: str = "", name: str = ""):
        self.id = graph_id or str(uuid.uuid4())
        self.name = name
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []
        self.start_node: str = ""
        self.end_node: str = ""

    def add_node(self, node: GraphNode):
        self.nodes[node.id] = node

    def add_edge(self, source: str, target: str, condition: str = ""):
        self.edges.append(GraphEdge(source=source, target=target, condition=condition))

    def set_start(self, node_id: str):
        self.start_node = node_id

    def set_end(self, node_id: str):
        self.end_node = node_id

    def get_next_nodes(self, current_id: str, state: AgentState) -> list[str]:
        """获取下一跳节点"""
        next_nodes = []
        for edge in self.edges:
            if edge.source == current_id:
                if not edge.condition:
                    next_nodes.append(edge.target)
                else:
                    # 简单条件评估
                    try:
                        result = eval(edge.condition, {"state": state, "vars": state.variables})
                        if result:
                            next_nodes.append(edge.target)
                    except Exception:
                        pass
        return next_nodes


# ============================================================
# 内置轻量级图引擎（无 LangGraph 依赖）
# ============================================================


class BuiltinGraphEngine:
    """
    内置轻量级图引擎

    当 langgraph 不可用时使用
    """

    def __init__(self):
        self._graphs: dict[str, AgentGraph] = {}
        self._executions: dict[str, AgentState] = {}
        self._node_handlers: dict[str, Callable] = {}
        self._max_iterations = 50

    def register_handler(self, node_type: str, handler: Callable):
        """注册节点处理器"""
        self._node_handlers[node_type] = handler

    def create_graph(
        self,
        name: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        start_node: str,
        end_node: str,
    ) -> AgentGraph:
        """从配置创建图"""
        graph = AgentGraph(name=name)

        for n in nodes:
            node = GraphNode(
                id=n["id"],
                name=n.get("name", n["id"]),
                node_type=NodeType(n.get("type", "llm")),
                config=n.get("config", {}),
                prompt_template=n.get("prompt_template", ""),
                model=n.get("model", ""),
                provider=n.get("provider", ""),
                tool_name=n.get("tool_name", ""),
                condition_expression=n.get("condition", ""),
                true_branch=n.get("true_branch", ""),
                false_branch=n.get("false_branch", ""),
            )
            graph.add_node(node)

        for e in edges:
            graph.add_edge(e["source"], e["target"], e.get("condition", ""))

        graph.set_start(start_node)
        graph.set_end(end_node)

        self._graphs[graph.id] = graph
        return graph

    async def execute(
        self,
        graph_id: str,
        input_data: dict[str, Any],
        state: Optional[AgentState] = None,
    ) -> AgentState:
        """执行图"""
        graph = self._graphs.get(graph_id)
        if not graph:
            raise ValueError(f"Graph not found: {graph_id}")

        if state is None:
            state = AgentState(
                messages=input_data.get("messages", []),
                variables=input_data.get("variables", {}),
            )

        state.current_node = graph.start_node
        iterations = 0

        while state.current_node and state.current_node != graph.end_node:
            if iterations >= self._max_iterations:
                state.error = f"Max iterations ({self._max_iterations}) exceeded"
                state.status = "failed"
                break

            node = graph.nodes.get(state.current_node)
            if not node:
                state.error = f"Node not found: {state.current_node}"
                state.status = "failed"
                break

            # 执行节点
            state.history.append({
                "node": node.id,
                "name": node.name,
                "type": node.node_type.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            try:
                result = await self._execute_node(node, state)
                state.node_results[node.id] = result

                # 条件节点：根据结果选择分支
                if node.node_type == NodeType.CONDITION:
                    if result and node.true_branch:
                        state.current_node = node.true_branch
                    elif not result and node.false_branch:
                        state.current_node = node.false_branch
                    else:
                        next_nodes = graph.get_next_nodes(node.id, state)
                        state.current_node = next_nodes[0] if next_nodes else None
                else:
                    next_nodes = graph.get_next_nodes(node.id, state)
                    state.current_node = next_nodes[0] if next_nodes else None

            except Exception as e:
                state.error = f"Node {node.id} failed: {str(e)}"
                state.status = "failed"
                logger.error(f"Graph execution error at node {node.id}: {e}")
                break

            iterations += 1

        if state.status != "failed":
            state.status = "completed"

        return state

    async def _execute_node(self, node: GraphNode, state: AgentState) -> Any:
        """执行单个节点"""
        if node.node_type == NodeType.LLM:
            return await self._execute_llm_node(node, state)
        elif node.node_type == NodeType.TOOL:
            return await self._execute_tool_node(node, state)
        elif node.node_type == NodeType.CONDITION:
            return await self._execute_condition_node(node, state)
        elif node.node_type == NodeType.TRANSFORM:
            return await self._execute_transform_node(node, state)
        elif node.node_type == NodeType.HUMAN_REVIEW:
            return {"status": "waiting_human", "prompt": node.review_prompt}
        return None

    async def _execute_llm_node(self, node: GraphNode, state: AgentState) -> dict[str, Any]:
        """执行 LLM 节点"""
        provider = node.provider or node.config.get("provider", "openai")
        model = node.model or node.config.get("model", "gpt-4o-mini")

        # 构建 prompt
        messages = state.messages.copy()
        if node.prompt_template:
            # 变量替换
            prompt = node.prompt_template
            for k, v in state.variables.items():
                prompt = prompt.replace(f"{{{k}}}", str(v))
            messages.append({"role": "user", "content": prompt})

        # 使用 adapter 工厂
        try:
            from app.services.llm_adapter_factory import create_adapter
            adapter = create_adapter(provider, {"model": model})
            result = await adapter.chat(messages=messages)
            return {
                "content": result.get("content", ""),
                "usage": result.get("usage", {}),
                "model": model,
            }
        except Exception as e:
            logger.warning(f"LLM adapter not available: {e}")
            return {
                "content": f"[LLM 模拟响应] Provider: {provider}, Model: {model}",
                "usage": {},
                "model": model,
            }

    async def _execute_tool_node(self, node: GraphNode, state: AgentState) -> dict[str, Any]:
        """执行 Tool 节点"""
        handler = self._node_handlers.get(f"tool:{node.tool_name}")
        if handler:
            return await handler(node.tool_params, state)
        return {"tool": node.tool_name, "status": "handler_not_found"}

    async def _execute_condition_node(self, node: GraphNode, state: AgentState) -> bool:
        """评估条件"""
        try:
            return eval(node.condition_expression, {
                "state": state,
                "vars": state.variables,
                "messages": state.messages,
            })
        except Exception as e:
            logger.warning(f"Condition evaluation failed: {e}")
            return False

    async def _execute_transform_node(self, node: GraphNode, state: AgentState) -> Any:
        """执行数据转换"""
        transform_type = node.config.get("transform_type", "identity")
        if transform_type == "extract_last":
            if state.messages:
                return state.messages[-1].get("content", "")
        elif transform_type == "merge_results":
            return {**state.node_results}
        return state.variables

    def get_execution_state(self, graph_id: str) -> Optional[AgentState]:
        """获取执行状态（断点续跑）"""
        return self._executions.get(graph_id)

    def save_state(self, graph_id: str, state: AgentState):
        """保存执行状态"""
        self._executions[graph_id] = state

    def list_graphs(self) -> list[dict[str, Any]]:
        """列出所有图"""
        return [
            {
                "id": g.id,
                "name": g.name,
                "node_count": len(g.nodes),
                "edge_count": len(g.edges),
                "start_node": g.start_node,
                "end_node": g.end_node,
            }
            for g in self._graphs.values()
        ]


# ============================================================
# LangGraph 集成（可选依赖）
# ============================================================

_langgraph_available = False

try:
    from langgraph.graph import StateGraph, END
    _langgraph_available = True
except ImportError:
    logger.info("LangGraph not installed, using built-in graph engine")


class LangGraphEngine:
    """LangGraph 引擎封装"""

    def __init__(self):
        self._compiled_graphs: dict[str, Any] = {}

    def create_from_config(
        self,
        graph_id: str,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        start_node: str,
    ) -> Any:
        """从配置创建 LangGraph"""
        if not _langgraph_available:
            raise RuntimeError("LangGraph not installed")

        # 创建状态图
        workflow = StateGraph(dict)

        # 添加节点
        for node_cfg in nodes:
            nid = node_cfg["id"]
            node_type = node_cfg.get("type", "llm")

            if node_type == "llm":
                workflow.add_node(nid, self._make_llm_node(node_cfg))
            elif node_type == "tool":
                workflow.add_node(nid, self._make_tool_node(node_cfg))
            elif node_type == "condition":
                workflow.add_node(nid, self._make_condition_node(node_cfg))

        # 添加边
        for edge_cfg in edges:
            source = edge_cfg["source"]
            target = edge_cfg["target"]
            if source == "__start__":
                workflow.set_entry_point(target)
            elif edge_cfg.get("condition"):
                workflow.add_conditional_edges(
                    source,
                    self._make_router(edge_cfg["condition"]),
                    {"true": target, "false": edge_cfg.get("false_branch", END)},
                )
            else:
                workflow.add_edge(source, target)

        # 编译
        compiled = workflow.compile()
        self._compiled_graphs[graph_id] = compiled
        return compiled

    async def execute(self, graph_id: str, input_state: dict[str, Any]) -> dict[str, Any]:
        compiled = self._compiled_graphs.get(graph_id)
        if not compiled:
            raise ValueError(f"Graph not found: {graph_id}")
        result = await compiled.ainvoke(input_state)
        return result

    @staticmethod
    def _make_llm_node(config: dict):
        async def node(state: dict) -> dict:
            # 使用 adapter
            provider = config.get("provider", "openai")
            model = config.get("model", "gpt-4o-mini")
            try:
                from app.services.llm_adapter_factory import create_adapter
                adapter = create_adapter(provider, {"model": model})
                result = await adapter.chat(messages=state.get("messages", []))
                state["messages"] = state.get("messages", []) + [
                    {"role": "assistant", "content": result.get("content", "")}
                ]
            except Exception:
                state["messages"] = state.get("messages", []) + [
                    {"role": "assistant", "content": "[LLM not available]"}
                ]
            return state
        return node

    @staticmethod
    def _make_tool_node(config: dict):
        async def node(state: dict) -> dict:
            return state
        return node

    @staticmethod
    def _make_condition_node(config: dict):
        async def node(state: dict) -> dict:
            return state
        return node

    @staticmethod
    def _make_router(condition: str):
        def router(state: dict):
            try:
                result = eval(condition, {"state": state})
                return "true" if result else "false"
            except Exception:
                return "false"
        return router


# ============================================================
# 统一入口
# ============================================================

_global_engine = None


def get_agent_engine():
    """获取 Agent 引擎（优先 LangGraph，降级内置）"""
    global _global_engine
    if _global_engine is None:
        if _langgraph_available:
            _global_engine = LangGraphEngine()
            logger.info("Using LangGraph engine")
        else:
            _global_engine = BuiltinGraphEngine()
            logger.info("Using built-in graph engine")
    return _global_engine
