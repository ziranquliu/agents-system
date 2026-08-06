"""
会话管理器 - 6态生命周期、上下文窗口策略、会话监控
"""
import json
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Message

logger = logging.getLogger(__name__)

# 6态生命周期状态
SESSION_STATES = ("active", "idle", "timeout", "archived", "cleaned", "error")

# 状态转换规则
STATE_TRANSITIONS = {
    "active":   ["idle", "timeout", "archived", "error"],
    "idle":     ["active", "timeout", "archived", "cleaned"],
    "timeout":  ["active", "archived", "cleaned"],
    "archived": ["cleaned"],
    "cleaned":  [],  # 终态
    "error":    ["active", "archived"],
}


def _safe_json(s, default=None):
    if not s:
        return default if default is not None else {}
    try:
        return json.loads(s) if isinstance(s, str) else s
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else {}


class SessionManager:
    """6态会话生命周期管理器"""

    # 默认配置
    DEFAULT_IDLE_TIMEOUT_MINUTES = 30
    DEFAULT_TIMEOUT_MINUTES = 120
    DEFAULT_AUTO_ARCHIVE_DAYS = 7
    DEFAULT_MAX_MESSAGES_IN_CONTEXT = 50
    DEFAULT_CONTEXT_WINDOW_TOKENS = 4096

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================================================================
    # 会话生命周期管理
    # ==================================================================

    async def get_or_create_session(
        self,
        user_id: str,
        agent_id: str,
        workspace_id: Optional[str] = None,
    ) -> Conversation:
        """获取活跃会话或创建新会话"""
        result = await self.db.execute(
            select(Conversation).where(
                and_(
                    Conversation.user_id == user_id,
                    Conversation.agent_id == agent_id,
                    Conversation.status == "active",
                )
            ).order_by(Conversation.created_at.desc()).limit(1)
        )
        session = result.scalar_one_or_none()

        if session:
            # 唤醒 idle/timeout 状态的会话
            if session.status in ("idle", "timeout"):
                session.status = "active"
                session.updated_at = datetime.now(timezone.utc)
                await self.db.flush()
            return session

        # 创建新会话
        session = Conversation(
            id=str(uuid.uuid4()),
            user_id=user_id,
            agent_id=agent_id,
            workspace_id=workspace_id,
            title="",
            status="active",
            model_info="",
            token_count=0,
            turn_count=0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(session)
        await self.db.flush()
        return session

    async def transition_state(
        self, session_id: str, new_state: str, reason: str = ""
    ) -> Conversation:
        """状态转换(含校验)"""
        if new_state not in SESSION_STATES:
            raise ValueError(f"无效状态: {new_state}")

        session = await self._get_session(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")

        current = session.status
        allowed = STATE_TRANSITIONS.get(current, [])
        if new_state not in allowed:
            raise ValueError(
                f"不允许从 {current} 转换到 {new_state}, "
                f"允许的转换: {allowed}"
            )

        session.status = new_state
        session.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info(
            "会话 %s 状态转换: %s -> %s (原因: %s)",
            session_id, current, new_state, reason,
        )
        return session

    async def timeout_check(self, idle_timeout_minutes: Optional[int] = None,
                            hard_timeout_minutes: Optional[int] = None) -> dict:
        """
        扫描并处理超时会话
        active/idle 超时 → timeout
        timeout 超时 → archived
        """
        idle_mins = idle_timeout_minutes or self.DEFAULT_IDLE_TIMEOUT_MINUTES
        hard_mins = hard_timeout_minutes or self.DEFAULT_TIMEOUT_MINUTES

        now = datetime.now(timezone.utc)
        idle_cutoff = now - timedelta(minutes=idle_mins)
        hard_cutoff = now - timedelta(minutes=hard_mins)

        # active → idle (超过 idle 时间未更新)
        active_result = await self.db.execute(
            select(Conversation).where(
                and_(
                    Conversation.status == "active",
                    Conversation.updated_at < idle_cutoff,
                )
            )
        )
        idled = 0
        for session in active_result.scalars().all():
            session.status = "idle"
            session.updated_at = now
            idled += 1

        # idle → timeout (超过硬超时)
        idle_result = await self.db.execute(
            select(Conversation).where(
                and_(
                    Conversation.status == "idle",
                    Conversation.updated_at < hard_cutoff,
                )
            )
        )
        timed_out = 0
        for session in idle_result.scalars().all():
            session.status = "timeout"
            session.updated_at = now
            timed_out += 1

        # active → timeout (长时间未处理)
        long_active = await self.db.execute(
            select(Conversation).where(
                and_(
                    Conversation.status == "active",
                    Conversation.updated_at < hard_cutoff,
                )
            )
        )
        for session in long_active.scalars().all():
            session.status = "timeout"
            session.updated_at = now
            timed_out += 1

        await self.db.flush()
        return {"idled": idled, "timed_out": timed_out}

    async def auto_archive(self, archive_days: Optional[int] = None) -> dict:
        """自动归档超过指定天数的 timeout/empty 会话"""
        days = archive_days or self.DEFAULT_AUTO_ARCHIVE_DAYS
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        result = await self.db.execute(
            select(Conversation).where(
                and_(
                    Conversation.status.in_(["timeout", "idle"]),
                    Conversation.updated_at < cutoff,
                )
            )
        )
        archived = 0
        for session in result.scalars().all():
            session.status = "archived"
            session.updated_at = datetime.now(timezone.utc)
            archived += 1

        await self.db.flush()
        return {"archived": archived}

    async def cleanup_archived(self) -> dict:
        """清理已归档会话的消息(保留元数据)"""
        result = await self.db.execute(
            select(Conversation).where(Conversation.status == "archived")
        )
        cleaned = 0
        for session in result.scalars().all():
            # 删除旧消息
            msg_result = await self.db.execute(
                select(Message).where(Message.conversation_id == session.id)
            )
            for msg in msg_result.scalars().all():
                await self.db.delete(msg)

            session.status = "cleaned"
            session.updated_at = datetime.now(timezone.utc)
            cleaned += 1

        await self.db.flush()
        return {"cleaned": cleaned}

    # ==================================================================
    # 上下文窗口管理
    # ==================================================================

    async def build_context(
        self,
        session_id: str,
        new_message: str,
        max_messages: Optional[int] = None,
        max_tokens: Optional[int] = None,
        strategy: str = "sliding_window",
    ) -> list[dict]:
        """
        构建上下文窗口
        
        策略:
        - sliding_window: 滑动窗口(保留最近N条消息)
        - importance: 保留重要消息(基于角色和长度)
        - summary: 摘要压缩(保留系统消息+摘要+最近消息)
        - hybrid: 混合策略(系统消息+最近消息+重要消息)
        """
        max_msgs = max_messages or self.DEFAULT_MAX_MESSAGES_IN_CONTEXT
        max_tok = max_tokens or self.DEFAULT_CONTEXT_WINDOW_TOKENS

        # 获取历史消息
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(max_msgs * 2)  # 多取一些以供策略筛选
        )
        messages = list(reversed(result.scalars().all()))

        if strategy == "sliding_window":
            context_msgs = messages[-max_msgs:]
        elif strategy == "importance":
            context_msgs = self._importance_filter(messages, max_msgs)
        elif strategy == "summary":
            context_msgs = self._summary_strategy(messages, max_msgs, max_tok)
        elif strategy == "hybrid":
            context_msgs = self._hybrid_strategy(messages, max_msgs, max_tok)
        else:
            context_msgs = messages[-max_msgs:]

        # 转为 dict 格式
        context = []
        for msg in context_msgs:
            context.append({
                "role": msg.role,
                "content": msg.content,
            })

        # 添加新消息
        context.append({"role": "user", "content": new_message})
        return context

    def _importance_filter(
        self, messages: list, max_messages: int
    ) -> list:
        """基于重要性过滤: system > assistant > user, 长消息 > 短消息"""
        scored = []
        for msg in messages:
            score = 0
            if msg.role == "system":
                score += 100
            elif msg.role == "assistant":
                score += 50
            else:
                score += 10
            # 消息长度加分
            score += min(len(msg.content or "") // 100, 20)
            scored.append((score, msg))

        # 按分数排序,取 top N
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = [m for _, m in scored[:max_messages]]
        # 保持时间顺序
        selected.sort(key=lambda m: m.created_at or datetime.min.replace(tzinfo=timezone.utc))
        return selected

    def _summary_strategy(
        self, messages: list, max_messages: int, max_tokens: int
    ) -> list:
        """摘要策略: 保留 system + 最近消息,中间的压缩"""
        if len(messages) <= max_messages:
            return messages

        # 保留系统消息
        system_msgs = [m for m in messages if m.role == "system"]

        # 保留最近的消息
        recent_count = max_messages // 2
        recent = messages[-recent_count:] if recent_count > 0 else []

        # 中间部分生成摘要占位
        middle = messages[len(system_msgs):-recent_count] if recent_count > 0 else messages[len(system_msgs):]
        if middle:
            summary_content = f"[历史摘要: 共{len(middle)}条消息,时间范围 {middle[0].created_at} ~ {middle[-1].created_at}]"
            summary_msg = Message(
                id=str(uuid.uuid4()),
                conversation_id=middle[0].conversation_id,
                role="system",
                content=summary_content,
                token_count=0,
                created_at=datetime.now(timezone.utc),
            )
            return system_msgs + [summary_msg] + recent

        return system_msgs + recent

    def _hybrid_strategy(
        self, messages: list, max_messages: int, max_tokens: int
    ) -> list:
        """混合策略: 系统消息 + 重要消息 + 最近消息"""
        system_msgs = [m for m in messages if m.role == "system"]
        non_system = [m for m in messages if m.role != "system"]

        # 最近的消息
        recent_count = max_messages // 3
        recent = non_system[-recent_count:] if recent_count > 0 else []

        # 剩余空间放重要消息
        remaining = max_messages - len(system_msgs) - len(recent)
        if remaining > 0 and len(non_system) > recent_count:
            older = non_system[:-recent_count] if recent_count > 0 else non_system
            important = self._importance_filter(older, remaining)
        else:
            important = []

        all_msgs = system_msgs + important + recent
        # 去重(保持顺序)
        seen = set()
        deduped = []
        for m in all_msgs:
            if m.id not in seen:
                seen.add(m.id)
                deduped.append(m)
        return deduped

    # ==================================================================
    # 会话分析
    # ==================================================================

    async def get_session_analytics(self, session_id: str) -> dict:
        """获取会话分析数据"""
        session = await self._get_session(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")

        msg_count_result = await self.db.execute(
            select(func.count()).select_from(Message).where(
                Message.conversation_id == session_id
            )
        )
        message_count = msg_count_result.scalar() or 0

        # Token 统计
        token_result = await self.db.execute(
            select(func.coalesce(func.sum(Message.token_count), 0)).where(
                Message.conversation_id == session_id
            )
        )
        total_tokens = token_result.scalar() or 0

        # 平均消息长度
        avg_len_result = await self.db.execute(
            select(func.coalesce(func.avg(func.length(Message.content)), 0)).where(
                Message.conversation_id == session_id
            )
        )
        avg_length = avg_len_result.scalar() or 0

        # 时间跨度
        first_result = await self.db.execute(
            select(func.min(Message.created_at)).where(
                Message.conversation_id == session_id
            )
        )
        first_msg = first_result.scalar()

        return {
            "session_id": session_id,
            "status": session.status,
            "message_count": message_count,
            "total_tokens": total_tokens,
            "average_message_length": round(float(avg_length), 1),
            "first_message_at": str(first_msg) if first_msg else None,
            "last_message_at": str(session.updated_at),
            "created_at": str(session.created_at),
            "duration_minutes": (
                (session.updated_at - session.created_at).total_seconds() / 60
                if session.created_at and session.updated_at else 0
            ),
        }

    async def batch_transition(
        self, session_ids: list[str], new_state: str, reason: str = ""
    ) -> dict:
        """批量状态转换"""
        succeeded = 0
        failed = 0
        for sid in session_ids:
            try:
                await self.transition_state(sid, new_state, reason)
                succeeded += 1
            except (ValueError, Exception) as e:
                failed += 1
                logger.warning("批量转换会话 %s 失败: %s", sid, str(e))
        return {"succeeded": succeeded, "failed": failed}

    async def get_lifecycle_stats(self) -> dict:
        """获取生命周期统计"""
        stats = {}
        for state in SESSION_STATES:
            result = await self.db.execute(
                select(func.count()).select_from(Conversation).where(
                    Conversation.status == state
                )
            )
            stats[state] = result.scalar() or 0
        stats["total"] = sum(stats.values())
        return stats

    # ==================================================================
    # 内部方法
    # ==================================================================

    async def _get_session(self, session_id: str) -> Optional[Conversation]:
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == session_id)
        )
        return result.scalar_one_or_none()

    # ==================================================================
    # 三级存储分层 (Hot→Warm→Cold)
    # ==================================================================

    """
    存储层级:
    - Hot: 活跃会话(内存/Redis) — 当前由上下文窗口策略管理
    - Warm: PG 中的归档会话 — status=archived, 消息保留
    - Cold: JSON 文件存储 — status=cleaned, 消息已归档到磁盘
    """

    async def archive_to_cold_storage(
        self, session_id: str, base_path: str = "cold_storage/sessions"
    ) -> dict:
        """
        将已归档会话的消息导出到 JSON 文件(冷存储),然后清理 DB 消息。

        流程:
        1. 读取会话的所有消息
        2. 导出为 JSON 文件(base_path/session_id.json)
        3. 删除 DB 中的消息记录
        4. 会话状态设为 cleaned
        """
        import os

        session = await self._get_session(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")
        if session.status not in ("archived", "cleaned"):
            raise ValueError(f"只能归档 archived/cleaned 状态的会话,当前: {session.status}")

        # 读取所有消息
        msg_result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == session_id)
            .order_by(Message.created_at)
        )
        messages = list(msg_result.scalars().all())

        if not messages:
            session.status = "cleaned"
            session.updated_at = datetime.now(timezone.utc)
            await self.db.flush()
            return {"archived": True, "messages_exported": 0, "file": None}

        # 构建归档数据
        archive_data = {
            "session_id": session_id,
            "user_id": session.user_id,
            "agent_id": session.agent_id,
            "title": session.title,
            "created_at": str(session.created_at),
            "archived_at": str(datetime.now(timezone.utc)),
            "message_count": len(messages),
            "total_tokens": session.token_count or 0,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "token_count": m.token_count or 0,
                    "model_name": m.model_name,
                    "created_at": str(m.created_at),
                }
                for m in messages
            ],
        }

        # 写入 JSON 文件
        os.makedirs(base_path, exist_ok=True)
        file_path = os.path.join(base_path, f"{session_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(archive_data, f, ensure_ascii=False, indent=2)

        # 删除 DB 中的消息
        for msg in messages:
            await self.db.delete(msg)

        session.status = "cleaned"
        session.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info(
            "会话 %s 已归档到冷存储: %s (%d条消息)",
            session_id, file_path, len(messages),
        )
        return {
            "archived": True,
            "messages_exported": len(messages),
            "file": file_path,
        }

    async def restore_from_cold_storage(
        self, session_id: str, base_path: str = "cold_storage/sessions"
    ) -> dict:
        """
        从冷存储 JSON 文件恢复会话消息到 DB。

        流程:
        1. 读取 JSON 归档文件
        2. 恢复消息到 DB
        3. 会话状态设为 active
        """
        import os

        session = await self._get_session(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")

        file_path = os.path.join(base_path, f"{session_id}.json")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"冷存储文件不存在: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            archive_data = json.load(f)

        restored_count = 0
        for msg_data in archive_data.get("messages", []):
            msg = Message(
                id=msg_data.get("id", str(uuid.uuid4())),
                conversation_id=session_id,
                role=msg_data.get("role", "user"),
                content=msg_data.get("content", ""),
                token_count=msg_data.get("token_count", 0),
                model_name=msg_data.get("model_name"),
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(msg)
            restored_count += 1

        session.status = "active"
        session.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info("会话 %s 已从冷存储恢复: %d条消息", session_id, restored_count)
        return {"restored": True, "messages_restored": restored_count, "file": file_path}

    async def batch_cold_archive(
        self, older_than_days: int = 90, base_path: str = "cold_storage/sessions"
    ) -> dict:
        """
        批量冷存储: 将超过指定天数的 archived 会话导出到 JSON 文件。

        常用于定时任务。
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        result = await self.db.execute(
            select(Conversation).where(
                and_(
                    Conversation.status == "archived",
                    Conversation.updated_at < cutoff,
                )
            )
        )
        sessions = list(result.scalars().all())

        archived = 0
        failed = 0
        for session in sessions:
            try:
                await self.archive_to_cold_storage(session.id, base_path)
                archived += 1
            except Exception as e:
                failed += 1
                logger.warning("批量冷存储会话 %s 失败: %s", session.id, str(e))

        return {"archived": archived, "failed": failed, "total": len(sessions)}
