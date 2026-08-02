"""
4.16 Token 使用管理与优化 服务
核心能力：
1. Token 用量持久化记录与统计（实时/历史趋势/模型分布/用户配额）
2. 成本控制：预算告警、用量限制、模型降级级联、成本分摊
3. 优化策略：Prompt 压缩、缓存命中、上下文裁剪、Token 预算控制
4. 模型选择建议（任务-模型匹配矩阵 + 性价比）
5. 优化效果评估（压缩率/缓存命中率/成本节省率）
"""
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token import (
    TokenUsage, TokenBudget, TokenAlert, ModelCascadeRule, TokenOptimizationStat,
)

# 模型价格表（USD per 1M tokens）
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "gpt-4o": {"input": 2.5, "output": 10},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "gpt-4-turbo": {"input": 10, "output": 30},
    "claude-3-5-sonnet-20241022": {"input": 3, "output": 15},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "gemini-1.5-pro": {"input": 1.25, "output": 5},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.3},
    "deepseek-chat": {"input": 0.27, "output": 1.1},
    "deepseek-r1": {"input": 0.55, "output": 2.19},
    "qwen2.5-72b": {"input": 0.4, "output": 1.2},
    "glm-4-plus": {"input": 0.5, "output": 2.0},
    "llama-3.1-70b": {"input": 0.3, "output": 0.9},
}

# 任务-模型匹配矩阵（建议模型 + 性价比评分 0-100）
TASK_MODEL_MATRIX: Dict[str, List[Dict[str, Any]]] = {
    "chat": [
        {"model": "gpt-4o-mini", "score": 92, "reason": "日常对话性价比最高"},
        {"model": "deepseek-chat", "score": 90, "reason": "中文友好，成本低"},
        {"model": "gpt-4o", "score": 85, "reason": "复杂对话更准确"},
    ],
    "code": [
        {"model": "claude-3-5-sonnet-20241022", "score": 95, "reason": "代码能力业界领先"},
        {"model": "gpt-4o", "score": 90, "reason": "代码生成与调试均衡"},
        {"model": "qwen2.5-72b", "score": 82, "reason": "开源代码模型高性价比"},
    ],
    "analysis": [
        {"model": "gpt-4o", "score": 90, "reason": "复杂推理与数据分析"},
        {"model": "deepseek-r1", "score": 93, "reason": "深度推理强"},
        {"model": "deepseek-chat", "score": 85, "reason": "统计分析成本低"},
    ],
    "writing": [
        {"model": "claude-3-5-sonnet-20241022", "score": 88, "reason": "长文质量高"},
        {"model": "gpt-4o", "score": 86, "reason": "写作风格灵活"},
        {"model": "gpt-4o-mini", "score": 80, "reason": "短文润色性价比高"},
    ],
    "translation": [
        {"model": "gpt-4o-mini", "score": 90, "reason": "翻译质量/成本均衡"},
        {"model": "deepseek-chat", "score": 88, "reason": "中英互译优秀"},
        {"model": "gemini-1.5-flash", "score": 85, "reason": "多语种覆盖广"},
    ],
}

# 内置级联链
DEFAULT_CASCADE_CHAIN = ["gpt-4o", "gpt-4o-mini", "deepseek-chat"]


class TokenService:
    """Token 用量记录 / 统计 / 成本控制"""

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """粗略估算 Token 数（中文约 1 字/Token，英文约 4 字符/Token）"""
        if not text:
            return 0
        cjk = sum(1 for c in text if ord(c) > 0x2E80)
        ascii_chars = len(text) - cjk
        return max(1, cjk + ascii_chars // 4)

    @staticmethod
    def calc_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
        pricing = MODEL_PRICING.get(model_name, {"input": 0, "output": 0})
        return round(
            input_tokens / 1_000_000 * pricing["input"]
            + output_tokens / 1_000_000 * pricing["output"], 6
        )

    @staticmethod
    async def record_usage(
        session: AsyncSession,
        *,
        user_id: str,
        model_name: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        agent_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        cached_tokens: int = 0,
        compressed_tokens: int = 0,
    ) -> Dict[str, Any]:
        """记录一次 Token 用量，并触发预算检查"""
        now = datetime.utcnow()
        date_key = now.strftime("%Y-%m-%d")
        cost = TokenService.calc_cost(model_name, input_tokens, output_tokens)

        record = TokenUsage(
            user_id=user_id,
            agent_id=agent_id,
            conversation_id=conversation_id,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            compressed_tokens=compressed_tokens,
            cost=cost,
            usage_date=date_key,
        )
        session.add(record)

        # 更新当日优化统计
        stmt = select(TokenOptimizationStat).where(TokenOptimizationStat.usage_date == date_key)
        stat = (await session.execute(stmt)).scalars().first()
        if not stat:
            stat = TokenOptimizationStat(usage_date=date_key)
            session.add(stat)
        stat.total_input += input_tokens
        stat.total_output += output_tokens
        stat.total_cost += cost
        stat.cached_tokens += cached_tokens
        stat.compressed_tokens += compressed_tokens

        await session.commit()

        # 预算检查（不因检查失败而影响记录）
        try:
            budget_check = await TokenService.check_budget(session, user_id, input_tokens + output_tokens)
        except Exception:
            budget_check = {"blocked": False, "alerts": [], "usage_pct": None}

        return {
            "recorded": True,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost": cost,
            **budget_check,
        }

    @staticmethod
    async def check_budget(session: AsyncSession, user_id: str, delta_tokens: int = 0) -> Dict[str, Any]:
        """预算/配额检查：返回用量百分比、是否阻断、触发的告警"""
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_key = now.strftime("%Y-%m")

        budget = (await session.execute(
            select(TokenBudget).where(TokenBudget.user_id == user_id)
        )).scalars().first()
        if not budget:
            budget = TokenBudget(user_id=user_id)
            session.add(budget)
            await session.commit()

        # 当月用量聚合
        month_records = (await session.execute(
            select(
                func.sum(TokenUsage.input_tokens).label("inp"),
                func.sum(TokenUsage.output_tokens).label("out"),
                func.sum(TokenUsage.cost).label("cost"),
            ).where(
                TokenUsage.user_id == user_id,
                TokenUsage.created_at >= month_start,
            )
        )).one()
        month_tokens = (month_records.inp or 0) + (month_records.out or 0) + delta_tokens
        month_cost = (month_records.cost or 0) + delta_tokens / 1_000_000 * 0.5  # 粗略

        usage_pct = min(100, int(month_tokens / budget.token_quota * 100)) if budget.token_quota else 0
        cost_pct = min(100, int(month_cost / budget.monthly_budget * 100)) if budget.monthly_budget else 0

        blocked = False
        alerts: List[Dict[str, Any]] = []

        if usage_pct >= budget.alert_threshold:
            # 检查是否已有同月未关闭告警
            existing = (await session.execute(
                select(TokenAlert).where(
                    TokenAlert.user_id == user_id,
                    TokenAlert.alert_type == "quota",
                    TokenAlert.status == "open",
                )
            )).scalars().first()
            if not existing:
                alert = TokenAlert(
                    user_id=user_id,
                    alert_type="quota",
                    severity="critical" if usage_pct >= 100 else "warning",
                    message=f"Token 配额已达 {usage_pct}%（{month_tokens}/{budget.token_quota}）",
                    threshold_pct=budget.alert_threshold,
                    current_usage=month_tokens,
                )
                session.add(alert)
                await session.commit()
                alerts.append({"type": "quota", "usage_pct": usage_pct})

        if usage_pct >= 100 and budget.block_when_exceeded:
            blocked = True

        return {
            "blocked": blocked,
            "usage_pct": usage_pct,
            "cost_pct": cost_pct,
            "month_tokens": month_tokens,
            "month_cost": round(month_cost, 4),
            "quota": budget.token_quota,
            "monthly_budget": budget.monthly_budget,
            "alerts": alerts,
        }

    @staticmethod
    async def get_stats(
        session: AsyncSession,
        user_id: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Token 统计：总计/模型分布/日趋势/用户排名"""
        since = datetime.utcnow() - timedelta(days=days)
        filters = [TokenUsage.created_at >= since]
        if user_id:
            filters.append(TokenUsage.user_id == user_id)

        # 总体
        totals = (await session.execute(
            select(
                func.count(TokenUsage.id).label("records"),
                func.sum(TokenUsage.input_tokens).label("inp"),
                func.sum(TokenUsage.output_tokens).label("out"),
                func.sum(TokenUsage.cost).label("cost"),
                func.sum(TokenUsage.cached_tokens).label("cached"),
                func.sum(TokenUsage.compressed_tokens).label("compressed"),
            ).where(*filters)
        )).one()

        # 模型分布
        model_rows = (await session.execute(
            select(
                TokenUsage.model_name,
                func.sum(TokenUsage.input_tokens).label("inp"),
                func.sum(TokenUsage.output_tokens).label("out"),
                func.sum(TokenUsage.cost).label("cost"),
                func.count(TokenUsage.id).label("calls"),
            ).where(*filters).group_by(TokenUsage.model_name)
        )).all()
        by_model = [
            {
                "model": r.model_name,
                "input_tokens": int(r.inp or 0),
                "output_tokens": int(r.out or 0),
                "cost": round(r.cost or 0, 4),
                "calls": int(r.calls or 0),
            }
            for r in model_rows
        ]

        # 日趋势
        day_rows = (await session.execute(
            select(
                TokenUsage.usage_date,
                func.sum(TokenUsage.input_tokens).label("inp"),
                func.sum(TokenUsage.output_tokens).label("out"),
                func.sum(TokenUsage.cost).label("cost"),
            ).where(*filters).group_by(TokenUsage.usage_date).order_by(TokenUsage.usage_date)
        )).all()
        daily = [
            {"date": r.usage_date, "input": int(r.inp or 0), "output": int(r.out or 0), "cost": round(r.cost or 0, 4)}
            for r in day_rows
        ]

        # 用户排名（成本分摊）
        user_rows = (await session.execute(
            select(
                TokenUsage.user_id,
                func.sum(TokenUsage.input_tokens).label("inp"),
                func.sum(TokenUsage.output_tokens).label("out"),
                func.sum(TokenUsage.cost).label("cost"),
            ).where(*filters).group_by(TokenUsage.user_id).order_by(func.sum(TokenUsage.cost).desc()).limit(10)
        )).all()
        by_user = [
            {"user_id": r.user_id, "input_tokens": int(r.inp or 0), "output_tokens": int(r.out or 0), "cost": round(r.cost or 0, 4)}
            for r in user_rows
        ]

        return {
            "total_tokens": int((totals.inp or 0) + (totals.out or 0)),
            "total_cost": round(totals.cost or 0, 4),
            "total_records": int(totals.records or 0),
            "cached_tokens": int(totals.cached or 0),
            "compressed_tokens": int(totals.compressed or 0),
            "by_model": by_model,
            "daily": daily,
            "by_user": by_user,
        }

    @staticmethod
    async def get_user_budget(session: AsyncSession, user_id: str) -> Dict[str, Any]:
        budget = (await session.execute(
            select(TokenBudget).where(TokenBudget.user_id == user_id)
        )).scalars().first()
        if not budget:
            budget = TokenBudget(user_id=user_id)
            session.add(budget)
            await session.commit()
        check = await TokenService.check_budget(session, user_id)
        return {
            "monthly_budget": budget.monthly_budget,
            "token_quota": budget.token_quota,
            "alert_threshold": budget.alert_threshold,
            "block_when_exceeded": budget.block_when_exceeded,
            "cascade_enabled": budget.cascade_enabled,
            "cascade_chain": json.loads(budget.cascade_chain) if budget.cascade_chain else DEFAULT_CASCADE_CHAIN,
            **check,
        }

    @staticmethod
    async def update_budget(session: AsyncSession, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        budget = (await session.execute(
            select(TokenBudget).where(TokenBudget.user_id == user_id)
        )).scalars().first()
        if not budget:
            budget = TokenBudget(user_id=user_id)
            session.add(budget)
        for k, v in data.items():
            if k == "cascade_chain" and isinstance(v, list):
                budget.cascade_chain = json.dumps(v, ensure_ascii=False)
            elif hasattr(budget, k) and v is not None:
                setattr(budget, k, v)
        await session.commit()
        return await TokenService.get_user_budget(session, user_id)

    @staticmethod
    async def list_alerts(
        session: AsyncSession,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        filters = []
        if user_id:
            filters.append(TokenAlert.user_id == user_id)
        if status:
            filters.append(TokenAlert.status == status)
        rows = (await session.execute(
            select(TokenAlert).where(*filters).order_by(TokenAlert.created_at.desc()).limit(limit)
        )).scalars().all()
        return [{
            "id": r.id, "user_id": r.user_id, "alert_type": r.alert_type,
            "severity": r.severity, "message": r.message,
            "threshold_pct": r.threshold_pct, "current_usage": r.current_usage,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows]

    @staticmethod
    async def update_alert(session: AsyncSession, alert_id: str, status: str) -> Dict[str, Any]:
        alert = await session.get(TokenAlert, alert_id)
        if not alert:
            raise ValueError("告警不存在")
        alert.status = status
        await session.commit()
        return {"id": alert_id, "status": status}


class OptimizationService:
    """Token 优化策略与效果评估"""

    @staticmethod
    async def optimize_context(
        session: AsyncSession,
        messages: List[Dict[str, Any]],
        max_tokens: int = 8000,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """上下文裁剪：系统消息 + 最近消息，返回裁剪报告"""
        if not messages:
            return {"messages": [], "original_tokens": 0, "compressed_tokens": 0, "ratio": 0}

        result: List[Dict[str, Any]] = []
        total = 0
        original_total = 0

        def est(m):
            text = m.get("content", "")
            t = TokenService.estimate_tokens(text)
            return max(1, t)

        # 系统消息优先保留
        for m in messages:
            t = est(m)
            original_total += t
        for m in messages:
            if m.get("role") == "system":
                t = est(m)
                if total + t <= max_tokens:
                    result.append(m)
                    total += t

        # 从最近消息往前添加
        for m in reversed([x for x in messages if x.get("role") != "system"]):
            t = est(m)
            if total + t <= max_tokens:
                result.insert(0, m)
                total += t

        kept_tokens = sum(est(m) for m in result)
        compressed = max(0, original_total - kept_tokens)
        return {
            "messages": result,
            "original_tokens": original_total,
            "compressed_tokens": compressed,
            "kept_tokens": kept_tokens,
            "ratio": round(compressed / original_total * 100, 1) if original_total else 0,
        }

    @staticmethod
    async def suggest_model(task_type: str, input_tokens: int = 0) -> Dict[str, Any]:
        """模型选择建议（任务-模型匹配矩阵）"""
        candidates = TASK_MODEL_MATRIX.get(task_type, TASK_MODEL_MATRIX["chat"])
        suggestion = candidates[0]
        if input_tokens > 8000:
            suggestion = candidates[0]  # 长输入仍推荐强模型
        return {
            "task_type": task_type,
            "suggested_model": suggestion["model"],
            "score": suggestion["score"],
            "reason": suggestion["reason"],
            "alternatives": candidates[1:],
        }

    @staticmethod
    async def get_effectiveness(session: AsyncSession, days: int = 30) -> Dict[str, Any]:
        """优化效果评估：压缩率 / 缓存命中率 / 成本节省率"""
        since = datetime.utcnow() - timedelta(days=days)
        rows = (await session.execute(
            select(TokenOptimizationStat).where(
                TokenOptimizationStat.usage_date >= since.strftime("%Y-%m-%d")
            )
        )).scalars().all()

        total_input = sum(r.total_input for r in rows)
        total_output = sum(r.total_output for r in rows)
        total_cost = sum(r.total_cost for r in rows)
        cached = sum(r.cached_tokens for r in rows)
        compressed = sum(r.compressed_tokens for r in rows)
        cascade_saved = sum(r.cascade_saved_cost for r in rows)

        cache_hit_rate = round(cached / (total_input + total_output) * 100, 2) if (total_input + total_output) else 0
        compression_rate = round(compressed / (total_input + compressed) * 100, 2) if (total_input + compressed) else 0
        cost_saved = round(total_cost * (compression_rate / 100) + cascade_saved, 4)

        return {
            "days": days,
            "total_input": total_input,
            "total_output": total_output,
            "total_cost": round(total_cost, 4),
            "cached_tokens": cached,
            "compressed_tokens": compressed,
            "cache_hit_rate": cache_hit_rate,
            "compression_rate": compression_rate,
            "cascade_saved_cost": round(cascade_saved, 4),
            "cost_saved": cost_saved,
            "estimated_saving_rate": round(cost_saved / (total_cost + cost_saved) * 100, 2) if (total_cost + cost_saved) else 0,
        }

    @staticmethod
    async def get_cascade_plan(session: AsyncSession, task_type: str = "chat") -> Dict[str, Any]:
        """模型级联计划：主模型 + 降级链"""
        rule = (await session.execute(
            select(ModelCascadeRule).where(ModelCascadeRule.task_type == task_type)
        )).scalars().first()
        if not rule:
            return {
                "task_type": task_type,
                "primary_model": DEFAULT_CASCADE_CHAIN[0],
                "fallback_chain": DEFAULT_CASCADE_CHAIN[1:],
                "max_input_tokens": 8000,
                "enabled": True,
            }
        chain = json.loads(rule.fallback_chain) if rule.fallback_chain else DEFAULT_CASCADE_CHAIN[1:]
        return {
            "task_type": rule.task_type,
            "primary_model": rule.primary_model,
            "fallback_chain": chain,
            "max_input_tokens": rule.max_input_tokens,
            "enabled": rule.enabled,
        }

    @staticmethod
    async def save_cascade_rule(session: AsyncSession, data: Dict[str, Any]) -> Dict[str, Any]:
        rule = (await session.execute(
            select(ModelCascadeRule).where(ModelCascadeRule.task_type == data["task_type"])
        )).scalars().first()
        if not rule:
            rule = ModelCascadeRule(task_type=data["task_type"])
            session.add(rule)
        if "primary_model" in data:
            rule.primary_model = data["primary_model"]
        if "fallback_chain" in data:
            rule.fallback_chain = json.dumps(data["fallback_chain"], ensure_ascii=False)
        if "max_input_tokens" in data:
            rule.max_input_tokens = data["max_input_tokens"]
        if "enabled" in data:
            rule.enabled = data["enabled"]
        await session.commit()
        return await OptimizationService.get_cascade_plan(session, data["task_type"])

    @staticmethod
    async def list_cascade_rules(session: AsyncSession) -> List[Dict[str, Any]]:
        rules = (await session.execute(select(ModelCascadeRule))).scalars().all()
        result = []
        for r in rules:
            chain = json.loads(r.fallback_chain) if r.fallback_chain else DEFAULT_CASCADE_CHAIN[1:]
            result.append({
                "task_type": r.task_type,
                "primary_model": r.primary_model,
                "fallback_chain": chain,
                "max_input_tokens": r.max_input_tokens,
                "enabled": r.enabled,
            })
        return result
