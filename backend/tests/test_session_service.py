"""
SessionService 测试 — 6态生命周期、状态转换、上下文管理
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from app.services.session_service import (
    SessionManager,
    SESSION_STATES,
    STATE_TRANSITIONS,
    _safe_json,
)


# ============================================================
# 工具函数测试
# ============================================================

class TestSafeJson:
    def test_valid_json(self):
        assert _safe_json('{"a": 1}') == {"a": 1}

    def test_non_string_passthrough(self):
        obj = {"key": "val"}
        assert _safe_json(obj) == obj

    def test_none_returns_default(self):
        assert _safe_json(None) == {}

    def test_none_returns_custom_default(self):
        assert _safe_json(None, default=[]) == []

    def test_empty_string_returns_default(self):
        assert _safe_json("") == {}

    def test_invalid_json_returns_default(self):
        assert _safe_json("not json") == {}

    def test_invalid_json_returns_custom_default(self):
        assert _safe_json("{bad", default="fallback") == "fallback"

    def test_json_array(self):
        assert _safe_json("[1,2,3]") == [1, 2, 3]


# ============================================================
# 常量测试
# ============================================================

class TestSessionConstants:
    def test_session_states_count(self):
        assert len(SESSION_STATES) == 6

    def test_session_states_values(self):
        expected = {"active", "idle", "timeout", "archived", "cleaned", "error"}
        assert set(SESSION_STATES) == expected

    def test_state_transitions_cover_all_states(self):
        for state in SESSION_STATES:
            assert state in STATE_TRANSITIONS

    def test_cleaned_is_terminal(self):
        assert STATE_TRANSITIONS["cleaned"] == []

    def test_active_can_go_to_idle(self):
        assert "idle" in STATE_TRANSITIONS["active"]

    def test_active_can_go_to_error(self):
        assert "error" in STATE_TRANSITIONS["active"]

    def test_archived_can_only_go_to_cleaned(self):
        assert STATE_TRANSITIONS["archived"] == ["cleaned"]

    def test_error_can_recover(self):
        assert "active" in STATE_TRANSITIONS["error"]

    def test_invalid_transition_not_allowed(self):
        # archived cannot go to active
        assert "active" not in STATE_TRANSITIONS["archived"]

    def test_idle_can_go_to_active(self):
        assert "active" in STATE_TRANSITIONS["idle"]

    def test_timeout_can_go_to_active(self):
        assert "active" in STATE_TRANSITIONS["timeout"]


# ============================================================
# SessionManager 单元测试 (mock db)
# ============================================================

class TestSessionManagerCreate:
    """测试 SessionManager 的创建逻辑"""

    def _make_manager(self):
        mock_db = AsyncMock()
        return SessionManager(mock_db)

    def test_default_config(self):
        mgr = self._make_manager()
        assert mgr.DEFAULT_IDLE_TIMEOUT_MINUTES == 30
        assert mgr.DEFAULT_TIMEOUT_MINUTES == 120
        assert mgr.DEFAULT_AUTO_ARCHIVE_DAYS == 7
        assert mgr.DEFAULT_MAX_MESSAGES_IN_CONTEXT == 50
        assert mgr.DEFAULT_CONTEXT_WINDOW_TOKENS == 4096

    def test_session_states_in_manager(self):
        """确认 SessionManager 可以访问 SESSION_STATES"""
        assert len(SESSION_STATES) == 6

    @pytest.mark.asyncio
    async def test_transition_invalid_state(self):
        mgr = self._make_manager()
        with pytest.raises(ValueError, match="无效状态"):
            await mgr.transition_state("s1", "nonexistent")

    @pytest.mark.asyncio
    async def test_transition_nonexistent_session(self):
        mgr = self._make_manager()
        # mock _get_session 返回 None
        mgr._get_session = AsyncMock(return_value=None)
        with pytest.raises(ValueError, match="会话不存在"):
            await mgr.transition_state("s1", "idle")

    @pytest.mark.asyncio
    async def test_transition_invalid_direction(self):
        """cleaned → idle 不允许"""
        mgr = self._make_manager()
        mock_session = MagicMock()
        mock_session.status = "cleaned"
        mgr._get_session = AsyncMock(return_value=mock_session)

        with pytest.raises(ValueError, match="不允许从"):
            await mgr.transition_state("s1", "idle")

    @pytest.mark.asyncio
    async def test_transition_valid(self):
        """active → idle 合法"""
        mgr = self._make_manager()
        mock_session = MagicMock()
        mock_session.status = "active"
        mgr._get_session = AsyncMock(return_value=mock_session)

        result = await mgr.transition_state("s1", "idle", reason="超时")
        assert result.status == "idle"

    @pytest.mark.asyncio
    async def test_context_sliding_window_default(self):
        """build_context 默认使用 sliding_window"""
        mgr = self._make_manager()
        # 创建模拟消息列表
        mock_msgs = []
        for i in range(5):
            msg = MagicMock()
            msg.role = "user" if i % 2 == 0 else "assistant"
            msg.content = f"Message {i}"
            msg.tool_calls = None
            msg.created_at = datetime.now(timezone.utc)
            mock_msgs.append(msg)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_msgs
        mgr.db.execute = AsyncMock(return_value=mock_result)

        # mock session
        mock_session = MagicMock()
        mgr._get_session = AsyncMock(return_value=mock_session)

        context = await mgr.build_context("s1", "Hello", strategy="sliding_window")
        assert isinstance(context, list)
        # sliding_window 应该保留最近 max_messages 条
        assert len(context) <= mgr.DEFAULT_MAX_MESSAGES_IN_CONTEXT


# ============================================================
# _safe_json 深度测试
# ============================================================

class TestSafeJsonDeep:
    def test_nested_json(self):
        data = '{"a": {"b": [1,2,3]}}'
        result = _safe_json(data)
        assert result["a"]["b"] == [1, 2, 3]

    def test_json_string_value(self):
        result = _safe_json('"hello"')
        assert result == "hello"

    def test_json_number(self):
        result = _safe_json("42")
        assert result == 42

    def test_json_boolean(self):
        result = _safe_json("true")
        assert result is True
