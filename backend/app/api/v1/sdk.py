"""
Agent SDK 上报接收 API

- /sdk/report: 接收批量上报数据
- /sdk/heartbeat: 接收心跳
- /sdk/metrics: 接收指标
- /sdk/events: 查询上报历史
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter()


class EventReport(BaseModel):
    id: str = ""
    event_type: str = ""
    agent_id: str = ""
    payload: dict = {}
    timestamp: Optional[str] = None


class BatchReport(BaseModel):
    agent_id: str = ""
    events: list[EventReport] = []
    batch_size: int = 0
    timestamp: Optional[str] = None


# 内存存储（生产应用 DB + Redis）
_sdk_events: list[dict] = []
_sdk_agents: dict[str, dict] = {}


@router.post("/report")
async def receive_report(report: BatchReport):
    """接收批量上报数据"""
    for event in report.events:
        _sdk_events.append({
            "id": event.id,
            "event_type": event.event_type,
            "agent_id": event.agent_id,
            "payload": event.payload,
            "timestamp": event.timestamp or datetime.utcnow().isoformat(),
        })

    # 更新 Agent 状态
    if report.agent_id:
        if report.agent_id not in _sdk_agents:
            _sdk_agents[report.agent_id] = {
                "agent_id": report.agent_id,
                "last_seen": datetime.utcnow().isoformat(),
                "event_count": 0,
                "status": "running",
            }
        _sdk_agents[report.agent_id]["last_seen"] = datetime.utcnow().isoformat()
        _sdk_agents[report.agent_id]["event_count"] += len(report.events)

    # 保留最近 10000 条
    if len(_sdk_events) > 10000:
        _sdk_events[:] = _sdk_events[-5000:]

    return {
        "status": "ok",
        "received": len(report.events),
        "agent_id": report.agent_id,
    }


@router.post("/heartbeat")
async def receive_heartbeat(agent_id: str, payload: dict = {}):
    """接收心跳"""
    if agent_id not in _sdk_agents:
        _sdk_agents[agent_id] = {
            "agent_id": agent_id,
            "event_count": 0,
            "status": "running",
        }
    _sdk_agents[agent_id]["last_seen"] = datetime.utcnow().isoformat()
    _sdk_agents[agent_id]["heartbeat_payload"] = payload
    return {"status": "ok"}


@router.get("/agents")
async def list_agents():
    """列出所有已上报的 Agent"""
    now = datetime.utcnow()
    agents = []
    for agent_id, info in _sdk_agents.items():
        agents.append({
            **info,
            "online": True,  # 简化：有上报即在线
        })
    return agents


@router.get("/events")
async def list_events(
    agent_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 100,
):
    """查询上报历史"""
    events = _sdk_events
    if agent_id:
        events = [e for e in events if e["agent_id"] == agent_id]
    if event_type:
        events = [e for e in events if e["event_type"] == event_type]
    return events[-limit:]


@router.get("/stats")
async def get_sdk_stats():
    """获取 SDK 统计"""
    total_events = len(_sdk_events)
    event_types = {}
    for e in _sdk_events:
        t = e["event_type"]
        event_types[t] = event_types.get(t, 0) + 1

    return {
        "total_agents": len(_sdk_agents),
        "total_events": total_events,
        "event_type_breakdown": event_types,
        "agents": list(_sdk_agents.values()),
    }
