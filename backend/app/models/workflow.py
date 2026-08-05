"""
工作流模型 - DAG工作流引擎
"""
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, Integer, DateTime, Float, func
from app.db.session import Base


class Workflow(Base):
    """工作流定义"""
    __tablename__ = "workflows"

    id = Column(String(36), primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    status = Column(String(20), default="draft")  # draft/running/completed/failed/paused
    dag_config = Column(Text, default="{}")  # JSON: nodes + edges definition
    variables = Column(Text, default="{}")  # JSON: workflow-level variables
    timeout = Column(Integer, default=3600)  # 总超时(秒)
    max_retries = Column(Integer, default=2)
    created_by = Column(String(36), nullable=False)
    workspace_id = Column(String(36), default=None)
    created_at = Column(DateTime, server_default=func.now(), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, onupdate=func.now(), default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, default=None)
    completed_at = Column(DateTime, default=None)
    result = Column(Text, default="{}")  # JSON: execution result


class WorkflowNode(Base):
    """工作流节点"""
    __tablename__ = "workflow_nodes"

    id = Column(String(36), primary_key=True)
    workflow_id = Column(String(36), nullable=False, index=True)
    node_id = Column(String(100), nullable=False)  # 节点标识(如 "node_1")
    name = Column(String(200), nullable=False)
    node_type = Column(String(50), nullable=False)  # agent/task/condition/subprocess
    agent_id = Column(String(36), default=None)  # 关联Agent(当node_type=agent)
    config = Column(Text, default="{}")  # JSON: 节点配置(模型/参数等)
    input_mapping = Column(Text, default="{}")  # JSON: 输入映射(从其他节点取值)
    output_key = Column(String(200), default="")  # 输出变量名
    timeout = Column(Integer, default=300)
    retries = Column(Integer, default=0)
    retry_delay = Column(Integer, default=5)
    condition = Column(Text, default="")  # 条件表达式(当node_type=condition)
    order = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now(), default=lambda: datetime.now(timezone.utc))


class WorkflowEdge(Base):
    """工作流边(节点间依赖)"""
    __tablename__ = "workflow_edges"

    id = Column(String(36), primary_key=True)
    workflow_id = Column(String(36), nullable=False, index=True)
    source_node_id = Column(String(100), nullable=False)
    target_node_id = Column(String(100), nullable=False)
    condition = Column(Text, default="")  # 条件表达式(条件分支)
    created_at = Column(DateTime, server_default=func.now(), default=lambda: datetime.now(timezone.utc))


class WorkflowExecution(Base):
    """工作流执行记录"""
    __tablename__ = "workflow_executions"

    id = Column(String(36), primary_key=True)
    workflow_id = Column(String(36), nullable=False, index=True)
    status = Column(String(20), default="running")  # running/completed/failed/cancelled
    trigger = Column(String(50), default="manual")  # manual/scheduled/api/event
    input_data = Column(Text, default="{}")  # JSON
    output_data = Column(Text, default="{}")  # JSON
    node_results = Column(Text, default="{}")  # JSON: {node_id: {status, output, duration}}
    error_message = Column(Text, default="")
    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, default=None)
    duration_ms = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now(), default=lambda: datetime.now(timezone.utc))
