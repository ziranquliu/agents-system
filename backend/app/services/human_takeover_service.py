"""
人工介入服务 — 对话转人工

功能:
- 对话转人工（human takeover）
- 人工客服分配
- 介入状态管理（pending/active/resolved）
- 人工回复后回传给 Agent
- 介入历史与统计
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TakeoverStatus(str, Enum):
    PENDING = "pending"         # 等待人工接入
    ACCEPTED = "accepted"       # 人工已接入
    ACTIVE = "active"           # 人工处理中
    TRANSFERRED = "transferred" # 已转接给其他人工
    RESOLVED = "resolved"       # 已解决
    CLOSED = "closed"           # 已关闭（回传给 Agent）


class TakeoverTrigger(str, Enum):
    USER_REQUEST = "user_request"     # 用户主动请求
    AGENT_ESCALATION = "agent_escalation"  # Agent 主动升级
    SENTIMENT = "sentiment"           # 情感分析触发
    COMPLEXITY = "complexity"         # 问题复杂度触发
    SYSTEM_RULE = "system_rule"       # 系统规则触发


@dataclass
class TakeoverSession:
    """人工介入会话"""
    id: str = ""
    session_id: str = ""
    conversation_id: str = ""
    agent_id: str = ""
    user_id: str = ""
    human_agent_id: Optional[str] = None
    status: TakeoverStatus = TakeoverStatus.PENDING
    trigger: TakeoverTrigger = TakeoverTrigger.USER_REQUEST
    trigger_reason: str = ""
    created_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    priority: int = 0  # 0=普通, 1=高, 2=紧急
    tags: list[str] = field(default_factory=list)
    summary: str = ""
    resolution: str = ""
    handoff_notes: str = ""  # Agent → 人工的交接笔记

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc)


@dataclass
class TakeoverMessage:
    """介入对话消息"""
    id: str = ""
    session_id: str = ""
    sender_type: str = "human"   # human / agent / system
    sender_id: str = ""
    content: str = ""
    timestamp: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc)


class HumanTakeoverService:
    """
    人工介入服务

    流程：
    1. 触发介入请求（用户 / Agent / 规则）
    2. 分配人工客服
    3. 人工处理
    4. 解决后回传给 Agent
    """

    def __init__(self):
        self._sessions: dict[str, TakeoverSession] = {}
        self._messages: dict[str, list[TakeoverMessage]] = {}
        self._agents_status: dict[str, str] = {}  # human_agent_id → status(available/busy/offline)

    # ----------------------------------------------------------
    # 介入请求
    # ----------------------------------------------------------

    async def request_takeover(
        self,
        session_id: str,
        conversation_id: str = "",
        agent_id: str = "",
        user_id: str = "",
        trigger: TakeoverTrigger = TakeoverTrigger.USER_REQUEST,
        trigger_reason: str = "",
        priority: int = 0,
        handoff_notes: str = "",
        tags: Optional[list[str]] = None,
    ) -> TakeoverSession:
        """请求人工介入"""
        session = TakeoverSession(
            session_id=session_id,
            conversation_id=conversation_id,
            agent_id=agent_id,
            user_id=user_id,
            trigger=trigger,
            trigger_reason=trigger_reason,
            priority=priority,
            handoff_notes=handoff_notes,
            tags=tags or [],
        )
        self._sessions[session.id] = session
        self._messages[session.id] = []

        # 系统消息
        system_msg = TakeoverMessage(
            session_id=session.id,
            sender_type="system",
            content=f"人工介入请求: {trigger_reason or trigger.value}",
        )
        self._messages[session.id].append(system_msg)

        logger.info(f"Takeover requested: session={session.id}, trigger={trigger.value}")
        return session

    async def accept_takeover(
        self,
        takeover_id: str,
        human_agent_id: str,
    ) -> Optional[TakeoverSession]:
        """人工客服接入"""
        session = self._sessions.get(takeover_id)
        if not session:
            return None

        if session.status != TakeoverStatus.PENDING:
            logger.warning(f"Cannot accept: takeover {takeover_id} status is {session.status}")
            return None

        session.status = TakeoverStatus.ACCEPTED
        session.human_agent_id = human_agent_id
        session.accepted_at = datetime.now(timezone.utc)
        self._agents_status[human_agent_id] = "busy"

        msg = TakeoverMessage(
            session_id=session.id,
            sender_type="system",
            content=f"人工客服 {human_agent_id} 已接入",
        )
        self._messages[session.id].append(msg)

        logger.info(f"Takeover accepted: {takeover_id} by {human_agent_id}")
        return session

    async def send_human_message(
        self,
        takeover_id: str,
        human_agent_id: str,
        content: str,
    ) -> Optional[TakeoverMessage]:
        """人工客服发送消息"""
        session = self._sessions.get(takeover_id)
        if not session or session.human_agent_id != human_agent_id:
            return None

        session.status = TakeoverStatus.ACTIVE

        msg = TakeoverMessage(
            session_id=session.id,
            sender_type="human",
            sender_id=human_agent_id,
            content=content,
        )
        self._messages[session.id].append(msg)
        return msg

    async def transfer_takeover(
        self,
        takeover_id: str,
        from_agent_id: str,
        to_agent_id: str,
        reason: str = "",
    ) -> Optional[TakeoverSession]:
        """转接给其他人工客服"""
        session = self._sessions.get(takeover_id)
        if not session or session.human_agent_id != from_agent_id:
            return None

        session.status = TakeoverStatus.TRANSFERRED
        session.human_agent_id = to_agent_id
        self._agents_status[from_agent_id] = "available"
        self._agents_status[to_agent_id] = "busy"

        msg = TakeoverMessage(
            session_id=session.id,
            sender_type="system",
            content=f"已转接给 {to_agent_id}" + (f" (原因: {reason})" if reason else ""),
        )
        self._messages[session.id].append(msg)
        return session

    async def resolve_takeover(
        self,
        takeover_id: str,
        human_agent_id: str,
        resolution: str = "",
        summary: str = "",
    ) -> Optional[TakeoverSession]:
        """解决介入问题"""
        session = self._sessions.get(takeover_id)
        if not session or session.human_agent_id != human_agent_id:
            return None

        session.status = TakeoverStatus.RESOLVED
        session.resolved_at = datetime.now(timezone.utc)
        session.resolution = resolution
        session.summary = summary
        self._agents_status[human_agent_id] = "available"

        msg = TakeoverMessage(
            session_id=session.id,
            sender_type="system",
            content=f"问题已解决: {resolution}" if resolution else "问题已解决",
        )
        self._messages[session.id].append(msg)
        return session

    async def close_takeover(
        self,
        takeover_id: str,
        back_to_agent: bool = True,
    ) -> Optional[TakeoverSession]:
        """关闭介入会话（可选回传给 Agent）"""
        session = self._sessions.get(takeover_id)
        if not session:
            return None

        session.status = TakeoverStatus.CLOSED

        msg = TakeoverMessage(
            session_id=session.id,
            sender_type="system",
            content="介入会话已关闭" + ("，已回传给 Agent" if back_to_agent else ""),
        )
        self._messages[session.id].append(msg)
        return session

    # ----------------------------------------------------------
    # 查询
    # ----------------------------------------------------------

    def get_takeover(self, takeover_id: str) -> Optional[TakeoverSession]:
        return self._sessions.get(takeover_id)

    def get_messages(self, takeover_id: str) -> list[dict[str, Any]]:
        messages = self._messages.get(takeover_id, [])
        return [
            {
                "id": m.id,
                "sender_type": m.sender_type,
                "sender_id": m.sender_id,
                "content": m.content,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
            }
            for m in messages
        ]

    def list_pending(self) -> list[dict[str, Any]]:
        """列出等待接入的会话"""
        return [
            {
                "id": s.id,
                "session_id": s.session_id,
                "agent_id": s.agent_id,
                "user_id": s.user_id,
                "trigger": s.trigger.value,
                "trigger_reason": s.trigger_reason,
                "priority": s.priority,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in self._sessions.values()
            if s.status == TakeoverStatus.PENDING
        ]

    def list_active(self) -> list[dict[str, Any]]:
        """列出正在处理的会话"""
        return [
            {
                "id": s.id,
                "session_id": s.session_id,
                "human_agent_id": s.human_agent_id,
                "status": s.status.value,
                "trigger": s.trigger.value,
                "accepted_at": s.accepted_at.isoformat() if s.accepted_at else None,
            }
            for s in self._sessions.values()
            if s.status in (TakeoverStatus.ACCEPTED, TakeoverStatus.ACTIVE, TakeoverStatus.TRANSFERRED)
        ]

    def get_takeover_history(
        self,
        agent_id: Optional[str] = None,
        human_agent_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """获取介入历史"""
        records = list(self._sessions.values())
        if agent_id:
            records = [r for r in records if r.agent_id == agent_id]
        if human_agent_id:
            records = [r for r in records if r.human_agent_id == human_agent_id]

        return [
            {
                "id": r.id,
                "session_id": r.session_id,
                "agent_id": r.agent_id,
                "human_agent_id": r.human_agent_id,
                "status": r.status.value,
                "trigger": r.trigger.value,
                "trigger_reason": r.trigger_reason,
                "priority": r.priority,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "accepted_at": r.accepted_at.isoformat() if r.accepted_at else None,
                "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
                "resolution": r.resolution,
                "summary": r.summary,
            }
            for r in records[-limit:]
        ]

    def get_stats(self) -> dict[str, Any]:
        """获取介入统计"""
        total = len(self._sessions)
        resolved = sum(1 for s in self._sessions.values() if s.status == TakeoverStatus.RESOLVED)
        pending = sum(1 for s in self._sessions.values() if s.status == TakeoverStatus.PENDING)
        avg_resolution_time = 0.0
        resolution_times = []
        for s in self._sessions.values():
            if s.accepted_at and s.resolved_at:
                dt = (s.resolved_at - s.accepted_at).total_seconds()
                resolution_times.append(dt)
        if resolution_times:
            avg_resolution_time = sum(resolution_times) / len(resolution_times)

        trigger_counts = {}
        for s in self._sessions.values():
            t = s.trigger.value
            trigger_counts[t] = trigger_counts.get(t, 0) + 1

        return {
            "total": total,
            "pending": pending,
            "active": sum(1 for s in self._sessions.values() if s.status == TakeoverStatus.ACTIVE),
            "resolved": resolved,
            "resolution_rate": round(resolved / total * 100, 1) if total > 0 else 0,
            "avg_resolution_time_seconds": round(avg_resolution_time, 1),
            "trigger_breakdown": trigger_counts,
        }
