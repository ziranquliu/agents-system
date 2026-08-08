"""
Tests for circuit_breaker.py — CircuitBreaker 3-state machine + ConnectionPool
"""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.circuit_breaker import CircuitBreaker, CircuitState


# ─────────────────────────────────────────────────────────
# CircuitBreaker — 状态转换
# ─────────────────────────────────────────────────────────
class TestCircuitBreaker:
    def test_initial_state(self):
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_failure_opens_circuit(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_success_decrements_failure_count(self):
        cb = CircuitBreaker("test", failure_threshold=5)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb._failure_count == 1

    def test_success_in_half_open_closes(self):
        cb = CircuitBreaker("test", success_threshold=2)
        cb._transition_to(CircuitState.HALF_OPEN)
        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_failure_in_half_open_opens(self):
        cb = CircuitBreaker("test")
        cb._transition_to(CircuitState.HALF_OPEN)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_auto_transition_to_half_open(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0)
        cb.record_failure()
        cb.record_failure()
        # recovery_timeout=0 时, state 属性会自动检查超时并转换
        # 第一次检查时已经是 open 状态且 last_failure_time <= now, 所以直接转 HALF_OPEN
        assert cb.state == CircuitState.HALF_OPEN

    def test_manual_reset(self):
        cb = CircuitBreaker("test", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0

    def test_half_open_max_calls(self):
        cb = CircuitBreaker("test", half_open_max_calls=1)
        cb._transition_to(CircuitState.HALF_OPEN)
        assert cb.allow_request() is True
        assert cb.allow_request() is False

    def test_stats(self):
        cb = CircuitBreaker("test", failure_threshold=5)
        cb.record_failure()
        stats = cb.get_stats()
        assert stats["name"] == "test"
        assert stats["state"] == "closed"
        assert stats["failure_count"] == 1

    def test_stats_tracks_rejections(self):
        cb = CircuitBreaker("test", failure_threshold=1)
        cb.record_failure()
        cb.allow_request()
        cb.allow_request()
        stats = cb.get_stats()
        assert stats["total_rejected"] == 2

    def test_failure_count_resets_on_closing(self):
        cb = CircuitBreaker("test", success_threshold=1)
        cb.record_failure()
        cb._transition_to(CircuitState.HALF_OPEN)
        cb.record_success()
        assert cb._failure_count == 0
        assert cb._success_count == 0


# ─────────────────────────────────────────────────────────
# ConnectionPool — 单元测试 (mock httpx)
# ─────────────────────────────────────────────────────────
class TestConnectionPool:
    @pytest.mark.asyncio
    async def test_get_client_creates(self):
        from app.services.circuit_breaker import ConnectionPool
        pool = ConnectionPool()
        with patch("app.services.circuit_breaker.httpx.AsyncClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.is_closed = False
            mock_instance.aclose = AsyncMock()
            MockClient.return_value = mock_instance
            client = await pool.get_client("http://localhost:8080")
            assert client is mock_instance
            assert pool._total_created == 1
            await pool.close()
        await pool.close()

    @pytest.mark.asyncio
    async def test_reuse_client(self):
        from app.services.circuit_breaker import ConnectionPool
        pool = ConnectionPool()
        with patch("app.services.circuit_breaker.httpx.AsyncClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.is_closed = False
            mock_instance.aclose = AsyncMock()
            MockClient.return_value = mock_instance
            c1 = await pool.get_client("http://localhost:8080")
            c2 = await pool.get_client("http://localhost:8080")
            assert c1 is c2
            assert pool._total_reused == 1
            assert pool._total_created == 1
            await pool.close()
        await pool.close()

    @pytest.mark.asyncio
    async def test_different_hosts(self):
        from app.services.circuit_breaker import ConnectionPool
        pool = ConnectionPool()
        with patch("app.services.circuit_breaker.httpx.AsyncClient") as MockClient:
            mock1 = MagicMock()
            mock1.is_closed = False
            mock1.aclose = AsyncMock()
            mock2 = MagicMock()
            mock2.is_closed = False
            mock2.aclose = AsyncMock()
            MockClient.side_effect = [mock1, mock2]
            c1 = await pool.get_client("http://host1:8080")
            c2 = await pool.get_client("http://host2:8080")
            assert c1 is not c2
            assert pool._total_created == 2
            await pool.close()
        await pool.close()

    @pytest.mark.asyncio
    async def test_close_all(self):
        from app.services.circuit_breaker import ConnectionPool
        pool = ConnectionPool()
        with patch("app.services.circuit_breaker.httpx.AsyncClient") as MockClient:
            mock1 = MagicMock()
            mock1.is_closed = False
            mock1.aclose = AsyncMock()
            mock2 = MagicMock()
            mock2.is_closed = False
            mock2.aclose = AsyncMock()
            MockClient.side_effect = [mock1, mock2]
            await pool.get_client("http://host1:8080")
            await pool.get_client("http://host2:8080")
            await pool.close()
            assert len(pool._clients) == 0

    def test_normalize_key(self):
        from app.services.circuit_breaker import ConnectionPool
        pool = ConnectionPool()
        k1 = pool._normalize_key("http://host:8080/")
        k2 = pool._normalize_key("http://host:8080")
        assert k1 == k2

    def test_stats(self):
        from app.services.circuit_breaker import ConnectionPool
        pool = ConnectionPool()
        stats = pool.get_stats()
        assert stats["total_created"] == 0
        assert stats["total_reused"] == 0
