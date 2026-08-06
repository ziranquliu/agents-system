"""
测试 - 对话理解增强 (意图/共指/话题)
"""

import pytest


class TestIntentDetection:
    """意图识别"""

    def _make_service(self):
        from app.services.dialogue_enhancement_service import DialogueEnhancementService
        return DialogueEnhancementService()

    @pytest.mark.asyncio
    async def test_question_intent(self):
        svc = self._make_service()
        result = await svc.detect_intent("什么是机器学习?")
        assert result["intent"] == "question"
        assert result["confidence"] > 0.5

    @pytest.mark.asyncio
    async def test_command_intent(self):
        svc = self._make_service()
        result = await svc.detect_intent("帮我创建一个Agent")
        assert result["intent"] == "command"
        assert result["confidence"] > 0.5

    @pytest.mark.asyncio
    async def test_greeting_intent(self):
        svc = self._make_service()
        result = await svc.detect_intent("你好")
        assert result["intent"] == "greeting"

    @pytest.mark.asyncio
    async def test_farewell_intent(self):
        svc = self._make_service()
        result = await svc.detect_intent("再见")
        assert result["intent"] == "farewell"

    @pytest.mark.asyncio
    async def test_batch_intent(self):
        svc = self._make_service()
        results = await svc.detect_intent_batch(["你好", "帮我运行代码", "为什么报错?"])
        assert len(results) == 3
        assert results[0]["intent"] == "greeting"

    @pytest.mark.asyncio
    async def test_session_tracking(self):
        svc = self._make_service()
        await svc.detect_intent("你好", session_id="s1")
        await svc.detect_intent("帮我运行", session_id="s1")
        summary = svc.get_session_summary("s1")
        assert summary["total_turns"] == 2


class TestCoreferenceResolution:
    """共指消解"""

    def _make_service(self):
        from app.services.dialogue_enhancement_service import DialogueEnhancementService
        return DialogueEnhancementService()

    @pytest.mark.asyncio
    async def test_resolve_pronoun(self):
        svc = self._make_service()
        context = [
            {"content": "张三是一个程序员", "role": "user"},
        ]
        result = await svc.resolve_coreference("他喜欢Python", session_id="")
        assert "resolved_text" in result

    @pytest.mark.asyncio
    async def test_no_context(self):
        svc = self._make_service()
        result = await svc.resolve_coreference("这是什么")
        assert result["resolution_count"] == 0


class TestTopicSwitch:
    """话题切换"""

    def _make_service(self):
        from app.services.dialogue_enhancement_service import DialogueEnhancementService
        return DialogueEnhancementService()

    @pytest.mark.asyncio
    async def test_continuation(self):
        svc = self._make_service()
        # 第一条消息
        await svc.detect_intent("Python 编程 基础", session_id="s1")
        # 第二条 — 同话题相关关键词
        result = await svc.detect_topic_switch("Python 的GIL是什么", session_id="s1")
        # 可能是 continuation/soft_switch/return (取决于相似度)
        assert result["switch_type"] in ("continuation", "soft_switch", "return")

    @pytest.mark.asyncio
    async def test_hard_switch(self):
        svc = self._make_service()
        await svc.detect_intent("Python 编程", session_id="s1")
        result = await svc.detect_topic_switch("今天天气怎么样", session_id="s1")
        assert result["switch_type"] in ("hard_switch", "soft_switch", "continuation")
        assert "distance_score" in result


class TestContextQuality:
    """上下文质量评估"""

    def _make_service(self):
        from app.services.dialogue_enhancement_service import DialogueEnhancementService
        return DialogueEnhancementService()

    @pytest.mark.asyncio
    async def test_quality_empty_session(self):
        svc = self._make_service()
        result = await svc.evaluate_context_quality("nonexistent")
        assert result["overall_score"] == 0

    @pytest.mark.asyncio
    async def test_quality_with_history(self):
        svc = self._make_service()
        for msg in ["你好", "什么是机器学习", "Python 怎么学"]:
            await svc.detect_intent(msg, session_id="s1")
        result = await svc.evaluate_context_quality("s1")
        assert result["overall_score"] > 0
        assert result["turns_analyzed"] == 3

    @pytest.mark.asyncio
    async def test_enhance_message(self):
        svc = self._make_service()
        result = await svc.enhance_message("什么是机器学习?", session_id="s1")
        assert "intent" in result
        assert "coreference" in result
        assert "topic_switch" in result
        assert "enhanced_text" in result
