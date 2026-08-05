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
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _safe_json(s, default=None):
    """安全解析 JSON 字符串"""
    if not s:
        return default or {}
    try:
        return json.loads(s) if isinstance(s, str) else s
    except (json.JSONDecodeError, TypeError):
        return default or {}


from sqlalchemy import func, select
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

        # 预算检查（不因检查失败而影响记录，但失败需可见）
        try:
            budget_check = await TokenService.check_budget(session, user_id, input_tokens + output_tokens)
        except Exception as e:
            logger.warning(f"Token预算检查失败，按不拦截处理: {e}")
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
            "cascade_chain": _safe_json(budget.cascade_chain, DEFAULT_CASCADE_CHAIN),
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


class PromptCompressor:
    """智能 Prompt 压缩器 - 裁剪冗余指令、合并重复内容"""

    @staticmethod
    def compress(
        messages: List[Dict[str, Any]],
        target_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """
        智能压缩对话消息
        策略:
        1. 保留所有 system 消息
        2. 去除重复的 user 消息
        3. 截断超长消息(保留首尾)
        4. 压缩格式化内容(代码块、列表等)
        """
        original_tokens = sum(TokenService.estimate_tokens(m.get("content", "")) for m in messages)
        if original_tokens <= target_tokens:
            return {
                "messages": messages,
                "original_tokens": original_tokens,
                "compressed_tokens": original_tokens,
                "savings": 0,
                "savings_pct": 0,
            }

        result = []
        seen_contents = set()

        # 1. 保留所有 system 消息(去重)
        for m in messages:
            if m.get("role") == "system":
                content = m.get("content", "").strip()
                content_hash = hash(content[:200])
                if content_hash not in seen_contents:
                    seen_contents.add(content_hash)
                    result.append(m)

        # 2. 处理非 system 消息
        non_system = [m for m in messages if m.get("role") != "system"]
        compressed_tokens = sum(TokenService.estimate_tokens(m.get("content", "")) for m in result)

        for m in non_system:
            content = m.get("content", "")
            tokens = TokenService.estimate_tokens(content)

            # 跳过重复内容
            content_hash = hash(content[:200])
            if content_hash in seen_contents:
                continue
            seen_contents.add(content_hash)

            if compressed_tokens + tokens <= target_tokens:
                result.append(m)
                compressed_tokens += tokens
            else:
                # 截断策略: 保留首部和尾部
                remaining = target_tokens - compressed_tokens
                if remaining > 100:
                    truncated = PromptCompressor._truncate_content(content, remaining)
                    if truncated:
                        result.append({
                            "role": m["role"],
                            "content": truncated,
                        })
                        compressed_tokens += TokenService.estimate_tokens(truncated)
                break

        total_compressed = sum(TokenService.estimate_tokens(m.get("content", "")) for m in result)
        savings = original_tokens - total_compressed

        return {
            "messages": result,
            "original_tokens": original_tokens,
            "compressed_tokens": total_compressed,
            "savings": savings,
            "savings_pct": round(savings / original_tokens * 100, 1) if original_tokens else 0,
        }

    @staticmethod
    def _truncate_content(content: str, target_tokens: int) -> str:
        """截断内容: 保留首尾,中间用省略号"""
        if not content:
            return ""
        # 按字符粗略截断(中文1字≈1token, 英文4字符≈1token)
        cjk_count = sum(1 for c in content if ord(c) > 0x2E80)
        char_limit = cjk_count + (target_tokens - cjk_count) * 4

        if len(content) <= char_limit:
            return content

        head_size = char_limit // 2
        tail_size = char_limit - head_size - 20  # 20 chars for marker
        if tail_size < 0:
            return content[:char_limit]

        return (
            content[:head_size]
            + f"\n\n[...已压缩省略 {len(content) - char_limit} 字符...]\n\n"
            + content[-tail_size:]
        )

    @staticmethod
    def compress_for_cascade(
        messages: List[Dict[str, Any]],
        small_model_max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """为小模型压缩: 更激进的截断以适配小模型上下文"""
        return PromptCompressor.compress(messages, target_tokens=small_model_max_tokens)


class CascadeExecutor:
    """模型级联执行器 - 小模型优先,置信度不足时升级"""

    @staticmethod
    async def execute_with_cascade(
        messages: List[Dict[str, Any]],
        cascade_chain: List[str],
        task_type: str = "chat",
        confidence_threshold: float = 0.7,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        模型级联执行:
        1. 先用小模型(cascade_chain[0])处理
        2. 如果返回结果包含低置信度标记,升级到下一个模型
        3. 重复直到达到置信度或用尽链
        """
        from app.services.llm import create_adapter

        results = []
        final_output = ""

        for i, model_name in enumerate(cascade_chain):
            # 构建适配器
            pricing = MODEL_PRICING.get(model_name, {})
            is_small_model = i < len(cascade_chain) - 1

            try:
                adapter = create_adapter("openai", {"model_name": model_name})
                response = await adapter.chat(
                    messages=messages,
                    temperature=0.7,
                )

                output = response.content
                tokens_used = TokenService.estimate_tokens(output)

                results.append({
                    "model": model_name,
                    "output": output,
                    "tokens": tokens_used,
                    "is_primary": i == 0,
                    "success": True,
                })

                # 检查是否需要升级
                if is_small_model:
                    confidence = CascadeExecutor._estimate_confidence(output)
                    if confidence >= confidence_threshold:
                        # 小模型足够好,直接返回
                        final_output = output
                        break
                    else:
                        # 置信度不够,升级
                        logger.info(
                            "模型 %s 置信度 %.2f < %.2f, 升级到 %s",
                            model_name, confidence, confidence_threshold,
                            cascade_chain[i + 1],
                        )
                        continue
                else:
                    final_output = output
                    break

            except Exception as e:
                logger.warning("模型 %s 调用失败: %s", model_name, str(e))
                results.append({
                    "model": model_name,
                    "output": "",
                    "error": "模型调用失败",
                    "is_primary": i == 0,
                    "success": False,
                })
                continue

        if not final_output and results:
            # 所有模型都失败了,使用最后一个成功的输出
            for r in reversed(results):
                if r.get("success"):
                    final_output = r["output"]
                    break

        # 计算成本
        total_cost = 0
        for r in results:
            if r.get("success"):
                total_cost += TokenService.calc_cost(
                    r["model"], 0, r.get("tokens", 0)
                )

        return {
            "output": final_output,
            "models_used": [r["model"] for r in results],
            "cascade_depth": len(results),
            "total_tokens": sum(r.get("tokens", 0) for r in results),
            "estimated_cost": round(total_cost, 6),
            "results": results,
        }

    @staticmethod
    def _estimate_confidence(output: str) -> float:
        """
        估算模型输出置信度(启发式规则):
        - 包含不确定性词汇 → 降低置信度
        - 输出长度适中 → 提高置信度
        - 包含明确结论/数字 → 提高置信度
        """
        confidence = 0.8  # 基准

        # 不确定性词汇
        low_confidence_words = [
            "可能", "也许", "不确定", "不太确定", "大概", "也许吧",
            "possibly", "maybe", "not sure", "uncertain", "might be",
            "我不确定", "不太清楚", "无法确定",
        ]
        for word in low_confidence_words:
            if word in output:
                confidence -= 0.1

        # 确定性词汇
        high_confidence_words = [
            "确定", "答案是", "结果为", "正确的",
            "definitely", "certainly", "the answer is",
        ]
        for word in high_confidence_words:
            if word in output:
                confidence += 0.05

        # 长度适中(50-500字)加分
        length = len(output)
        if 50 <= length <= 500:
            confidence += 0.05
        elif length < 20:
            confidence -= 0.15  # 太短可能是不知道答案

        return max(0.0, min(1.0, confidence))

    @staticmethod
    async def select_and_execute(
        messages: List[Dict[str, Any]],
        task_type: str = "chat",
        user_id: Optional[str] = None,
        session: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        自动选择级联链并执行:
        1. 从数据库获取级联规则
        2. 如果没有则使用默认链
        3. 执行级联
        """
        cascade_chain = DEFAULT_CASCADE_CHAIN
        if session and user_id:
            try:
                budget = (await session.execute(
                    select(TokenBudget).where(TokenBudget.user_id == user_id)
                )).scalars().first()
                if budget and budget.cascade_enabled:
                    chain = _safe_json(budget.cascade_chain, None)
                    if chain:
                        cascade_chain = chain
            except Exception as e:
                logger.warning("获取级联配置失败: %s", str(e))

        return await CascadeExecutor.execute_with_cascade(
            messages=messages,
            cascade_chain=cascade_chain,
            task_type=task_type,
            user_id=user_id,
        )


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
        chain = _safe_json(rule.fallback_chain, DEFAULT_CASCADE_CHAIN[1:])
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
            chain = _safe_json(r.fallback_chain, DEFAULT_CASCADE_CHAIN[1:])
            result.append({
                "task_type": r.task_type,
                "primary_model": r.primary_model,
                "fallback_chain": chain,
                "max_input_tokens": r.max_input_tokens,
                "enabled": r.enabled,
            })
        return result
