"""
工作流 API - DAG工作流CRUD + 执行 + 历史
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.workflow_engine import WorkflowEngine, DAGValidationError
from app.services.auth_service import get_current_user

router = APIRouter()


# ==================================================================
# 工作流 CRUD
# ==================================================================

@router.post("", status_code=201)
async def create_workflow(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """创建工作流"""
    if not data.get("name"):
        raise HTTPException(status_code=400, detail="工作流名称不能为空")

    # 如果有dag_config,校验DAG
    dag_config = data.get("dag_config", {})
    nodes = dag_config.get("nodes", [])
    edges = dag_config.get("edges", [])

    engine = WorkflowEngine(db)
    try:
        if nodes:
            WorkflowEngine.validate_dag(
                [{"node_id": n["node_id"], "name": n.get("name", n["node_id"]),
                  "node_type": n.get("node_type", "agent")} for n in nodes],
                [{"source": e["source"], "target": e["target"]} for e in edges],
            )
    except DAGValidationError as e:
        raise HTTPException(status_code=400, detail=f"DAG校验失败: {str(e)}")

    workflow = await engine.create_workflow(data, str(current_user.id))
    return {"id": workflow.id, "name": workflow.name, "status": workflow.status}


@router.get("")
async def list_workflows(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """列出工作流"""
    engine = WorkflowEngine(db)
    offset = (page - 1) * page_size
    workflows, total = await engine.list_workflows(offset, page_size, str(current_user.id))
    return {
        "items": [
            {
                "id": w.id, "name": w.name, "description": w.description,
                "status": w.status, "created_at": str(w.created_at),
                "started_at": str(w.started_at) if w.started_at else None,
                "completed_at": str(w.completed_at) if w.completed_at else None,
            }
            for w in workflows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取工作流详情(含节点和边)"""
    engine = WorkflowEngine(db)
    detail = await engine.get_workflow_detail(workflow_id)
    if not detail:
        raise HTTPException(status_code=404, detail="工作流不存在")

    workflow = detail["workflow"]
    return {
        "id": workflow.id,
        "name": workflow.name,
        "description": workflow.description,
        "status": workflow.status,
        "dag_config": {
            "nodes": [
                {
                    "node_id": n.node_id, "name": n.name, "node_type": n.node_type,
                    "agent_id": n.agent_id, "config": n.config,
                    "input_mapping": n.input_mapping, "output_key": n.output_key,
                    "timeout": n.timeout, "retries": n.retries, "condition": n.condition,
                    "order": n.order,
                }
                for n in detail["nodes"]
            ],
            "edges": [
                {"source": e.source_node_id, "target": e.target_node_id, "condition": e.condition}
                for e in detail["edges"]
            ],
        },
        "variables": workflow.variables,
        "timeout": workflow.timeout,
        "max_retries": workflow.max_retries,
        "result": workflow.result,
        "created_at": str(workflow.created_at),
        "started_at": str(workflow.started_at) if workflow.started_at else None,
        "completed_at": str(workflow.completed_at) if workflow.completed_at else None,
    }


@router.put("/{workflow_id}")
async def update_workflow(
    workflow_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """更新工作流"""
    engine = WorkflowEngine(db)

    # 校验DAG
    dag_config = data.get("dag_config")
    if dag_config:
        nodes = dag_config.get("nodes", [])
        edges = dag_config.get("edges", [])
        if nodes:
            try:
                WorkflowEngine.validate_dag(
                    [{"node_id": n["node_id"], "name": n.get("name", n["node_id"]),
                      "node_type": n.get("node_type", "agent")} for n in nodes],
                    [{"source": e["source"], "target": e["target"]} for e in edges],
                )
            except DAGValidationError as e:
                raise HTTPException(status_code=400, detail=f"DAG校验失败: {str(e)}")

    workflow = await engine.update_workflow(workflow_id, data)
    if not workflow:
        raise HTTPException(status_code=404, detail="工作流不存在")
    return {"id": workflow.id, "name": workflow.name, "status": workflow.status}


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """删除工作流"""
    engine = WorkflowEngine(db)
    try:
        deleted = await engine.delete_workflow(workflow_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="工作流不存在")


# ==================================================================
# 执行
# ==================================================================

@router.post("/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: str,
    data: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """执行工作流"""
    engine = WorkflowEngine(db)
    try:
        result = await engine.execute_workflow(workflow_id, data or {})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DAGValidationError as e:
        raise HTTPException(status_code=400, detail=f"DAG校验失败: {str(e)}")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return result


# ==================================================================
# 执行历史
# ==================================================================

@router.get("/{workflow_id}/executions")
async def list_executions(
    workflow_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """列出执行历史"""
    engine = WorkflowEngine(db)
    offset = (page - 1) * page_size
    executions, total = await engine.list_executions(workflow_id, offset, page_size)
    return {
        "items": [
            {
                "id": e.id, "status": e.status, "trigger": e.trigger,
                "duration_ms": e.duration_ms, "error_message": e.error_message,
                "started_at": str(e.started_at), "completed_at": str(e.completed_at),
            }
            for e in executions
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/executions/{execution_id}")
async def get_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取执行详情"""
    engine = WorkflowEngine(db)
    execution = await engine.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    return {
        "id": execution.id,
        "workflow_id": execution.workflow_id,
        "status": execution.status,
        "trigger": execution.trigger,
        "input_data": execution.input_data,
        "output_data": execution.output_data,
        "node_results": execution.node_results,
        "error_message": execution.error_message,
        "duration_ms": execution.duration_ms,
        "started_at": str(execution.started_at),
        "completed_at": str(execution.completed_at) if execution.completed_at else None,
    }


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """取消执行"""
    engine = WorkflowEngine(db)
    cancelled = await engine.cancel_execution(execution_id)
    if not cancelled:
        raise HTTPException(status_code=400, detail="无法取消(未找到或未在运行中)")
    return {"status": "cancelled"}


# ==================================================================
# 统计
# ==================================================================

@router.get("/stats/overview")
async def get_workflow_stats(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取工作流统计"""
    engine = WorkflowEngine(db)
    return await engine.get_workflow_stats()
