"""
日志聚合服务 — Elasticsearch / Loki 集中日志推送与搜索

功能:
1. Elasticsearch: 批量推送日志、按字段搜索、索引管理
2. Loki: push API 推送、LogQL 查询
3. 统一搜索: 跨 ES + Loki 聚合搜索结果
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class ElasticsearchClient:
    """Elasticsearch 推送与搜索客户端"""

    def __init__(self, base_url: str, index_prefix: str = "agent-logs"):
        self.base_url = base_url.rstrip("/")
        self.index_prefix = index_prefix
        self._buffer: List[dict] = []
        self._buffer_size = 100
        self._flush_interval = 5  # 秒

    def _index_name(self, timestamp: Optional[datetime] = None) -> str:
        """按日期分索引: agent-logs-2024.01.01"""
        ts = timestamp or datetime.now(timezone.utc)
        return f"{self.index_prefix}-{ts.strftime('%Y.%m.%d')}"

    async def index_log(self, log_entry: dict) -> bool:
        """单条索引"""
        url = f"{self.base_url}/{self._index_name()}/_doc"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json=log_entry)
                return resp.status_code in (200, 201)
        except Exception as e:
            logger.warning("ES 单条索引失败: %s", str(e))
            return False

    async def bulk_index(self, entries: List[dict]) -> dict:
        """批量索引（_bulk API）"""
        if not entries:
            return {"success": True, "indexed": 0}

        index_name = self._index_name()
        lines = []
        for entry in entries:
            action = {"index": {"_index": index_name}}
            lines.append(json.dumps(action))
            lines.append(json.dumps(entry, default=str))
        body = "\n".join(lines) + "\n"

        url = f"{self.base_url}/_bulk"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    url,
                    content=body,
                    headers={"Content-Type": "application/x-ndjson"},
                )
                result = resp.json()
                errors = result.get("errors", False)
                return {
                    "success": not errors,
                    "indexed": len(entries),
                    "errors": result.get("items", []) if errors else [],
                }
        except Exception as e:
            logger.warning("ES 批量索引失败: %s", str(e))
            return {"success": False, "indexed": 0, "error": str(e)}

    async def search(
        self,
        query: str = "",
        level: Optional[str] = None,
        agent_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        size: int = 100,
    ) -> dict:
        """ES 搜索"""
        must = []
        if query:
            must.append({"match": {"message": query}})
        if level:
            must.append({"term": {"level": level}})
        if agent_id:
            must.append({"term": {"agent_id": agent_id}})
        if start_time or end_time:
            range_q = {}
            if start_time:
                range_q["gte"] = start_time
            if end_time:
                range_q["lte"] = end_time
            must.append({"range": {"@timestamp": range_q}})

        body = {
            "query": {"bool": {"must": must}} if must else {"match_all": {}},
            "sort": [{"@timestamp": {"order": "desc"}}],
            "size": size,
        }

        url = f"{self.base_url}/{self.index_prefix}-*/_search"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json=body)
                result = resp.json()
                hits = result.get("hits", {}).get("hits", [])
                total = result.get("hits", {}).get("total", {}).get("value", 0)
                return {
                    "success": True,
                    "total": total,
                    "items": [h.get("_source", {}) for h in hits],
                }
        except Exception as e:
            logger.warning("ES 搜索失败: %s", str(e))
            return {"success": False, "total": 0, "items": [], "error": str(e)}

    async def health_check(self) -> dict:
        """ES 集群健康检查"""
        url = f"{self.base_url}/_cluster/health"
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(url)
                return {"success": True, **resp.json()}
        except Exception as e:
            return {"success": False, "error": str(e)}


class LokiClient:
    """Loki push API 客户端"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def push_logs(
        self,
        streams: List[Dict[str, Any]],
    ) -> bool:
        """
        推送日志到 Loki。

        streams 格式:
        [
            {
                "stream": {"app": "agent-system", "level": "error"},
                "values": [["1234567890000000000", "log message"]]
            }
        ]
        """
        url = f"{self.base_url}/loki/api/v1/push"
        body = {"streams": streams}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    url,
                    json=body,
                    headers={"Content-Type": "application/json"},
                )
                return resp.status_code in (200, 204)
        except Exception as e:
            logger.warning("Loki 推送失败: %s", str(e))
            return False

    async def push_log(
        self,
        labels: Dict[str, str],
        message: str,
        timestamp_ns: Optional[int] = None,
    ) -> bool:
        """推送单条日志"""
        ts = timestamp_ns or str(int(time.time() * 1e9))
        stream = {"stream": labels, "values": [[ts, message]]}
        return await self.push_logs([stream])

    async def push_batch(
        self,
        label_key: str,
        label_value: str,
        entries: List[Dict[str, Any]],
    ) -> bool:
        """
        批量推送: 同一标签的日志批量发送。

        entries: [{"timestamp_ns": "...", "message": "...", "extra_labels": {...}}]
        """
        values = []
        for entry in entries:
            ts = entry.get("timestamp_ns", str(int(time.time() * 1e9)))
            values.append([ts, entry.get("message", "")])

        stream = {
            "stream": {label_key: label_value},
            "values": values,
        }
        return await self.push_logs([stream])

    async def query(self, logql: str, limit: int = 100) -> dict:
        """LogQL 查询"""
        url = f"{self.base_url}/loki/api/v1/query_range"
        params = {"query": logql, "limit": limit}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, params=params)
                result = resp.json()
                return {"success": True, "data": result.get("data", {})}
        except Exception as e:
            logger.warning("Loki 查询失败: %s", str(e))
            return {"success": False, "data": {}, "error": str(e)}

    async def health_check(self) -> dict:
        """Loki 健康检查"""
        url = f"{self.base_url}/ready"
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(url)
                return {"success": resp.status_code == 200, "status": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}


class LogAggregationService:
    """统一日志聚合管理器"""

    def __init__(
        self,
        es_url: Optional[str] = None,
        loki_url: Optional[str] = None,
        es_index_prefix: str = "agent-logs",
    ):
        self._es: Optional[ElasticsearchClient] = None
        self._loki: Optional[LokiClient] = None
        self._es_url = es_url
        self._loki_url = loki_url

        if es_url:
            self._es = ElasticsearchClient(es_url, es_index_prefix)
        if loki_url:
            self._loki = LokiClient(loki_url)

    @classmethod
    def from_config(cls) -> "LogAggregationService":
        """从环境变量构建"""
        import os
        es_url = os.getenv("ELASTICSEARCH_URL")
        loki_url = os.getenv("LOKI_URL")
        es_prefix = os.getenv("ES_INDEX_PREFIX", "agent-logs")
        return cls(es_url=es_url, loki_url=loki_url, es_index_prefix=es_prefix)

    async def push_log_entry(
        self,
        level: str,
        message: str,
        agent_id: Optional[str] = None,
        logger_name: str = "app",
        extra: Optional[dict] = None,
    ) -> dict:
        """推送单条日志到所有启用的后端"""
        now = datetime.now(timezone.utc)
        ts_ns = str(int(now.timestamp() * 1e9))

        # 统一日志格式
        log_entry = {
            "@timestamp": now.isoformat(),
            "level": level.lower(),
            "logger": logger_name,
            "message": message,
            "agent_id": agent_id,
        }
        if extra:
            log_entry.update(extra)

        results = {}

        # ES
        if self._es:
            results["elasticsearch"] = await self._es.index_log(log_entry)

        # Loki
        if self._loki:
            labels = {"app": "agent-system", "level": level.lower()}
            if agent_id:
                labels["agent_id"] = agent_id
            results["loki"] = await self._loki.push_log(
                labels=labels, message=message, timestamp_ns=ts_ns
            )

        return results

    async def push_batch(
        self,
        entries: List[dict],
    ) -> dict:
        """批量推送日志"""
        results = {}

        if self._es:
            results["elasticsearch"] = await self._es.bulk_index(entries)

        if self._loki:
            # Loki: 按 agent_id 分组
            groups: Dict[str, list] = {}
            now_ns = str(int(time.time() * 1e9))
            for entry in entries:
                agent_id = entry.get("agent_id", "system")
                groups.setdefault(agent_id, []).append({
                    "timestamp_ns": now_ns,
                    "message": json.dumps(entry, default=str),
                })

            loki_ok = True
            for agent_id, batch in groups.items():
                ok = await self._loki.push_batch("agent_id", agent_id, batch)
                if not ok:
                    loki_ok = False
            results["loki"] = loki_ok

        return results

    async def search(
        self,
        query: str = "",
        level: Optional[str] = None,
        agent_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        backend: str = "elasticsearch",
        size: int = 100,
    ) -> dict:
        """搜索日志"""
        if backend == "elasticsearch" and self._es:
            return await self._es.search(query, level, agent_id, start_time, end_time, size)
        elif backend == "loki" and self._loki:
            logql = self._build_logql(query, level, agent_id)
            return await self._loki.query(logql, size)
        else:
            return {"success": False, "error": f"后端 {backend} 未配置"}

    @staticmethod
    def _build_logql(
        query: str = "",
        level: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> str:
        """构建 LogQL 查询"""
        selectors = ['app="agent-system"']
        if level:
            selectors.append(f'level="{level.lower()}"')
        if agent_id:
            selectors.append(f'agent_id="{agent_id}"')
        selector_str = "{" + ", ".join(selectors) + "}"
        if query:
            return f'{selector_str} |~ "{query}"'
        return selector_str

    async def health_check(self) -> dict:
        """检查所有后端健康状态"""
        results = {}
        if self._es:
            results["elasticsearch"] = await self._es.health_check()
        else:
            results["elasticsearch"] = {"status": "not_configured"}

        if self._loki:
            results["loki"] = await self._loki.health_check()
        else:
            results["loki"] = {"status": "not_configured"}

        return results


# 全局实例（惰性初始化）
_log_agg_service: Optional[LogAggregationService] = None


def get_log_aggregation_service() -> LogAggregationService:
    global _log_agg_service
    if _log_agg_service is None:
        _log_agg_service = LogAggregationService.from_config()
    return _log_agg_service
