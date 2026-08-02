"""
MCP 批量安装与跨 Agent 同步 API
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.auth_service import get_current_user
from app.services.mcp_batch_service import MCPBatchService

router = APIRouter(prefix="/api/v1/mcp-batch", tags=["MCP 批量安装"], dependencies=[Depends(get_current_user)])


def _binding_to_dict(b):
    return {
        "id": b.id,
        "mcp_server_id": b.mcp_server_id,
        "mcp_server_name": b.mcp_server_name,
        "agent_id": b.agent_id,
        "agent_name": b.agent_name,
        "sync_mode": b.sync_mode,
        "override_config": b.override_config,
        "override_protocol": b.override_protocol,
        "template_id": b.template_id,
        "status": b.status,
        "source_version": b.source_version,
        "synced_version": b.synced_version,
        "is_encrypted": b.is_encrypted,
        "last_synced_at": b.last_synced_at.isoformat() if b.last_synced_at else None,
        "sync_error": b.sync_error,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "updated_at": b.updated_at.isoformat() if b.updated_at else None,
    }


def _queue_to_dict(q):
    return {
        "id": q.id,
        "status": q.status,
        "total_items": q.total_items,
        "success_count": q.success_count or 0,
        "fail_count": q.fail_count or 0,
        "created_by": q.created_by,
        "created_at": q.created_at.isoformat() if q.created_at else None,
        "completed_at": q.completed_at.isoformat() if q.completed_at else None,
    }


def _item_to_dict(i):
    return {
        "id": i.id,
        "queue_id": i.queue_id,
        "mcp_server_id": i.mcp_server_id,
        "mcp_server_name": i.mcp_server_name,
        "agent_id": i.agent_id,
        "sync_mode": i.sync_mode,
        "status": i.status,
        "error_message": i.error_message,
        "started_at": i.started_at.isoformat() if i.started_at else None,
        "completed_at": i.completed_at.isoformat() if i.completed_at else None,
    }


# ----------------------------------------------------------
# 批量安装
# ----------------------------------------------------------

@router.post("/install", summary="创建 MCP 批量安装任务")
async def create_batch_install(data: dict, db: AsyncSession = Depends(get_db)):
    svc = MCPBatchService(db)
    queue = await svc.create_batch_install(
        mcp_ids=data["mcp_ids"],
        agent_ids=data["agent_ids"],
        sync_mode=data.get("sync_mode", "shared"),
        created_by=data.get("created_by", ""),
    )
    return {"success": True, "data": _queue_to_dict(queue)}


@router.post("/install/{queue_id}/execute", summary="执行批量安装")
async def execute_batch(queue_id: str, db: AsyncSession = Depends(get_db)):
    svc = MCPBatchService(db)
    try:
        queue = await svc.execute_batch(queue_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": _queue_to_dict(queue)}


@router.get("/install", summary="批量安装队列列表")
async def list_queues(offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
                      db: AsyncSession = Depends(get_db)):
    svc = MCPBatchService(db)
    items, total = await svc.list_queues(offset, limit)
    return {"success": True, "data": [_queue_to_dict(q) for q in items], "total": total}


@router.get("/install/{queue_id}", summary="获取队列详情")
async def get_queue(queue_id: str, db: AsyncSession = Depends(get_db)):
    svc = MCPBatchService(db)
    queue = await svc.get_queue(queue_id)
    if not queue:
        raise HTTPException(404, "队列不存在")
    return {"success": True, "data": _queue_to_dict(queue)}


@router.get("/install/{queue_id}/items", summary="获取队列安装项")
async def get_queue_items(queue_id: str, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1),
                          db: AsyncSession = Depends(get_db)):
    svc = MCPBatchService(db)
    items, total = await svc.get_queue_items(queue_id, offset, limit)
    return {"success": True, "data": [_item_to_dict(i) for i in items], "total": total}


# ----------------------------------------------------------
# 跨 Agent 绑定管理
# ----------------------------------------------------------

@router.get("/bindings", summary="查询绑定列表")
async def list_bindings(
    mcp_server_id: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    sync_mode: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    svc = MCPBatchService(db)
    items, total = await svc.list_bindings(
        mcp_server_id=mcp_server_id, agent_id=agent_id,
        sync_mode=sync_mode, status=status,
        offset=offset, limit=limit,
    )
    return {"success": True, "data": [_binding_to_dict(b) for b in items], "total": total}


@router.get("/bindings/{binding_id}", summary="获取绑定详情")
async def get_binding(binding_id: str, db: AsyncSession = Depends(get_db)):
    svc = MCPBatchService(db)
    binding = await svc.get_binding(binding_id)
    if not binding:
        raise HTTPException(404, "绑定不存在")
    return {"success": True, "data": _binding_to_dict(binding)}


@router.put("/bindings/{binding_id}", summary="更新绑定配置")
async def update_binding(binding_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    svc = MCPBatchService(db)
    binding = await svc.update_binding(binding_id, data)
    if not binding:
        raise HTTPException(404, "绑定不存在")
    return {"success": True, "data": _binding_to_dict(binding)}


@router.delete("/bindings/{binding_id}", summary="删除绑定")
async def remove_binding(binding_id: str, db: AsyncSession = Depends(get_db)):
    svc = MCPBatchService(db)
    ok = await svc.remove_binding(binding_id)
    if not ok:
        raise HTTPException(404, "绑定不存在")
    return {"success": True, "message": "已解除绑定"}


# ----------------------------------------------------------
# 同步
# ----------------------------------------------------------

@router.get("/check-updates/{mcp_server_id}", summary="检查 MCP 更新")
async def check_updates(mcp_server_id: str, db: AsyncSession = Depends(get_db)):
    svc = MCPBatchService(db)
    data = await svc.check_updates(mcp_server_id)
    return {"success": True, "data": data}


@router.post("/sync/{binding_id}", summary="同步单条绑定")
async def sync_binding(binding_id: str, db: AsyncSession = Depends(get_db)):
    svc = MCPBatchService(db)
    result = await svc.sync_binding(binding_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return {"success": True, "data": result}


@router.post("/sync-all/{mcp_server_id}", summary="同步 MCP 所有绑定")
async def sync_all(mcp_server_id: str, db: AsyncSession = Depends(get_db)):
    svc = MCPBatchService(db)
    results = await svc.sync_all_for_mcp(mcp_server_id)
    return {"success": True, "data": results, "total": len(results)}