"""
对话质量评分与用户满意度分析

功能:
- 对话质量多维评分（响应质量/响应速度/解决率/用户满意度）
- 用户满意度分析（CSAT评分）
- 对话质量趋势分析
- Agent 质量排名
- 质量告警（低分对话自动标记）
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class QualityDimension(str, Enum):
    RESPONSE_RELEVANCE = "response_relevance"     # 回答相关性
    RESPONSE_COMPLETENESS = "response_completeness"  # 回答完整度
    RESPONSE_SPEED = "response_speed"            # 响应速度
    RESOLUTION_RATE = "resolution_rate"          # 解决率
    USER_SATISFACTION = "user_satisfaction"      # 用户满意度
    CONTEXT_AWARENESS = "context_awareness"      # 上下文理解


@dataclass
class QualityScore:
    """对话质量评分"""
    conversation_id: str = ""
    session_id: str = ""
    agent_id: str = ""
    # 各维度分数 (0-100)
    response_relevance: float = 0.0
    response_completeness: float = 0.0
    response_speed: float = 0.0
    resolution_rate: float = 0.0
    user_satisfaction: float = 0.0
    context_awareness: float = 0.0
    # 综合评分
    overall_score: float = 0.0
    # 元信息
    message_count: int = 0
    total_duration_ms: float = 0.0
    avg_response_time_ms: float = 0.0
    resolved: bool = False
    # 用户反馈
    csat_score: Optional[int] = None  # 1-5
    csat_comment: str = ""
    scored_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "agent_id": self.agent_id,
            "dimensions": {
                "response_relevance": round(self.response_relevance, 1),
                "response_completeness": round(self.response_completeness, 1),
                "response_speed": round(self.response_speed, 1),
                "resolution_rate": round(self.resolution_rate, 1),
                "user_satisfaction": round(self.user_satisfaction, 1),
                "context_awareness": round(self.context_awareness, 1),
            },
            "overall_score": round(self.overall_score, 1),
            "message_count": self.message_count,
            "total_duration_ms": round(self.total_duration_ms, 1),
            "avg_response_time_ms": round(self.avg_response_time_ms, 1),
            "resolved": self.resolved,
            "csat_score": self.csat_score,
            "csat_comment": self.csat_comment,
            "scored_at": self.scored_at.isoformat() if self.scored_at else None,
        }


@dataclass
class QualityWeights:
    """质量维度权重"""
    response_relevance: float = 0.25
    response_completeness: float = 0.20
    response_speed: float = 0.15
    resolution_rate: float = 0.20
    user_satisfaction: float = 0.15
    context_awareness: float = 0.05


class ConversationQualityService:
    """
    对话质量评分服务

    评分公式:
    overall = Σ(dimension_score × weight)

    CSAT 分析:
    - 5分: 非常满意
    - 4分: 满意
    - 3分: 一般
    - 2分: 不满意
    - 1分: 非常不满意
    """

    # 默认权重
    DEFAULT_WEIGHTS = QualityWeights()

    # 响应时间评分区间（ms）
    SPEED_THRESHOLDS = [
        (1000, 100),     # <1s → 100分
        (3000, 80),      # <3s → 80分
        (5000, 60),      # <5s → 60分
        (10000, 40),     # <10s → 40分
        (30000, 20),     # <30s → 20分
        (float("inf"), 0),
    ]

    # 质量告警阈值
    QUALITY_ALERT_THRESHOLD = 40.0

    def __init__(self):
        self._scores: dict[str, QualityScore] = {}
        self._agent_scores: dict[str, list[float]] = {}  # agent_id → scores
        self._weights = self.DEFAULT_WEIGHTS
        self._alerts: list[dict[str, Any]] = []

    # ----------------------------------------------------------
    # 评分
    # ----------------------------------------------------------

    def score_conversation(
        self,
        conversation_id: str,
        agent_id: str,
        messages: list[dict[str, Any]],
        response_times_ms: Optional[list[float]] = None,
        resolved: bool = False,
        session_id: str = "",
    ) -> QualityScore:
        """
        对对话进行质量评分

        messages 格式:
        [{"role": "user/assistant", "content": "...", "timestamp": "..."}]
        """
        score = QualityScore(
            conversation_id=conversation_id,
            session_id=session_id,
            agent_id=agent_id,
            message_count=len(messages),
            resolved=resolved,
            scored_at=datetime.now(timezone.utc),
        )

        if not messages:
            score.overall_score = 0
            return score

        # 计算响应速度
        if response_times_ms:
            score.avg_response_time_ms = sum(response_times_ms) / len(response_times_ms)
        elif len(messages) > 1:
            # 估算：用户消息和助手消息交替
            times = []
            for i in range(1, len(messages)):
                if messages[i].get("role") == "assistant" and messages[i - 1].get("role") == "user":
                    # 估算响应时间（基于消息长度）
                    content_len = len(messages[i].get("content", ""))
                    times.append(content_len * 5)  # 粗略估算
            if times:
                score.avg_response_time_ms = sum(times) / len(times)

        score.response_speed = self._score_speed(score.avg_response_time_ms)

        # 基于消息内容评估（启发式）
        assistant_messages = [m for m in messages if m.get("role") == "assistant"]
        user_messages = [m for m in messages if m.get("role") == "user"]

        # 相关性评估（基于关键词匹配）
        score.response_relevance = self._score_relevance(user_messages, assistant_messages)

        # 完整度评估（基于回答长度和结构）
        score.response_completeness = self._score_completeness(assistant_messages)

        # 解决率
        score.resolution_rate = 100.0 if resolved else (80.0 if len(assistant_messages) > 0 else 0.0)

        # 上下文理解（基于对话轮次的连贯性）
        score.context_awareness = self._score_context_awareness(messages)

        # 用户满意度（基于 CSAT 或推断）
        score.user_satisfaction = self._infer_satisfaction(messages)

        # 综合评分
        w = self._weights
        score.overall_score = (
            score.response_relevance * w.response_relevance +
            score.response_completeness * w.response_completeness +
            score.response_speed * w.response_speed +
            score.resolution_rate * w.resolution_rate +
            score.user_satisfaction * w.user_satisfaction +
            score.context_awareness * w.context_awareness
        )

        # 存储
        self._scores[conversation_id] = score
        if agent_id not in self._agent_scores:
            self._agent_scores[agent_id] = []
        self._agent_scores[agent_id].append(score.overall_score)

        # 质量告警
        if score.overall_score < self.QUALITY_ALERT_THRESHOLD:
            self._alerts.append({
                "conversation_id": conversation_id,
                "agent_id": agent_id,
                "score": score.overall_score,
                "timestamp": score.scored_at.isoformat() if score.scored_at else None,
            })

        return score

    def set_csat(self, conversation_id: str, score: int, comment: str = "") -> bool:
        """设置用户满意度评分"""
        quality = self._scores.get(conversation_id)
        if not quality:
            return False
        quality.csat_score = max(1, min(5, score))
        quality.csat_comment = comment
        # 更新用户满意度维度
        quality.user_satisfaction = quality.csat_score * 20  # 1-5 → 0-100
        # 重算综合评分
        w = self._weights
        quality.overall_score = (
            quality.response_relevance * w.response_relevance +
            quality.response_completeness * w.response_completeness +
            quality.response_speed * w.response_speed +
            quality.resolution_rate * w.resolution_rate +
            quality.user_satisfaction * w.user_satisfaction +
            quality.context_awareness * w.context_awareness
        )
        return True

    # ----------------------------------------------------------
    # 评分算法（启发式）
    # ----------------------------------------------------------

    def _score_speed(self, avg_ms: float) -> float:
        """响应速度评分"""
        for threshold, score in self.SPEED_THRESHOLDS:
            if avg_ms < threshold:
                return score
        return 0

    def _score_relevance(
        self,
        user_msgs: list[dict],
        assistant_msgs: list[dict],
    ) -> float:
        """相关性评分"""
        if not user_msgs or not assistant_msgs:
            return 50.0

        # 简单启发式：关键词重叠
        total_score = 0.0
        for user_msg in user_msgs:
            user_words = set(user_msg.get("content", "").lower().split())
            best_match = 0.0
            for asst_msg in assistant_msgs:
                asst_words = set(asst_msg.get("content", "").lower().split())
                if user_words and asst_words:
                    overlap = len(user_words & asst_words) / len(user_words)
                    best_match = max(best_match, overlap)
            total_score += min(best_match * 100, 100)

        return total_score / len(user_msgs) if user_msgs else 50.0

    def _score_completeness(self, assistant_msgs: list[dict]) -> float:
        """完整度评分"""
        if not assistant_msgs:
            return 0.0

        lengths = [len(m.get("content", "")) for m in assistant_msgs]
        avg_len = sum(lengths) / len(lengths)

        # 理想长度 200-800 字符
        if avg_len < 50:
            return 30.0
        elif avg_len < 100:
            return 50.0
        elif avg_len < 200:
            return 70.0
        elif avg_len <= 800:
            return 90.0
        else:
            return 80.0  # 过长扣分

    def _score_context_awareness(self, messages: list[dict]) -> float:
        """上下文理解评分"""
        if len(messages) < 2:
            return 50.0

        # 检查代词使用（指代消解）
        pronouns = {"它", "这个", "那个", "这里", "那里", "上面", "下面", "他", "她"}
        context_score = 70.0  # 基准分

        for i in range(1, len(messages)):
            content = messages[i].get("content", "")
            if messages[i].get("role") == "assistant":
                # 检查是否回应了用户的具体内容
                if i > 0 and messages[i - 1].get("role") == "user":
                    prev_content = messages[i - 1].get("content", "")
                    # 长回答通常意味着更多上下文理解
                    if len(content) > len(prev_content) * 0.5:
                        context_score += 5

        return min(context_score, 100.0)

    def _infer_satisfaction(self, messages: list[dict]) -> float:
        """推断用户满意度"""
        if not messages:
            return 50.0

        # 检查用户正面/负面反馈
        positive_words = {"谢谢", "感谢", "很好", "太棒了", "完美", "不错", "好的", "解决了"}
        negative_words = {"不行", "错误", "不对", "没用", "失望", "差", "差评", "差劲"}

        pos_count = 0
        neg_count = 0
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "").lower()
                for w in positive_words:
                    if w in content:
                        pos_count += 1
                for w in negative_words:
                    if w in content:
                        neg_count += 1

        if pos_count > neg_count:
            return 80.0
        elif neg_count > pos_count:
            return 30.0
        else:
            return 60.0

    # ----------------------------------------------------------
    # 查询与分析
    # ----------------------------------------------------------

    def get_score(self, conversation_id: str) -> Optional[dict[str, Any]]:
        score = self._scores.get(conversation_id)
        return score.to_dict() if score else None

    def get_agent_ranking(self, limit: int = 20) -> list[dict[str, Any]]:
        """Agent 质量排名"""
        rankings = []
        for agent_id, scores in self._agent_scores.items():
            if scores:
                rankings.append({
                    "agent_id": agent_id,
                    "avg_score": round(sum(scores) / len(scores), 1),
                    "total_conversations": len(scores),
                    "min_score": round(min(scores), 1),
                    "max_score": round(max(scores), 1),
                })
        rankings.sort(key=lambda x: x["avg_score"], reverse=True)
        return rankings[:limit]

    def get_quality_trend(
        self,
        agent_id: Optional[str] = None,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """质量趋势分析"""
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        trend = []

        for i in range(days):
            day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            day_scores = []
            for score in self._scores.values():
                if score.scored_at and score.scored_at.strftime("%Y-%m-%d") == day:
                    if agent_id and score.agent_id != agent_id:
                        continue
                    day_scores.append(score.overall_score)

            if day_scores:
                trend.append({
                    "date": day,
                    "avg_score": round(sum(day_scores) / len(day_scores), 1),
                    "count": len(day_scores),
                })
            else:
                trend.append({"date": day, "avg_score": None, "count": 0})

        return list(reversed(trend))

    def get_alerts(self, limit: int = 50) -> list[dict[str, Any]]:
        """获取质量告警"""
        return self._alerts[-limit:]

    def get_overall_stats(self) -> dict[str, Any]:
        """获取整体质量统计"""
        if not self._scores:
            return {"total_conversations": 0, "avg_score": 0}

        scores = [s.overall_score for s in self._scores.values()]
        csat_scores = [s.csat_score for s in self._scores.values() if s.csat_score]

        return {
            "total_conversations": len(self._scores),
            "avg_score": round(sum(scores) / len(scores), 1),
            "min_score": round(min(scores), 1),
            "max_score": round(max(scores), 1),
            "total_csat_ratings": len(csat_scores),
            "avg_csat": round(sum(csat_scores) / len(csat_scores), 1) if csat_scores else None,
            "resolved_count": sum(1 for s in self._scores.values() if s.resolved),
            "resolution_rate": round(
                sum(1 for s in self._scores.values() if s.resolved) / len(self._scores) * 100, 1
            ),
            "alert_count": len(self._alerts),
        }
