"""
会话管理增强服务 - 生命周期/上下文/Token统计/导出
"""
import json
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm import selectinload, joinedload


# ---- Token 统计 ----
token_usage_stats = {
    "total_tokens": 0,
    "total_conversations": 0,
    "total_messages": 0,
    "by_model": {},  # model_name -> {"input_tokens": 0, "output_tokens": 0, "cost": 0}
    "daily_usage": {},  # "YYYY-MM-DD" -> {"input": 0, "output": 0}
}


# 模型价格表（USD per 1M tokens）
MODEL_PRICING = {
    "gpt-4o": {"input": 2.5, "output": 10},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "gpt-4-turbo": {"input": 10, "output": 30},
    "claude-3-5-sonnet-20241022": {"input": 3, "output": 15},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "gemini-1.5-pro": {"input": 1.25, "output": 5},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.3},
    "deepseek-chat": {"input": 0.27, "output": 1.1},
}


def record_token_usage(
    model_name: str,
    input_tokens: int,
    output_tokens: int,
) -> dict:
    """记录 Token 使用"""
    now = datetime.utcnow()
    date_key = now.strftime("%Y-%m-%d")
    total = input_tokens + output_tokens

    token_usage_stats["total_tokens"] += total
    token_usage_stats["total_messages"] += 1

    # 按模型统计
    if model_name not in token_usage_stats["by_model"]:
        token_usage_stats["by_model"][model_name] = {"input_tokens": 0, "output_tokens": 0, "cost": 0.0}
    token_usage_stats["by_model"][model_name]["input_tokens"] += input_tokens
    token_usage_stats["by_model"][model_name]["output_tokens"] += output_tokens

    # 计算成本
    pricing = MODEL_PRICING.get(model_name, {"input": 0, "output": 0})
    cost = (input_tokens / 1_000_000 * pricing["input"]) + (output_tokens / 1_000_000 * pricing["output"])
    token_usage_stats["by_model"][model_name]["cost"] = round(
        token_usage_stats["by_model"][model_name].get("cost", 0) + cost, 6
    )

    # 按日统计
    if date_key not in token_usage_stats["daily_usage"]:
        token_usage_stats["daily_usage"][date_key] = {"input": 0, "output": 0}
    token_usage_stats["daily_usage"][date_key]["input"] += input_tokens
    token_usage_stats["daily_usage"][date_key]["output"] += output_tokens

    return {
        "recorded": True,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total,
        "estimated_cost": round(cost, 6),
    }


def get_token_stats() -> dict:
    """获取 Token 使用统计"""
    return {
        "total_tokens": token_usage_stats["total_tokens"],
        "total_messages": token_usage_stats["total_messages"],
        "by_model": token_usage_stats["by_model"],
        "daily_usage": dict(sorted(token_usage_stats["daily_usage"].items(), reverse=True)[:30]),
        "models_count": len(token_usage_stats["by_model"]),
    }


def reset_token_stats() -> dict:
    """重置 Token 统计"""
    token_usage_stats["total_tokens"] = 0
    token_usage_stats["total_conversations"] = 0
    token_usage_stats["total_messages"] = 0
    token_usage_stats["by_model"] = {}
    token_usage_stats["daily_usage"] = {}
    return {"message": "Token 统计已重置"}


# ---- 上下文管理 ----
def estimate_context_tokens(text: str) -> int:
    """估算文本的 Token 数（粗略估算：4字符≈1 token）"""
    return max(1, len(text) // 4)


def optimize_context(messages: list[dict], max_tokens: int = 8000) -> list[dict]:
    """优化上下文窗口 - 在 token 预算内保留最关键的消息

    策略：保留系统消息 + 最近的 N 条消息，丢弃中间的历史消息
    """
    if not messages:
        return []

    result = []
    total = 0

    # 先添加系统消息
    sys_messages = [m for m in messages if m.get("role") == "system"]
    for m in sys_messages:
        tokens = estimate_context_tokens(m.get("content", ""))
        if total + tokens <= max_tokens:
            result.append(m)
            total += tokens

    # 从后往前添加消息（最近的优先）
    remaining = [m for m in messages if m.get("role") != "system"]
    for m in reversed(remaining):
        tokens = estimate_context_tokens(m.get("content", ""))
        if total + tokens <= max_tokens:
            result.insert(len(sys_messages), m)  # 插入到系统消息之后
            total += tokens

    return result


def suggest_context_window(conversation_length: int) -> dict:
    """根据对话长度建议 context window 配置"""
    if conversation_length < 10:
        return {"suggested_window": 4096, "reason": "短对话，使用 4K 窗口", "economy": "optimal"}
    elif conversation_length < 50:
        return {"suggested_window": 8192, "reason": "中等长度，使用 8K 窗口", "economy": "balanced"}
    elif conversation_length < 200:
        return {"suggested_window": 16384, "reason": "长对话，使用 16K 窗口", "economy": "high_usage"}
    else:
        return {"suggested_window": 32768, "reason": "超长对话，使用 32K 窗口", "economy": "max_usage"}


# ---- 会话生命周期操作 ----
async def archive_conversation(db: AsyncSession, conversation_id: str) -> dict:
    """归档对话"""
    from app.models.conversation import Conversation
    conv = await db.get(Conversation, conversation_id)
    if not conv:
        raise ValueError("对话不存在")
    conv.status = "archived"
    await db.flush()
    return {"message": "对话已归档", "conversation_id": conversation_id}


async def export_conversation(db: AsyncSession, conversation_id: str, format: str = "json") -> dict:
    """导出对话"""
    from app.models.conversation import Conversation, Message

    conv = await db.get(Conversation, conversation_id)
    if not conv:
        raise ValueError("对话不存在")

    result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at)
    )
    messages = result.scalars().all()

    export_data = {
        "conversation": {
            "id": conv.id,
            "title": conv.title,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "message_count": len(messages),
        },
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "tokens": m.tokens,
            }
            for m in messages
        ],
    }

    if format == "markdown":
        md = f"# {conv.title or '对话导出'}\n\n"
        md += f"- 创建时间: {conv.created_at}\n"
        md += f"- 消息数: {len(messages)}\n\n"
        md += "---\n\n"
        for m in messages:
            role_label = "🧑 User" if m.role == "user" else "🤖 Assistant"
            md += f"### {role_label}\n\n{m.content}\n\n"
        return {"format": "markdown", "content": md, "filename": f"conversation_{conversation_id[:8]}.md"}

    return {"format": "json", "content": json.dumps(export_data, ensure_ascii=False, indent=2), "filename": f"conversation_{conversation_id[:8]}.json"}
