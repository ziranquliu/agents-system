"""
会话恢复服务 — 断线恢复 + 会话迁移

功能:
- 会话状态序列化/反序列化（Redis 缓存，TTL 60s）
- 跨 Agent 会话迁移（5 步流程）
- 客户端断线重连（未读消息恢复）
- 迁移历史记录
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    """会话状态快照"""
    session_id: str = ""
    agent_id: str = ""
    user_id: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    sequence_number: int = 0
    serialized_at: Optional[datetime] = None
    ttl_seconds: int = 60

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "messages": self.messages,
            "context": self.context,
            "metadata": self.metadata,
            "sequence_number": self.sequence_number,
            "serialized_at": self.serialized_at.isoformat() if self.serialized_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionState":
        ts = data.get("serialized_at")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        return cls(
            session_id=data.get("session_id", ""),
            agent_id=data.get("agent_id", ""),
            user_id=data.get("user_id", ""),
            messages=data.get("messages", []),
            context=data.get("context", {}),
            metadata=data.get("metadata", {}),
            sequence_number=data.get("sequence_number", 0),
            serialized_at=ts,
        )


@dataclass
class MigrationRecord:
    """会话迁移记录"""
    id: str = ""
    session_id: str = ""
    source_agent_id: str = ""
    target_agent_id: str = ""
    user_id: str = ""
    status: str = "pending"   # pending / in_progress / completed / failed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: str = ""
    messages_migrated: int = 0

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())


class SessionRecoveryService:
    """
    会话恢复服务

    - save_session_state(): 序列化状态到 Redis（TTL 60s）
    - restore_session(): 从 Redis 恢复
    - migrate_session(): 跨 Agent 迁移（5 步流程）
    - reconnect(): 断线重连 + 未读消息
    """

    STATE_PREFIX = "session:state:"
    MIGRATION_PREFIX = "session:migration:"
    UNREAD_PREFIX = "session:unread:"
    DEFAULT_TTL = 60  # seconds

    def __init__(self):
        self._redis = None
        self._in_memory_cache: dict[str, dict[str, Any]] = {}
        self._migration_history: list[MigrationRecord] = []

    async def initialize(self, redis_client=None):
        """初始化（可选 Redis）"""
        self._redis = redis_client
        if self._redis:
            logger.info("SessionRecoveryService initialized with Redis")
        else:
            logger.info("SessionRecoveryService initialized with in-memory cache")

    # ----------------------------------------------------------
    # 状态序列化与反序列化
    # ----------------------------------------------------------

    async def save_session_state(
        self,
        session_id: str,
        state_data: dict[str, Any],
        ttl: int = DEFAULT_TTL,
    ) -> bool:
        """保存会话状态到缓存"""
        state = SessionState(
            session_id=session_id,
            agent_id=state_data.get("agent_id", ""),
            user_id=state_data.get("user_id", ""),
            messages=state_data.get("messages", []),
            context=state_data.get("context", {}),
            metadata=state_data.get("metadata", {}),
            sequence_number=state_data.get("sequence_number", 0),
            serialized_at=datetime.now(timezone.utc),
            ttl_seconds=ttl,
        )

        key = f"{self.STATE_PREFIX}{session_id}"
        serialized = json.dumps(state.to_dict(), ensure_ascii=False, default=str)

        try:
            if self._redis:
                await self._redis.setex(key, ttl, serialized)
                logger.debug(f"Session state saved to Redis: {session_id} (TTL={ttl}s)")
            else:
                self._in_memory_cache[key] = {
                    "data": serialized,
                    "expires_at": datetime.now(timezone.utc).timestamp() + ttl,
                }
                logger.debug(f"Session state saved to memory: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save session state {session_id}: {e}")
            return False

    async def restore_session(self, session_id: str) -> Optional[SessionState]:
        """从缓存恢复会话状态"""
        key = f"{self.STATE_PREFIX}{session_id}"

        try:
            serialized = None
            if self._redis:
                serialized = await self._redis.get(key)
            else:
                cached = self._in_memory_cache.get(key)
                if cached:
                    if cached["expires_at"] > datetime.now(timezone.utc).timestamp():
                        serialized = cached["data"]
                    else:
                        del self._in_memory_cache[key]

            if serialized:
                if isinstance(serialized, bytes):
                    serialized = serialized.decode("utf-8")
                data = json.loads(serialized)
                state = SessionState.from_dict(data)
                logger.debug(f"Session state restored: {session_id}")
                return state

            logger.debug(f"No cached state for session: {session_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to restore session {session_id}: {e}")
            return None

    # ----------------------------------------------------------
    # 跨 Agent 会话迁移
    # ----------------------------------------------------------

    async def migrate_session(
        self,
        session_id: str,
        source_agent_id: str,
        target_agent_id: str,
        user_id: str = "",
    ) -> MigrationRecord:
        """
        迁移会话到另一个 Agent

        5 步流程:
        1. 序列化当前状态 → 写入 Redis（TTL: 60s）
        2. 目标 Agent 从 Redis 读取状态
        3. 目标 Agent 接管
        4. 源 Agent 释放资源
        5. 记录迁移事件
        """
        record = MigrationRecord(
            session_id=session_id,
            source_agent_id=source_agent_id,
            target_agent_id=target_agent_id,
            user_id=user_id,
            status="in_progress",
            started_at=datetime.now(timezone.utc),
        )

        try:
            # Step 1: 序列化并保存
            state_data = {
                "agent_id": source_agent_id,
                "user_id": user_id,
                "messages": [],
                "context": {},
                "metadata": {"migration": True, "target_agent": target_agent_id},
                "sequence_number": 0,
            }
            saved = await self.save_session_state(session_id, state_data, ttl=60)
            if not saved:
                raise RuntimeError("Failed to serialize session state")

            record.messages_migrated = len(state_data.get("messages", []))

            # Step 2 & 3: 目标 Agent 读取并接管
            restored = await self.restore_session(session_id)
            if restored:
                restored.agent_id = target_agent_id
                restored.context["migrated_from"] = source_agent_id
                restored.context["migration_time"] = datetime.now(timezone.utc).isoformat()
                # 重新保存到目标
                await self.save_session_state(session_id, restored.to_dict(), ttl=120)
                record.messages_migrated = len(restored.messages)

            # Step 4: 清理源 Agent（清理缓存）
            source_key = f"{self.STATE_PREFIX}{session_id}:source"
            if self._redis:
                await self._redis.delete(source_key)

            # Step 5: 记录
            record.status = "completed"
            record.completed_at = datetime.now(timezone.utc)
            logger.info(
                f"Session migrated: {session_id} "
                f"from {source_agent_id} to {target_agent_id}"
            )

        except Exception as e:
            record.status = "failed"
            record.error_message = str(e)
            record.completed_at = datetime.now(timezone.utc)
            logger.error(f"Session migration failed: {session_id}: {e}")

        self._migration_history.append(record)
        return record

    # ----------------------------------------------------------
    # 断线重连
    # ----------------------------------------------------------

    async def reconnect(
        self,
        session_id: str,
        client_id: str = "",
    ) -> dict[str, Any]:
        """
        客户端断线重连

        1. 查找会话
        2. 返回自上次交付以来的未读消息
        3. 恢复状态
        """
        # Step 1: 查找会话状态
        state = await self.restore_session(session_id)

        if not state:
            return {
                "success": False,
                "error": "Session not found or expired",
                "session_id": session_id,
            }

        # Step 2: 获取未读消息（使用 sequence number）
        last_delivered_seq = 0
        unread_key = f"{self.UNREAD_PREFIX}{session_id}:{client_id}"
        if self._redis:
            last_seq = await self._redis.get(unread_key)
            if last_seq:
                last_delivered_seq = int(last_seq)

        unread = await self.get_unread_messages(session_id, last_delivered_seq)

        result = {
            "success": True,
            "session_id": session_id,
            "agent_id": state.agent_id,
            "user_id": state.user_id,
            "unread_messages": unread,
            "unread_count": len(unread),
            "context": state.context,
            "sequence_number": state.sequence_number,
            "reconnected_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info(
            f"Client reconnected: session={session_id}, "
            f"unread={len(unread)}"
        )
        return result

    async def get_unread_messages(
        self,
        session_id: str,
        last_delivered_seq: int = 0,
    ) -> list[dict[str, Any]]:
        """获取指定序号之后的未读消息"""
        state = await self.restore_session(session_id)
        if not state:
            return []

        return [
            msg for msg in state.messages
            if msg.get("sequence", 0) > last_delivered_seq
        ]

    async def update_delivery_seq(self, session_id: str, client_id: str, seq: int):
        """更新已交付序号"""
        key = f"{self.UNREAD_PREFIX}{session_id}:{client_id}"
        try:
            if self._redis:
                await self._redis.setex(key, 86400, str(seq))  # 24h TTL
            else:
                self._in_memory_cache[key] = {"data": str(seq), "expires_at": datetime.now(timezone.utc).timestamp() + 86400}
        except Exception as e:
            logger.error(f"Failed to update delivery seq: {e}")

    # ----------------------------------------------------------
    # 迁移历史
    # ----------------------------------------------------------

    def get_migration_history(
        self,
        session_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """获取迁移历史"""
        records = self._migration_history
        if session_id:
            records = [r for r in records if r.session_id == session_id]

        return [
            {
                "id": r.id,
                "session_id": r.session_id,
                "source_agent_id": r.source_agent_id,
                "target_agent_id": r.target_agent_id,
                "user_id": r.user_id,
                "status": r.status,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "error_message": r.error_message,
                "messages_migrated": r.messages_migrated,
            }
            for r in records[-limit:]
        ]

    def get_migration_stats(self) -> dict[str, Any]:
        """获取迁移统计"""
        total = len(self._migration_history)
        success = sum(1 for r in self._migration_history if r.status == "completed")
        return {
            "total_migrations": total,
            "success_count": success,
            "failure_count": total - success,
            "success_rate": round(success / total * 100, 1) if total > 0 else 0,
        }
