"""
智能体记忆管理服务 - 三层记忆体系的核心逻辑
包含：CRUD、重要性评分、遗忘、隐私脱敏、搜索、统计分析
"""
import json
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select, func as sa_func, and_, or_, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import AgentMemory, MemoryAnalytics, MemoryType, MemoryCategory

from sqlalchemy.orm import selectinload, joinedload


# ============================================================
# 隐私敏感信息检测（正则模式）
# ============================================================
SENSITIVE_PATTERNS = {
    "personal": [
        r"\b1[3-9]\d{9}\b",           # 手机号
        r"\b\d{17}[\dXx]\b",           # 身份证
        r"\b\d{6,20}\b",               # 银行卡/QQ号（纯数字6-20位）
    ],
    "credential": [
        r"(?i)(password|passwd|pwd|secret|token|api[_-]?key)\s*[:=]\s*\S+",
        r"(?i)(sk-[a-zA-Z0-9]{20,}|pk-[a-zA-Z0-9]{20,})",  # OpenAI key
    ],
    "custom": [],
}


def _detect_sensitive(content: str) -> tuple[bool, str, str]:
    """
    检测敏感信息。
    返回: (is_sensitive, sensitive_type, masked_content)
    """
    masked = content
    for stype, patterns in SENSITIVE_PATTERNS.items():
        for pat in patterns:
            matches = list(re.finditer(pat, masked))
            for m in matches:
                val = m.group()
                if stype == "personal" and len(val) == 11:  # 手机号 → 138****1234
                    masked = masked.replace(val, val[:3] + "****" + val[-4:])
                elif stype == "personal" and len(val) == 18:  # 身份证
                    masked = masked.replace(val, val[:6] + "********" + val[-4:])
                else:
                    masked = masked.replace(val, "******")
    is_sensitive = masked != content
    s_type = ""
    if is_sensitive:
        for stype, patterns in SENSITIVE_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, content):
                    s_type = stype
                    break
            if s_type:
                break
    return is_sensitive, s_type, masked


def _compute_importance(content: str, access_count: int,
                        last_accessed: Optional[datetime] = None,
                        ttl_seconds: Optional[int] = None) -> float:
    """
    计算记忆重要性评分 (0-10)。
    因子：
    - 内容长度分 (0-3): 短/中/长/很大
    - 访问次数分 (0-3): 从日志统计
    - 时效性分 (0-2): 近期访问加权
    - 基础分 (0-2)
    """
    length_score = min(3.0, len(content) / 500 * 3)

    freq_score = min(3.0, math.log2(access_count + 1))

    recency_score = 0.0
    if last_accessed:
        days_since = (datetime.now(timezone.utc) - last_accessed).days
        if days_since <= 1:
            recency_score = 2.0
        elif days_since <= 7:
            recency_score = 1.5
        elif days_since <= 30:
            recency_score = 1.0
        elif days_since <= 90:
            recency_score = 0.5

    base_score = 1.0
    if ttl_seconds:
        # 有TTL的短期记忆基础分更低
        base_score = 0.5

    score = length_score + freq_score + recency_score + base_score
    return round(min(10.0, max(0.0, score)), 2)


def _compute_memory_category(content: str, title: str) -> str:
# TODO: Consider splitting this function into smaller sub-functions
    """根据内容关键词初步判断记忆类别"""
    text = (title + " " + content).lower()
    if any(w in text for w in ["喜欢", "偏好", "喜欢用", "更倾向于", "prefer", "favorite"]):
        return MemoryCategory.PREFERENCE
    if any(w in text for w in ["行为", "习惯", "pattern", "always", "通常会"]):
        return MemoryCategory.BEHAVIOR
    if any(w in text for w in ["知道", "了解", "知识", "是", "位于"]):
        return MemoryCategory.KNOWLEDGE
    return MemoryCategory.CONVERSATION


# ============================================================
# 主服务类
# ============================================================

class MemoryService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ----------------------------------------------------------
    # CRUD
    # ----------------------------------------------------------

    async def create_memory(self, data: dict[str, Any]) -> AgentMemory:
        """创建记忆，自动检测敏感信息并计算重要性"""
        content = data.get("content", "")
        title = data.get("title", "")

        # 敏感信息检测
        is_sensitive, s_type, masked = _detect_sensitive(content)

        # 自动分类
        if not data.get("category"):
            data["category"] = _compute_memory_category(content, title)

        # 重要性评分
        ttl = data.get("ttl_seconds")
        importance = _compute_importance(content, 0, None, ttl)

        expires_at = None
        if ttl:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)

        memory = AgentMemory(
            agent_id=data["agent_id"],
            memory_type=data.get("memory_type", MemoryType.LONG_TERM),
            title=title,
            content=content,
            summary=data.get("summary", ""),
            category=data["category"],
            tags=json.dumps(data.get("tags", []), ensure_ascii=False),
            keywords=json.dumps(data.get("keywords", []), ensure_ascii=False),
            embedding_text=data.get("embedding_text", ""),
            importance_score=importance,
            access_count=0,
            is_sensitive=is_sensitive,
            sensitive_info_type=s_type,
            masked_content=masked if is_sensitive else None,
            source_type=data.get("source_type", "manual"),
            source_id=data.get("source_id"),
            created_by=data.get("created_by"),
            shared_to_agents=json.dumps(data.get("shared_to_agents", []), ensure_ascii=False),
            is_public=data.get("is_public", False),
            ttl_seconds=ttl,
            expires_at=expires_at,
        )
        self.db.add(memory)
        await self.db.flush()
        return memory

    async def get_memory(self, memory_id: str) -> Optional[AgentMemory]:
        """获取单条记忆，同时更新访问计数"""
        result = await self.db.execute(
            select(AgentMemory).where(AgentMemory.id == memory_id, AgentMemory.is_forgotten == False)
        )
        memory = result.scalar_one_or_none()
        if memory:
            memory.access_count = (memory.access_count or 0) + 1
            memory.last_accessed_at = datetime.now(timezone.utc)
            memory.importance_score = _compute_importance(
                memory.content, memory.access_count, memory.last_accessed_at, memory.ttl_seconds
            )
            await self.db.flush()
        return memory

    async def update_memory(self, memory_id: str, data: dict[str, Any]) -> Optional[AgentMemory]:
        """更新记忆内容，重新计算重要性和敏感检测"""
        result = await self.db.execute(
            select(AgentMemory).where(AgentMemory.id == memory_id, AgentMemory.is_forgotten == False)
        )
        memory = result.scalar_one_or_none()
        if not memory:
            return None

        updatable = ["title", "content", "summary", "category", "tags", "keywords",
                     "importance_score", "ttl_seconds", "is_public", "shared_to_agents"]

        for key in updatable:
            if key in data:
                setattr(memory, key, data[key])

        if "content" in data:
            is_sensitive, s_type, masked = _detect_sensitive(data["content"])
            memory.is_sensitive = is_sensitive
            memory.sensitive_info_type = s_type
            memory.masked_content = masked if is_sensitive else None

        if data.get("ttl_seconds") is not None:
            memory.expires_at = datetime.now(timezone.utc) + timedelta(seconds=data["ttl_seconds"])

        # 重新评分
        memory.importance_score = _compute_importance(
            memory.content, memory.access_count or 0, memory.last_accessed_at, memory.ttl_seconds
        )

        if isinstance(memory.tags, str):
            pass  # already JSON
        if isinstance(data.get("tags"), list):
            memory.tags = json.dumps(data["tags"], ensure_ascii=False)
        if isinstance(data.get("keywords"), list):
            memory.keywords = json.dumps(data["keywords"], ensure_ascii=False)

        await self.db.flush()
        return memory

    async def delete_memory(self, memory_id: str, reason: str = "manual") -> bool:
        """软删除 - 标记为遗忘"""
        result = await self.db.execute(
            select(AgentMemory).where(AgentMemory.id == memory_id, AgentMemory.is_forgotten == False)
        )
        memory = result.scalar_one_or_none()
        if not memory:
            return False
        memory.is_forgotten = True
        memory.forget_reason = reason
        memory.forgotten_at = datetime.now(timezone.utc)
        await self.db.flush()
        return True

    async def hard_delete_memory(self, memory_id: str) -> bool:
        """物理删除（GDPR 合规）"""
        result = await self.db.execute(
            sa_delete(AgentMemory).where(AgentMemory.id == memory_id)
        )
        return result.rowcount > 0

    async def list_memories(
        self,
        agent_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        category: Optional[str] = None,
        is_sensitive: Optional[bool] = None,
        is_public: Optional[bool] = None,
        include_forgotten: bool = False,
        keyword: Optional[str] = None,
        tag: Optional[str] = None,
        importance_min: Optional[float] = None,
        importance_max: Optional[float] = None,
        sort_by: str = "created_at",
        sort_desc: bool = True,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[AgentMemory], int]:
        """查询记忆列表，支持多维过滤"""
        conditions = []

        if agent_id:
            conditions.append(AgentMemory.agent_id == agent_id)
        if memory_type:
            conditions.append(AgentMemory.memory_type == memory_type)
        if category:
            conditions.append(AgentMemory.category == category)
        if is_sensitive is not None:
            conditions.append(AgentMemory.is_sensitive == is_sensitive)
        if is_public is not None:
            conditions.append(AgentMemory.is_public == is_public)
        if not include_forgotten:
            conditions.append(AgentMemory.is_forgotten == False)
        if keyword:
            conditions.append(
                or_(
                    AgentMemory.content.ilike(f"%{keyword}%"),
                    AgentMemory.title.ilike(f"%{keyword}%"),
                    AgentMemory.summary.ilike(f"%{keyword}%"),
                )
            )
        if importance_min is not None:
            conditions.append(AgentMemory.importance_score >= importance_min)
        if importance_max is not None:
            conditions.append(AgentMemory.importance_score <= importance_max)

        # tag 过滤（JSON 字段内搜索）
        if tag:
            conditions.append(AgentMemory.tags.ilike(f"%{tag}%"))

        where_clause = and_(*conditions) if conditions else True

        # 总数
        count_q = select(sa_func.count()).select_from(AgentMemory).where(where_clause)
        count_result = await self.db.execute(count_q)
        total = count_result.scalar() or 0

        # 排序
        sort_col = getattr(AgentMemory, sort_by, AgentMemory.created_at)
        order = sort_col.desc() if sort_desc else sort_col.asc()

        q = (
            select(AgentMemory)
            .where(where_clause)
            .order_by(order)
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(q)
        items = list(result.scalars().all())
        return items, total

    # ----------------------------------------------------------
    # 遗忘处理
    # ----------------------------------------------------------

    async def process_expired_memories(self) -> int:
        """处理过期记忆：自动遗忘"""
        now = datetime.now(timezone.utc)
        q = (
            select(AgentMemory)
            .where(
                AgentMemory.expires_at <= now,
                AgentMemory.is_forgotten == False,
            )
        )
        result = await self.db.execute(q)
        expired = list(result.scalars().all())
        count = 0
        for mem in expired:
            mem.is_forgotten = True
            mem.forget_reason = "ttl_expired"
            mem.forgotten_at = now
            count += 1
        if count:
            await self.db.flush()
        return count

    async def process_low_importance_memories(self, threshold: float = 2.0,
                                              max_per_agent: int = 50) -> int:
        """遗忘低重要性记忆（仅长期记忆）"""
        now = datetime.now(timezone.utc)
        subq = (
            select(AgentMemory.agent_id, AgentMemory.importance_score)
            .where(
                AgentMemory.memory_type == MemoryType.LONG_TERM,
                AgentMemory.is_forgotten == False,
                AgentMemory.importance_score < threshold,
            )
            .order_by(AgentMemory.importance_score.asc())
        )
        # 每个 Agent 最多遗忘 max_per_agent 条
        result = await self.db.execute(subq)
        candidates = list(result.all())
        # group by agent
        agent_groups: dict[str, list] = {}
        for row in candidates:
            agent_groups.setdefault(row.agent_id, []).append(row)
        count = 0
        for agent_id, rows in agent_groups.items():
            to_forget = rows[:max_per_agent]
            for row in to_forget:
                mem_id = row[0] if hasattr(row, '__getitem__') else row.id
                # re-fetch
                r2 = await self.db.execute(
                    select(AgentMemory).where(AgentMemory.id == mem_id)
                )
                mem = r2.scalar_one_or_none()
                if mem and not mem.is_forgotten:
                    mem.is_forgotten = True
                    mem.forget_reason = "low_importance"
                    mem.forgotten_at = now
                    count += 1
        if count:
            await self.db.flush()
        return count

    async def forget_memories_by_agent(self, agent_id: str,
                                       memory_type: Optional[str] = None) -> int:
        """批量遗忘某个智能体的所有/某类记忆"""
        conditions = [AgentMemory.agent_id == agent_id, AgentMemory.is_forgotten == False]
        if memory_type:
            conditions.append(AgentMemory.memory_type == memory_type)
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(AgentMemory).where(and_(*conditions))
        )
        memories = list(result.scalars().all())
        for mem in memories:
            mem.is_forgotten = True
            mem.forget_reason = "batch_forget"
            mem.forgotten_at = now
        await self.db.flush()
        return len(memories)

    # ----------------------------------------------------------
    # 记忆合并与去重
    # ----------------------------------------------------------

    async def merge_duplicate_memories(self, agent_id: str,
                                       similarity_threshold: float = 0.8) -> int:
        """
        合并相似记忆（基于内容关键词重合度）。
        保留重要性最高的那条，其余标记为遗忘。
        """
        result = await self.db.execute(
            select(AgentMemory)
            .where(
                AgentMemory.agent_id == agent_id,
                AgentMemory.is_forgotten == False,
                AgentMemory.memory_type == MemoryType.LONG_TERM,
            )
            .order_by(AgentMemory.importance_score.desc())
        )
        memories = list(result.scalars().all())
        merged_count = 0
        for i in range(len(memories)):
            if memories[i].is_forgotten:
                continue
            for j in range(i + 1, len(memories)):
                if memories[j].is_forgotten:
                    continue
                sim = self._text_similarity(memories[i].content, memories[j].content)
                if sim >= similarity_threshold:
                    # 合并到重要性高的那个
                    high, low = (memories[i], memories[j]) if memories[i].importance_score >= memories[j].importance_score else (memories[j], memories[i])
                    # 内容合并
                    if len(low.content) > len(high.content):
                        high.content = low.content
                    high.access_count = (high.access_count or 0) + (low.access_count or 0)
                    high.importance_score = _compute_importance(
                        high.content, high.access_count, high.last_accessed_at, high.ttl_seconds
                    )
                    # 标记低分记忆为遗忘
                    low.is_forgotten = True
                    low.forget_reason = "merged"
                    low.forgotten_at = datetime.now(timezone.utc)
                    merged_count += 1
        if merged_count:
            await self.db.flush()
        return merged_count

    @staticmethod
    def _text_similarity(a: str, b: str) -> float:
        """简单文本相似度：基于公共单词的 Jaccard 系数"""
        if not a or not b:
            return 0.0
        set_a = set(a.lower().split())
        set_b = set(b.lower().split())
        if not set_a or not set_b:
            return 0.0
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union)

    # ----------------------------------------------------------
    # 统计分析
    # ----------------------------------------------------------

    async def get_memory_stats(self, agent_id: str) -> dict[str, Any]:
        """获取指定智能体的记忆统计数据"""
        base_q = select(AgentMemory).where(AgentMemory.agent_id == agent_id)

        # 总数
        r = await self.db.execute(select(sa_func.count()).select_from(AgentMemory).where(
            AgentMemory.agent_id == agent_id, AgentMemory.is_forgotten == False))
        total = r.scalar() or 0

        # 按类型
        stats = {}
        for mtype in [MemoryType.SHORT_TERM, MemoryType.LONG_TERM, MemoryType.SHARED]:
            r = await self.db.execute(select(sa_func.count()).select_from(AgentMemory).where(
                and_(AgentMemory.agent_id == agent_id, AgentMemory.memory_type == mtype, AgentMemory.is_forgotten == False)))
            stats[mtype] = r.scalar() or 0

        # 按类别
        categories = {}
        for cat in [MemoryCategory.CONVERSATION, MemoryCategory.KNOWLEDGE,
                    MemoryCategory.PREFERENCE, MemoryCategory.BEHAVIOR, MemoryCategory.CUSTOM]:
            r = await self.db.execute(select(sa_func.count()).select_from(AgentMemory).where(
                and_(AgentMemory.agent_id == agent_id, AgentMemory.category == cat, AgentMemory.is_forgotten == False)))
            if c := r.scalar() or 0:
                categories[cat] = c

        # 重要性分布
        r = await self.db.execute(select(sa_func.avg(AgentMemory.importance_score)).where(
            and_(AgentMemory.agent_id == agent_id, AgentMemory.is_forgotten == False)))
        avg_imp = round(r.scalar() or 0, 2)

        # 敏感记忆数
        r = await self.db.execute(select(sa_func.count()).select_from(AgentMemory).where(
            and_(AgentMemory.agent_id == agent_id, AgentMemory.is_sensitive == True, AgentMemory.is_forgotten == False)))
        sensitive_count = r.scalar() or 0

        # 遗忘数
        r = await self.db.execute(select(sa_func.count()).select_from(AgentMemory).where(
            and_(AgentMemory.agent_id == agent_id, AgentMemory.is_forgotten == True)))
        forgotten_count = r.scalar() or 0

        # TTL统计
        r = await self.db.execute(select(sa_func.count()).select_from(AgentMemory).where(
            and_(AgentMemory.agent_id == agent_id, AgentMemory.expires_at != None,
                 AgentMemory.expires_at > datetime.now(timezone.utc), AgentMemory.is_forgotten == False)))
        ttl_active = r.scalar() or 0

        return {
            "total_memories": total,
            "short_term_count": stats[MemoryType.SHORT_TERM],
            "long_term_count": stats[MemoryType.LONG_TERM],
            "shared_count": stats[MemoryType.SHARED],
            "category_distribution": categories,
            "avg_importance": avg_imp,
            "sensitive_count": sensitive_count,
            "forgotten_count": forgotten_count,
            "ttl_active_count": ttl_active,
        }

    async def record_analytics_snapshot(self, agent_id: str) -> MemoryAnalytics:
        """记录当前时刻的记忆分析快照"""
        stats = await self.get_memory_stats(agent_id)
        analytics = MemoryAnalytics(
            agent_id=agent_id,
            period="realtime",
            total_memories=stats["total_memories"],
            short_term_count=stats["short_term_count"],
            long_term_count=stats["long_term_count"],
            shared_count=stats["shared_count"],
            forgotten_count=stats["forgotten_count"],
            category_distribution=json.dumps(stats["category_distribution"], ensure_ascii=False),
            avg_importance=stats["avg_importance"],
            high_importance_count=stats.get("high_importance_count", 0),
            medium_importance_count=stats.get("medium_importance_count", 0),
            low_importance_count=stats.get("low_importance_count", 0),
        )
        self.db.add(analytics)
        await self.db.flush()
        return analytics

    # ----------------------------------------------------------
    # GDPR 合规
    # ----------------------------------------------------------

    async def gdpr_delete_user_data(self, user_id: str) -> int:
        """GDPR 删除：清除指定用户创建的所有记忆（硬删除）"""
        result = await self.db.execute(
            sa_delete(AgentMemory).where(AgentMemory.created_by == user_id)
        )
        return result.rowcount

    async def gdpr_export_user_data(self, user_id: str) -> list[dict]:
        """GDPR 导出：导出指定用户创建的所有记忆"""
        result = await self.db.execute(
            select(AgentMemory).where(AgentMemory.created_by == user_id)
        )
        memories = result.scalars().all()
        return [
            {
                "id": m.id,
                "agent_id": m.agent_id,
                "memory_type": m.memory_type,
                "title": m.title,
                "content": m.content,
                "category": m.category,
                "importance_score": m.importance_score,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in memories
        ]
