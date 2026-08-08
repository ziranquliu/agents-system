"""
LogAggregationService 测试 — Elasticsearch/Loki 双后端日志推送
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.services.log_aggregation_service import (
    LogAggregationService,
    ElasticsearchClient,
    LokiClient,
)


# ============================================================
# ElasticsearchClient 测试
# ============================================================

class TestElasticsearchClient:
    def test_init(self):
        client = ElasticsearchClient("http://localhost:9200", "test-logs")
        assert client.base_url == "http://localhost:9200"
        assert client.index_prefix == "test-logs"

    def test_init_trailing_slash(self):
        client = ElasticsearchClient("http://localhost:9200/")
        assert client.base_url == "http://localhost:9200"

    def test_index_name_format(self):
        client = ElasticsearchClient("http://localhost:9200", "agent-logs")
        ts = datetime(2026, 1, 15, tzinfo=timezone.utc)
        name = client._index_name(ts)
        assert name == "agent-logs-2026.01.15"

    def test_index_name_now(self):
        client = ElasticsearchClient("http://localhost:9200", "logs")
        name = client._index_name()
        assert name.startswith("logs-")

    def test_buffer_initial(self):
        client = ElasticsearchClient("http://localhost:9200")
        assert len(client._buffer) == 0
        assert client._buffer_size == 100


# ============================================================
# LokiClient 测试
# ============================================================

class TestLokiClient:
    def test_init(self):
        client = LokiClient("http://localhost:3100")
        assert client.base_url == "http://localhost:3100"


# ============================================================
# LogAggregationService 初始化测试
# ============================================================

class TestLogAggregationInit:
    def test_init_no_backends(self):
        service = LogAggregationService()
        assert service._es is None
        assert service._loki is None

    def test_init_es_only(self):
        service = LogAggregationService(es_url="http://localhost:9200")
        assert service._es is not None
        assert service._loki is None

    def test_init_loki_only(self):
        service = LogAggregationService(loki_url="http://localhost:3100")
        assert service._es is None
        assert service._loki is not None

    def test_init_both(self):
        service = LogAggregationService(
            es_url="http://localhost:9200",
            loki_url="http://localhost:3100",
        )
        assert service._es is not None
        assert service._loki is not None

    def test_from_config_with_env(self):
        with patch.dict("os.environ", {
            "ELASTICSEARCH_URL": "http://es:9200",
            "LOKI_URL": "http://loki:3100",
        }):
            service = LogAggregationService.from_config()
            assert service._es is not None
            assert service._loki is not None

    def test_from_config_no_env(self):
        with patch.dict("os.environ", {}, clear=True):
            service = LogAggregationService.from_config()
            assert service._es is None
            assert service._loki is None


# ============================================================
# push_log_entry 测试
# ============================================================

class TestPushLogEntry:
    @pytest.mark.asyncio
    async def test_push_no_backends(self):
        service = LogAggregationService()
        result = await service.push_log_entry(level="info", message="test")
        assert result == {}

    @pytest.mark.asyncio
    async def test_push_es_success(self):
        service = LogAggregationService(es_url="http://localhost:9200")
        with patch.object(service._es, "index_log", new_callable=AsyncMock, return_value=True):
            result = await service.push_log_entry(level="info", message="test msg")
            assert result["elasticsearch"] is True

    @pytest.mark.asyncio
    async def test_push_es_failure(self):
        service = LogAggregationService(es_url="http://localhost:9200")
        with patch.object(service._es, "index_log", new_callable=AsyncMock, return_value=False):
            result = await service.push_log_entry(level="info", message="test msg")
            assert result["elasticsearch"] is False

    @pytest.mark.asyncio
    async def test_push_loki_success(self):
        service = LogAggregationService(loki_url="http://localhost:3100")
        with patch.object(service._loki, "push_log", new_callable=AsyncMock, return_value=True):
            result = await service.push_log_entry(level="info", message="test msg")
            assert result["loki"] is True

    @pytest.mark.asyncio
    async def test_push_both_success(self):
        service = LogAggregationService(
            es_url="http://localhost:9200",
            loki_url="http://localhost:3100",
        )
        with patch.object(service._es, "index_log", new_callable=AsyncMock, return_value=True), \
             patch.object(service._loki, "push_log", new_callable=AsyncMock, return_value=True):
            result = await service.push_log_entry(level="info", message="test msg")
            assert result["elasticsearch"] is True
            assert result["loki"] is True

    @pytest.mark.asyncio
    async def test_push_with_agent_id(self):
        service = LogAggregationService(es_url="http://localhost:9200")
        with patch.object(service._es, "index_log", new_callable=AsyncMock, return_value=True) as mock_push:
            await service.push_log_entry(level="error", message="err", agent_id="a1")
            call_args = mock_push.call_args
            assert call_args[0][0]["agent_id"] == "a1"

    @pytest.mark.asyncio
    async def test_push_with_extra(self):
        service = LogAggregationService(es_url="http://localhost:9200")
        with patch.object(service._es, "index_log", new_callable=AsyncMock, return_value=True) as mock_push:
            await service.push_log_entry(level="info", message="test", extra={"custom": "data"})
            call_args = mock_push.call_args
            assert call_args[0][0]["custom"] == "data"

    @pytest.mark.asyncio
    async def test_push_es_exception_propagates(self):
        service = LogAggregationService(es_url="http://localhost:9200")
        with patch.object(service._es, "index_log", new_callable=AsyncMock, side_effect=Exception("network error")):
            with pytest.raises(Exception, match="network error"):
                await service.push_log_entry(level="info", message="test")


# ============================================================
# push_batch 测试
# ============================================================

class TestPushLogBatch:
    @pytest.mark.asyncio
    async def test_batch_no_backends(self):
        service = LogAggregationService()
        entries = [{"level": "info", "message": f"msg{i}"} for i in range(5)]
        result = await service.push_batch(entries)
        assert result == {}

    @pytest.mark.asyncio
    async def test_batch_es_success(self):
        service = LogAggregationService(es_url="http://localhost:9200")
        entries = [{"level": "info", "message": f"msg{i}"} for i in range(3)]
        with patch.object(service._es, "bulk_index", new_callable=AsyncMock, return_value={"success": True, "indexed": 3}):
            result = await service.push_batch(entries)
            assert result["elasticsearch"]["indexed"] == 3

    @pytest.mark.asyncio
    async def test_batch_empty(self):
        service = LogAggregationService(es_url="http://localhost:9200")
        result = await service.push_batch([])
        assert "elasticsearch" in result or result == {}


# ============================================================
# 无操作测试
# ============================================================

class TestNoOp:
    @pytest.mark.asyncio
    async def test_no_op(self):
        """占位测试以确保模块可导入"""
        service = LogAggregationService()
        assert service is not None
