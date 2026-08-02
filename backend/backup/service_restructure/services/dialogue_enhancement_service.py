"""
对话增强服务 — Human-in-the-loop / 质量评分 / 满意度 / 高级导出
"""
import csv
import io
import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, func as sa_func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Message
from app.models.dialogue_enhancement import (

from sqlalchemy.orm import selectinload, joinedload
    HumanIntervention, DialogueRating, RatingAnalytics,
)


class DialogueEnhancementService:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ----------------------------------------------------------
    # Human-in-the-Loop
    # ----------------------------------------------------------

    async def create_intervention(
        self,
        conversation_id: str,
        agent_id: str,
        intervention_type: str,
        original_content: str,
        message_id: str = "",
        handled_by: str = "",
    ) -> HumanIntervention:
        """创建人工介入请求"""
        intervention = HumanIntervention(
            conversation_id=conversation_id,
            message_id=message_id,
            agent_id=agent_id,
            intervention_type=intervention_type,
            original_content=original_content,
            status="pending",
            handled_by=handled_by,
        )
        self.db.add(intervention)
        await self.db.flush()
        return intervention

    async def approve_intervention(self, intervention_id: str, note: str = ""
                                   ) -> Optional[HumanIntervention]:
        """审批通过人工介入"""
        r = await self.db.execute(
            select(HumanIntervention).where(HumanIntervention.id == intervention_id)
        )
        inv = r.scalar_one_or_none()
        if not inv:
            return None
        inv.approved = True
        inv.approval_note = note
        inv.status = "approved"
        inv.handled_at = datetime.now(timezone.utc)
        await self.db.flush()
        return inv

    async def reject_intervention(self, intervention_id: str, note: str = ""
                                  ) -> Optional[HumanIntervention]:
        """驳回人工介入"""
        r = await self.db.execute(
            select(HumanIntervention).where(HumanIntervention.id == intervention_id)
        )
        inv = r.scalar_one_or_none()
        if not inv:
            return None
        inv.approved = False
        inv.approval_note = note
        inv.status = "rejected"
        inv.handled_at = datetime.now(timezone.utc)
        await self.db.flush()
        return inv

    async def modify_content(self, intervention_id: str, new_content: str
                            ) -> Optional[HumanIntervention]:
        """修改 AI 回复内容"""
        r = await self.db.execute(
            select(HumanIntervention).where(HumanIntervention.id == intervention_id)
        )
        inv = r.scalar_one_or_none()
        if not inv:
            return None
        inv.modified_content = new_content
        inv.status = "modified"
        inv.handled_at = datetime.now(timezone.utc)
        await self.db.flush()
        return inv

    async def list_interventions(
        self,
        conversation_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[HumanIntervention], int]:
        conditions = []
        if conversation_id:
            conditions.append(HumanIntervention.conversation_id == conversation_id)
        if agent_id:
            conditions.append(HumanIntervention.agent_id == agent_id)
        if status:
            conditions.append(HumanIntervention.status == status)

        where = and_(*conditions) if conditions else True
        count_q = select(sa_func.count()).select_from(HumanIntervention).where(where)
        total = (await self.db.execute(count_q)).scalar() or 0

        r = await self.db.execute(
            select(HumanIntervention).where(where)
            .order_by(HumanIntervention.created_at.desc())
            .offset(offset).limit(limit)
        )
        return list(r.scalars().all()), total

    # ----------------------------------------------------------
    # 对话评分
    # ----------------------------------------------------------

    async def create_rating(self, data: dict[str, Any]) -> DialogueRating:
        """创建评分记录，自动计算综合分"""
        scores = [
            data.get("relevance_score", 0) or 0,
            data.get("accuracy_score", 0) or 0,
            data.get("completeness_score", 0) or 0,
            data.get("clarity_score", 0) or 0,
            data.get("speed_score", 0) or 0,
        ]
        valid_scores = [s for s in scores if s > 0]
        overall = round(sum(valid_scores) / len(valid_scores), 2) if valid_scores else 0.0

        rating = DialogueRating(
            conversation_id=data["conversation_id"],
            message_id=data.get("message_id", ""),
            satisfaction_score=data.get("satisfaction_score"),
            relevance_score=data.get("relevance_score"),
            accuracy_score=data.get("accuracy_score"),
            completeness_score=data.get("completeness_score"),
            clarity_score=data.get("clarity_score"),
            speed_score=data.get("speed_score"),
            overall_score=overall,
            feedback_text=data.get("feedback_text", ""),
            feedback_category=data.get("feedback_category", "neutral"),
            rated_by=data.get("rated_by", ""),
            rated_by_type=data.get("rated_by_type", "user"),
        )
        self.db.add(rating)
        await self.db.flush()
        return rating

    async def list_ratings(
        self,
        conversation_id: Optional[str] = None,
        min_overall: Optional[float] = None,
        feedback_category: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[DialogueRating], int]:
        conditions = []
        if conversation_id:
            conditions.append(DialogueRating.conversation_id == conversation_id)
        if min_overall is not None:
            conditions.append(DialogueRating.overall_score >= min_overall)
        if feedback_category:
            conditions.append(DialogueRating.feedback_category == feedback_category)

        where = and_(*conditions) if conditions else True
        count_q = select(sa_func.count()).select_from(DialogueRating).where(where)
        total = (await self.db.execute(count_q)).scalar() or 0

        r = await self.db.execute(
            select(DialogueRating).where(where)
            .order_by(DialogueRating.created_at.desc())
            .offset(offset).limit(limit)
        )
        return list(r.scalars().all()), total

    async def get_rating_stats(self) -> dict[str, Any]:
        """获取评分统计"""
        r = await self.db.execute(select(DialogueRating))
        ratings = list(r.scalars().all())

        if not ratings:
            return {
                "total_ratings": 0,
                "avg_satisfaction": 0,
                "avg_overall": 0,
                "avg_relevance": 0, "avg_accuracy": 0,
                "avg_completeness": 0, "avg_clarity": 0, "avg_speed": 0,
                "satisfaction_distribution": {},
                "category_distribution": {},
            }

        total = len(ratings)
        satisfaction_dist: dict[str, int] = {}
        category_dist: dict[str, int] = {}
        sum_sat = sum_rel = sum_acc = sum_com = sum_cla = sum_spd = sum_ov = 0

        for r in ratings:
            if r.satisfaction_score:
                k = str(r.satisfaction_score)
                satisfaction_dist[k] = satisfaction_dist.get(k, 0) + 1
                sum_sat += r.satisfaction_score
            if r.feedback_category:
                category_dist[r.feedback_category] = category_dist.get(r.feedback_category, 0) + 1
            sum_rel += r.relevance_score or 0
            sum_acc += r.accuracy_score or 0
            sum_com += r.completeness_score or 0
            sum_cla += r.clarity_score or 0
            sum_spd += r.speed_score or 0
            sum_ov += r.overall_score or 0

        return {
            "total_ratings": total,
            "avg_satisfaction": round(sum_sat / total, 2) if sum_sat else 0,
            "avg_overall": round(sum_ov / total, 2),
            "avg_relevance": round(sum_rel / total, 2),
            "avg_accuracy": round(sum_acc / total, 2),
            "avg_completeness": round(sum_com / total, 2),
            "avg_clarity": round(sum_cla / total, 2),
            "avg_speed": round(sum_spd / total, 2),
            "satisfaction_distribution": dict(sorted(satisfaction_dist.items())),
            "category_distribution": category_dist,
        }

    async def record_analytics_snapshot(self, period: str = "realtime") -> RatingAnalytics:
        """记录评分分析快照"""
        stats = await self.get_rating_stats()
        analytics = RatingAnalytics(
            period=period,
            total_ratings=stats["total_ratings"],
            avg_satisfaction=stats["avg_satisfaction"],
            avg_relevance=stats["avg_relevance"],
            avg_accuracy=stats["avg_accuracy"],
            avg_completeness=stats["avg_completeness"],
            avg_clarity=stats["avg_clarity"],
            avg_speed=stats["avg_speed"],
            avg_overall=stats["avg_overall"],
            satisfaction_distribution=json.dumps(stats["satisfaction_distribution"], ensure_ascii=False),
            category_distribution=json.dumps(stats["category_distribution"], ensure_ascii=False),
        )
        self.db.add(analytics)
        await self.db.flush()
        return analytics

    # ----------------------------------------------------------
    # 高级导出 (CSV)
    # ----------------------------------------------------------

    async def export_conversation_csv(self, conversation_id: str) -> str:
        """导出对话为 CSV"""
        r = await self.db.execute(
            select(Message).where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        messages = list(r.scalars().all())

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["序号", "角色", "内容", "Token数", "模型", "时间"])

        for i, m in enumerate(messages, 1):
            writer.writerow([
                i,
                m.role,
                m.content[:500] if m.content else "",
                m.total_tokens or 0,
                m.model_used or "",
                m.created_at.isoformat() if m.created_at else "",
            ])

        return output.getvalue()

    async def export_conversation_pdf_html(self, conversation_id: str) -> str:
        """导出对话为 HTML（用于打印/转 PDF）"""
        r = await self.db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = r.scalar_one_or_none()
        if not conv:
            raise ValueError("对话不存在")

        r2 = await self.db.execute(
            select(Message).where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        messages = list(r2.scalars().all())

        html_parts = [f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{conv.title or '对话导出'}</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; }}
  h1 {{ font-size: 1.5em; color: #333; }}
  .meta {{ color: #666; font-size: 0.9em; margin-bottom: 20px; }}
  .msg {{ margin: 12px 0; padding: 12px; border-radius: 8px; }}
  .msg.user {{ background: #e3f2fd; }}
  .msg.assistant {{ background: #f3e5f5; }}
  .msg.system {{ background: #fff3e0; }}
  .role {{ font-weight: bold; font-size: 0.85em; margin-bottom: 4px; }}
  .content {{ white-space: pre-wrap; font-size: 0.95em; }}
  .time {{ color: #999; font-size: 0.75em; margin-top: 4px; }}
  @media print {{ body {{ margin: 0; }} }}
</style></head><body>
<h1>{conv.title or '对话导出'}</h1>
<div class="meta">消息数: {len(messages)} | 创建时间: {conv.created_at}</div>
<hr>"""]

        for m in messages:
            role_label = {"user": "👤 用户", "assistant": "🤖 AI", "system": "⚙️ 系统", "tool": "🔧 工具"}.get(m.role, m.role)
            html_parts.append(f"""<div class="msg {m.role}">
  <div class="role">{role_label}</div>
  <div class="content">{m.content}</div>
  <div class="time">{'Token: ' + str(m.total_tokens) if m.total_tokens else ''} | {m.created_at}</div>
</div>""")

        html_parts.append("</body></html>")
        return "\n".join(html_parts)

    async def list_conversations_for_export(
        self,
        agent_id: Optional[str] = None,
        user_id: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Conversation], int]:
        """获取可用于导出的对话列表"""
        conditions = []
        if agent_id:
            conditions.append(Conversation.agent_id == agent_id)
        if user_id:
            conditions.append(Conversation.user_id == user_id)

        where = and_(*conditions) if conditions else True
        count_q = select(sa_func.count()).select_from(Conversation).where(where)
        total = (await self.db.execute(count_q)).scalar() or 0

        r = await self.db.execute(
            select(Conversation).where(where)
            .order_by(Conversation.updated_at.desc())
            .offset(offset).limit(limit)
        )
        return list(r.scalars().all()), total

    # ----------------------------------------------------------
    # 4.15.7 批量导出（多选会话）
    # ----------------------------------------------------------

    _SENSITIVE_PATTERNS = [
        (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "***@***"),
        (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "1**********"),
        (re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"), "******************"),
        (re.compile(r"(?<!\d)\d{15}(?!\d)"), "***************"),
    ]

    @staticmethod
    def _mask_text(text: str) -> str:
        """脱敏：邮箱 / 手机号 / 身份证 / 银行卡号"""
        if not text:
            return text
        for pattern, repl in DialogueEnhancementService._SENSITIVE_PATTERNS:
            text = pattern.sub(repl, text)
        return text

    async def batch_export_conversations(
        self,
        conversation_ids: list[str],
        export_format: str = "csv",
        include_metadata: bool = False,
        mask_sensitive: bool = False,
    ) -> tuple[str, str]:
        """批量导出多个对话，返回 (内容, 建议文件名)。
        支持格式: csv / json / html
        """
        export_format = (export_format or "csv").lower()
        if export_format not in ("csv", "json", "html"):
            raise ValueError("不支持的导出格式，仅支持 csv / json / html")

        results: list[tuple[Conversation, list[Message]]] = []
        for cid in conversation_ids:
            r = await self.db.execute(
                select(Conversation).where(Conversation.id == cid)
            )
            conv = r.scalar_one_or_none()
            if not conv:
                continue
            r2 = await self.db.execute(
                select(Message).where(Message.conversation_id == cid)
                .order_by(Message.created_at)
            )
            results.append((conv, list(r2.scalars().all())))

        if not results:
            raise ValueError("未找到可导出的对话，请检查所选会话是否存在")

        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        if export_format == "json":
            content = self._batch_to_json(results, include_metadata, mask_sensitive)
            return content, f"conversations_batch_{ts}.json"
        if export_format == "html":
            content = self._batch_to_html(results, include_metadata, mask_sensitive)
            return content, f"conversations_batch_{ts}.html"
        content = self._batch_to_csv(results, include_metadata, mask_sensitive)
        return content, f"conversations_batch_{ts}.csv"

    def _batch_to_csv(
        self,
        results: list[tuple[Conversation, list[Message]]],
        include_metadata: bool,
        mask_sensitive: bool,
    ) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        if include_metadata:
            writer.writerow(["对话ID", "对话标题", "Agent", "用户", "序号", "角色", "内容", "Token数", "模型", "时间"])
        else:
            writer.writerow(["对话ID", "序号", "角色", "内容", "Token数", "模型", "时间"])

        for conv, messages in results:
            for i, m in enumerate(messages, 1):
                content = m.content or ""
                if mask_sensitive:
                    content = self._mask_text(content)
                row = [conv.id]
                if include_metadata:
                    row += [conv.title or "", conv.agent_id, conv.user_id]
                row += [
                    i,
                    m.role,
                    content[:500],
                    m.total_tokens or 0,
                    m.model_used or "",
                    m.created_at.isoformat() if m.created_at else "",
                ]
                writer.writerow(row)
        return output.getvalue()

    def _batch_to_json(
        self,
        results: list[tuple[Conversation, list[Message]]],
        include_metadata: bool,
        mask_sensitive: bool,
    ) -> str:
        payload = []
        for conv, messages in results:
            item: dict[str, Any] = {
                "conversation_id": conv.id,
                "title": conv.title or "",
            }
            if include_metadata:
                item["agent_id"] = conv.agent_id
                item["user_id"] = conv.user_id
                item["workspace_id"] = getattr(conv, "workspace_id", None)
                item["status"] = getattr(conv, "status", None)
                item["message_count"] = len(messages)
                item["token_count"] = getattr(conv, "token_count", None)
                item["created_at"] = conv.created_at.isoformat() if conv.created_at else None
                item["updated_at"] = conv.updated_at.isoformat() if conv.updated_at else None

            messages_out = []
            for m in messages:
                content = m.content or ""
                if mask_sensitive:
                    content = self._mask_text(content)
                msg: dict[str, Any] = {
                    "role": m.role,
                    "content": content,
                    "content_type": getattr(m, "content_type", None),
                    "total_tokens": m.total_tokens or 0,
                    "model_used": m.model_used or "",
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                if include_metadata:
                    msg["message_id"] = m.id
                    msg["prompt_tokens"] = getattr(m, "prompt_tokens", None) or 0
                    msg["completion_tokens"] = getattr(m, "completion_tokens", None) or 0
                messages_out.append(msg)
            item["messages"] = messages_out
            payload.append(item)
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _batch_to_html(
        self,
        results: list[tuple[Conversation, list[Message]]],
        include_metadata: bool,
        mask_sensitive: bool,
    ) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        parts = [f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>批量对话导出</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; }}
  h1 {{ font-size: 1.5em; color: #333; }}
  h2 {{ font-size: 1.2em; color: #444; margin-top: 28px; border-bottom: 1px solid #eee; padding-bottom: 6px; }}
  .meta {{ color: #666; font-size: 0.9em; margin-bottom: 20px; }}
  .msg {{ margin: 12px 0; padding: 12px; border-radius: 8px; }}
  .msg.user {{ background: #e3f2fd; }}
  .msg.assistant {{ background: #f3e5f5; }}
  .msg.system {{ background: #fff3e0; }}
  .msg.tool {{ background: #e8f5e9; }}
  .role {{ font-weight: bold; font-size: 0.85em; margin-bottom: 4px; }}
  .content {{ white-space: pre-wrap; font-size: 0.95em; }}
  .time {{ color: #999; font-size: 0.75em; margin-top: 4px; }}
  @media print {{ body {{ margin: 0; }} }}
</style></head><body>
<h1>📦 批量对话导出</h1>
<div class="meta">共 {len(results)} 个对话 | 导出时间: {now}{' | 已脱敏' if mask_sensitive else ''}</div>"""]

        for idx, (conv, messages) in enumerate(results, 1):
            parts.append(f'<h2>{idx}. {conv.title or "无标题对话"}</h2>')
            if include_metadata:
                parts.append(
                    f'<div class="meta">对话ID: {conv.id} | Agent: {conv.agent_id} | '
                    f'用户: {conv.user_id} | 消息数: {len(messages)} | '
                    f'创建: {conv.created_at}</div>'
                )
            for m in messages:
                role_label = {"user": "👤 用户", "assistant": "🤖 AI", "system": "⚙️ 系统", "tool": "🔧 工具"}.get(m.role, m.role)
                content = m.content or ""
                if mask_sensitive:
                    content = self._mask_text(content)
                parts.append(f"""<div class="msg {m.role}">
  <div class="role">{role_label}</div>
  <div class="content">{content}</div>
  <div class="time">{'Token: ' + str(m.total_tokens) if m.total_tokens else ''} | {m.created_at}</div>
</div>""")

        parts.append("</body></html>")
        return "\n".join(parts)
