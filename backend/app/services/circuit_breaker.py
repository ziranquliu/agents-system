"""
熔断器 + 连接池 - MCP/SKILL调用保护
实现 3 态熔断器 (CLOSED/OPEN/HALF-OPEN) + HTTP 连接池管理
"""
import asyncio
import time
import logging
from enum import Enum
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"       # 正常(允许调用)
    OPEN = "open"           # 熔断(拒绝调用)
    HALF_OPEN = "half_open" # 半开(允许一次探测调用)


class CircuitBreaker:
    """
    3 态熔断器
    
    CLOSED  → 失败计数 ≥ failure_threshold → OPEN
    OPEN    → 超时 recovery_timeout → HALF_OPEN
    HALF_OPEN → 成功 → CLOSED / 失败 → OPEN
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        half_open_max_calls: int = 1,
        success_threshold: int = 2,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time = 0.0
        self._total_calls = 0
        self._total_failures = 0
        self._total_rejected = 0

    @property
    def state(self) -> CircuitState:
        """获取当前状态(含自动转换)"""
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)
        return self._state

    def _transition_to(self, new_state: CircuitState):
        old = self._state
        self._state = new_state
        if new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._success_count = 0
        elif new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
        logger.info("熔断器 [%s] 状态转换: %s -> %s", self.name, old.value, new_state.value)

    def allow_request(self) -> bool:
        """是否允许请求通过"""
        self._total_calls += 1
        current_state = self.state  # 触发自动转换检查

        if current_state == CircuitState.CLOSED:
            return True
        elif current_state == CircuitState.HALF_OPEN:
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True
            self._total_rejected += 1
            return False
        else:  # OPEN
            self._total_rejected += 1
            return False

    def record_success(self):
        """记录成功调用"""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._transition_to(CircuitState.CLOSED)
        elif self._state == CircuitState.CLOSED:
            self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self):
        """记录失败调用"""
        self._failure_count += 1
        self._total_failures += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                self._transition_to(CircuitState.OPEN)

    def reset(self):
        """手动重置"""
        self._transition_to(CircuitState.CLOSED)

    def get_stats(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "total_calls": self._total_calls,
            "total_failures": self._total_failures,
            "total_rejected": self._total_rejected,
            "last_failure_time": self._last_failure_time,
        }


class ConnectionPool:
    """
    HTTP 连接池管理
    
    - 每个 host:port 独立池
    - 最大连接数限制
    - 空闲超时回收
    - 健康检查
    """

    def __init__(
        self,
        max_connections_per_host: int = 10,
        max_total_connections: int = 50,
        idle_timeout: int = 300,
        health_check_interval: int = 60,
    ):
        self.max_connections_per_host = max_connections_per_host
        self.max_total_connections = max_total_connections
        self.idle_timeout = idle_timeout
        self.health_check_interval = health_check_interval

        self._clients: dict[str, httpx.AsyncClient] = {}
        self._usage_count: dict[str, int] = {}
        self._last_used: dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._total_created = 0
        self._total_reused = 0

    async def get_client(self, base_url: str) -> httpx.AsyncClient:
        """获取或创建连接"""
        key = self._normalize_key(base_url)

        async with self._lock:
            if key in self._clients:
                client = self._clients[key]
                if not client.is_closed:
                    self._usage_count[key] = self._usage_count.get(key, 0) + 1
                    self._last_used[key] = time.time()
                    self._total_reused += 1
                    return client

            # 检查总数限制
            if len(self._clients) >= self.max_total_connections:
                await self._evict_idle()

            # 创建新连接
            client = httpx.AsyncClient(
                base_url=base_url,
                timeout=httpx.Timeout(30.0),
                limits=httpx.Limits(
                    max_connections=self.max_connections_per_host,
                    max_keepalive_connections=self.max_connections_per_host // 2,
                ),
            )
            self._clients[key] = client
            self._usage_count[key] = 1
            self._last_used[key] = time.time()
            self._total_created += 1

            return client

    async def release(self, base_url: str):
        """释放连接(标记为可复用)"""
        key = self._normalize_key(base_url)
        self._last_used[key] = time.time()

    async def close(self, base_url: Optional[str] = None):
        """关闭连接"""
        async with self._lock:
            if base_url:
                key = self._normalize_key(base_url)
                if key in self._clients:
                    await self._clients[key].aclose()
                    del self._clients[key]
                    self._usage_count.pop(key, None)
                    self._last_used.pop(key, None)
            else:
                for key, client in list(self._clients.items()):
                    await client.aclose()
                self._clients.clear()
                self._usage_count.clear()
                self._last_used.clear()

    async def _evict_idle(self):
        """回收空闲连接"""
        now = time.time()
        to_remove = []
        for key, last_t in self._last_used.items():
            if now - last_t > self.idle_timeout:
                to_remove.append(key)

        for key in to_remove:
            if key in self._clients:
                await self._clients[key].aclose()
                del self._clients[key]
                self._usage_count.pop(key, None)
                self._last_used.pop(key, None)

        # 如果还是超限,移除最不常用的
        if len(self._clients) >= self.max_total_connections and self._clients:
            least_used_key = min(self._usage_count, key=self._usage_count.get)
            if least_used_key in self._clients:
                await self._clients[least_used_key].aclose()
                del self._clients[least_used_key]
                self._usage_count.pop(least_used_key, None)
                self._last_used.pop(least_used_key, None)

    @staticmethod
    def _normalize_key(base_url: str) -> str:
        return base_url.rstrip("/").lower()

    def get_stats(self) -> dict:
        return {
            "active_connections": len(self._clients),
            "max_connections_per_host": self.max_connections_per_host,
            "max_total_connections": self.max_total_connections,
            "total_created": self._total_created,
            "total_reused": self._total_reused,
            "usage_by_host": {
                k: {"usage_count": v, "last_used": self._last_used.get(k, 0)}
                for k, v in self._usage_count.items()
            },
        }


# ==================================================================
# 全局实例
# ==================================================================

class MCPProtectionManager:
    """
    MCP 调用保护管理器
    整合熔断器 + 连接池 + 降级策略
    """

    # 降级级别
    DEGRADE_LEVELS = {
        0: "full",         # 完全功能
        1: "cached",       # 使用缓存
        2: "simplified",   # 简化响应
        3: "unavailable",  # 不可用
    }

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._pool = ConnectionPool()
        self._degrade_level: int = 0
        self._fallback_responses: dict[str, str] = {}

    def get_breaker(
        self, name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
    ) -> CircuitBreaker:
        """获取或创建熔断器"""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
            )
        return self._breakers[name]

    async def call_with_protection(
        self,
        name: str,
        url: str,
        method: str = "POST",
        json_data: Optional[dict] = None,
        timeout: float = 30.0,
        fallback: Optional[str] = None,
    ) -> dict:
        """
        带保护的 HTTP 调用:
        1. 检查熔断器
        2. 从连接池获取连接
        3. 执行调用
        4. 更新熔断器状态
        """
        breaker = self.get_breaker(name)

        # 熔断检查
        if not breaker.allow_request():
            logger.warning("MCP调用 [%s] 被熔断器拒绝", name)
            return {
                "success": False,
                "error": "服务暂时不可用(熔断中)",
                "circuit_state": breaker.state.value,
                "fallback": fallback,
                "degraded": True,
            }

        # 连接池获取
        client = await self._pool.get_client(url)

        try:
            if method.upper() == "POST":
                response = await client.post(
                    url, json=json_data or {}, timeout=timeout
                )
            elif method.upper() == "GET":
                response = await client.get(url, timeout=timeout)
            elif method.upper() == "PUT":
                response = await client.put(
                    url, json=json_data or {}, timeout=timeout
                )
            elif method.upper() == "DELETE":
                response = await client.delete(url, timeout=timeout)
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")

            response.raise_for_status()
            breaker.record_success()
            await self._pool.release(url)

            return {
                "success": True,
                "status_code": response.status_code,
                "data": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
            }

        except httpx.TimeoutException:
            breaker.record_failure()
            return {
                "success": False,
                "error": "请求超时",
                "circuit_state": breaker.state.value,
                "fallback": fallback,
            }
        except httpx.HTTPStatusError as e:
            breaker.record_failure()
            return {
                "success": False,
                "error": f"HTTP错误: {e.response.status_code}",
                "circuit_state": breaker.state.value,
                "fallback": fallback,
            }
        except Exception as e:
            breaker.record_failure()
            logger.error("MCP调用 [%s] 异常: %s", name, str(e))
            return {
                "success": False,
                "error": "调用异常",
                "circuit_state": breaker.state.value,
                "fallback": fallback,
            }

    def set_degrade_level(self, level: int):
        """设置降级级别"""
        if level in self.DEGRADE_LEVELS:
            self._degrade_level = level
            logger.info("降级级别设置为: %d (%s)", level, self.DEGRADE_LEVELS[level])

    def get_degrade_level(self) -> int:
        return self._degrade_level

    def get_all_stats(self) -> dict:
        return {
            "degrade_level": self._degrade_level,
            "degrade_mode": self.DEGRADE_LEVELS.get(self._degrade_level, "unknown"),
            "circuit_breakers": {
                name: breaker.get_stats()
                for name, breaker in self._breakers.items()
            },
            "connection_pool": self._pool.get_stats(),
        }

    async def shutdown(self):
        """关闭所有连接"""
        await self._pool.close()


# 全局保护管理器
mcp_protection = MCPProtectionManager()
