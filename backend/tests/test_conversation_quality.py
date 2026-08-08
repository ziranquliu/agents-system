"""
ConversationQualityService 测试 — 质量评分、CSAT分析、Agent排名、告警
"""
import pytest
from datetime import datetime, timezone

from app.services.conversation_quality_service import (
    ConversationQualityService,
    QualityScore,
    QualityWeights,
    QualityDimension,
)


# ============================================================
# 枚举 / 数据类测试
# ============================================================

class TestQualityDimension:
    def test_all_dimensions(self):
        values = {d.value for d in QualityDimension}
        assert "response_relevance" in values
        assert "response_completeness" in values
        assert "response_speed" in values
        assert "resolution_rate" in values
        assert "user_satisfaction" in values
        assert "context_awareness" in values
        assert len(values) == 6


class TestQualityScore:
    def test_default_values(self):
        score = QualityScore()
        assert score.conversation_id == ""
        assert score.overall_score == 0.0
        assert score.resolved is False
        assert score.csat_score is None

    def test_to_dict(self):
        score = QualityScore(
            conversation_id="conv1",
            agent_id="a1",
            response_relevance=85.0,
            response_completeness=90.0,
            overall_score=87.5,
            message_count=10,
            resolved=True,
            csat_score=5,
        )
        d = score.to_dict()
        assert d["conversation_id"] == "conv1"
        assert d["dimensions"]["response_relevance"] == 85.0
        assert d["overall_score"] == 87.5
        assert d["resolved"] is True

    def test_to_dict_none_scored_at(self):
        score = QualityScore()
        d = score.to_dict()
        assert d["scored_at"] is None


class TestQualityWeights:
    def test_default_weights_sum(self):
        w = QualityWeights()
        total = (w.response_relevance + w.response_completeness +
                 w.response_speed + w.resolution_rate +
                 w.user_satisfaction + w.context_awareness)
        assert abs(total - 1.0) < 0.01


# ============================================================
# ConversationQualityService 评分测试
# ============================================================

class TestQualityServiceScore:
    def setup_method(self):
        self.service = ConversationQualityService()

    def test_score_empty_messages(self):
        score = self.service.score_conversation("c1", "a1", [])
        assert score.overall_score == 0
        assert score.message_count == 0

    def test_score_basic_conversation(self):
        messages = [
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "Python is a programming language."},
            {"role": "user", "content": "How do I install it?"},
            {"role": "assistant", "content": "You can install Python from python.org."},
        ]
        score = self.service.score_conversation("c1", "a1", messages)
        assert score.overall_score > 0
        assert score.message_count == 4
        assert score.response_speed > 0

    def test_score_resolved_conversation(self):
        messages = [
            {"role": "user", "content": "Help"},
            {"role": "assistant", "content": "I can help you."},
        ]
        score = self.service.score_conversation("c1", "a1", messages, resolved=True)
        assert score.resolution_rate == 100.0

    def test_score_unresolved_conversation(self):
        messages = [
            {"role": "user", "content": "Help"},
            {"role": "assistant", "content": "I can help you."},
        ]
        score = self.service.score_conversation("c1", "a1", messages, resolved=False)
        assert score.resolution_rate == 80.0

    def test_score_with_explicit_response_times(self):
        messages = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"},
            {"role": "assistant", "content": "A2"},
        ]
        score = self.service.score_conversation(
            "c1", "a1", messages, response_times_ms=[500, 2000]
        )
        assert score.avg_response_time_ms == 1250.0

    def test_score_stored(self):
        messages = [{"role": "user", "content": "Q"}, {"role": "assistant", "content": "A"}]
        score = self.service.score_conversation("c1", "a1", messages)
        assert "c1" in self.service._scores

    def test_score_agent_accumulated(self):
        messages = [{"role": "user", "content": "Q"}, {"role": "assistant", "content": "A"}]
        self.service.score_conversation("c1", "a1", messages)
        self.service.score_conversation("c2", "a1", messages)
        assert "a1" in self.service._agent_scores
        assert len(self.service._agent_scores["a1"]) == 2

    def test_score_dimension_bounds(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there! How can I help you today?"},
        ]
        score = self.service.score_conversation("c1", "a1", messages)
        assert 0 <= score.response_relevance <= 100
        assert 0 <= score.response_completeness <= 100
        assert 0 <= score.response_speed <= 100
        assert 0 <= score.resolution_rate <= 100
        assert 0 <= score.user_satisfaction <= 100
        assert 0 <= score.context_awareness <= 100
        assert 0 <= score.overall_score <= 100


# ============================================================
# 排名 / 告警测试
# ============================================================

class TestQualityServiceRanking:
    def setup_method(self):
        self.service = ConversationQualityService()
        msgs_a = [{"role": "user", "content": "Q"}, {"role": "assistant", "content": "Great detailed answer"}]
        msgs_b = [{"role": "user", "content": "Q"}, {"role": "assistant", "content": "OK"}]
        self.service.score_conversation("c1", "a1", msgs_a, resolved=True)
        self.service.score_conversation("c2", "a2", msgs_b, resolved=False)

    def test_get_agent_rankings(self):
        rankings = self.service.get_agent_ranking()
        assert len(rankings) == 2
        assert rankings[0]["agent_id"] in ("a1", "a2")

    def test_get_stats(self):
        stats = self.service.get_overall_stats()
        assert stats["total_conversations"] == 2
        assert "avg_score" in stats


# ============================================================
# 边界情况
# ============================================================

class TestQualityEdgeCases:
    def setup_method(self):
        self.service = ConversationQualityService()

    def test_single_message(self):
        score = self.service.score_conversation("c1", "a1", [{"role": "user", "content": "Hi"}])
        assert score.overall_score >= 0

    def test_long_conversation(self):
        messages = []
        for i in range(100):
            messages.append({"role": "user", "content": f"Question {i}"})
            messages.append({"role": "assistant", "content": f"Answer {i}"})
        score = self.service.score_conversation("c1", "a1", messages)
        assert score.message_count == 200
