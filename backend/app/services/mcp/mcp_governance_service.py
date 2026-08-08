"""
MCP 服务治理 — 负载均衡 / 限流 / 灰度发布

功能:
- 负载均衡（轮询/加权/最少连接）
- 限流（令牌桶/滑动窗口）
- 灰度发布（金丝雀发布/蓝绿部署）
- 熔断降级（已有 circuit_breaker.py，此处集成）
- 调用链审计
"""

import asyncio
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LoadBalanceStrategy(str, Enum):
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    LEAST_CONNECTIONS = "least_connections"
    RANDOM = "random"


class RateLimitAlgorithm(str, Enum):
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"


class DeploymentStrategy(str, Enum):
    CANARY = "canary"           # 金丝雀发布
    BLUE_GREEN = "blue_green"   # 蓝绿部署
    ROLLING = "rolling"         # 滚动更新


@dataclass
class ServerInstance:
    """MCP Server 实例"""
    id: str = ""
    host: str = ""
    port: int = 8080
    weight: int = 1
    active_connections: int = 0
    total_requests: int = 0
    total_errors: int = 0
    avg_response_ms: float = 0
    healthy: bool = True
    version: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class RateLimitConfig:
    """限流配置"""
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.TOKEN_BUCKET
    max_requests: int = 100        # 窗口内最大请求数
    window_seconds: int = 60       # 窗口大小（秒）
    burst_size: int = 20           # 令牌桶突发容量
    refill_rate: float = 10.0      # 令牌填充速率（个/秒）


@dataclass
class CanaryConfig:
    """灰度发布配置"""
    strategy: DeploymentStrategy = DeploymentStrategy.CANARY
    canary_weight: int = 10        # 金丝雀权重 (%)
    stable_weight: int = 90        # 稳定版权重 (%)
    rollout_increment: int = 10    # 每次递增 (%)
    rollout_interval_seconds: int = 300  # 递增间隔
    success_threshold: float = 0.99  # 成功率阈值
    rollback_on_failure: bool = True
    current_percentage: int = 0    # 当前金丝雀百分比
    status: str = "pending"        # pending/in_progress/completed/rolled_back


@dataclass
class AuditEntry:
    """调用审计条目"""
    id: str = ""
    server_id: str = ""
    tool_name: str = ""
    caller_agent_id: str = ""
    request_id: str = ""
    status: str = "success"
    response_ms: float = 0
    timestamp: Optional[datetime] = None
    error_message: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())


class MCPGovernanceService:
    """
    MCP 服务治理

    - 负载均衡：轮询/加权/最少连接
    - 限流：令牌桶/滑动窗口
    - 灰度发布：金丝雀/蓝绿/滚动
    - 调用链审计
    """

    def __init__(self):
        self._instances: dict[str, ServerInstance] = {}
        self._round_robin_index = 0
        self._rate_limit_config: Optional[RateLimitConfig] = None
        self._rate_limit_buckets: dict[str, float] = {}  # server_id → tokens
        self._rate_limit_windows: dict[str, deque] = {}  # server_id → timestamps
        self._canary_configs: dict[str, CanaryConfig] = {}
        self._audit_log: list[AuditEntry] = []
        self._lock = asyncio.Lock()

    # ----------------------------------------------------------
    # 实例管理
    # ----------------------------------------------------------

    def register_instance(self, instance: ServerInstance) -> str:
        """注册 MCP Server 实例"""
        if not instance.id:
            instance.id = str(uuid.uuid4())
        self._instances[instance.id] = instance
        logger.info(f"MCP instance registered: {instance.id} ({instance.host}:{instance.port})")
        return instance.id

    def deregister_instance(self, instance_id: str) -> bool:
        """注销实例"""
        if instance_id in self._instances:
            del self._instances[instance_id]
            return True
        return False

    def get_instance(self, instance_id: str) -> Optional[ServerInstance]:
        return self._instances.get(instance_id)

    def list_instances(self, healthy_only: bool = True) -> list[dict[str, Any]]:
        instances = list(self._instances.values())
        if healthy_only:
            instances = [i for i in instances if i.healthy]
        return [
            {
                "id": i.id, "host": i.host, "port": i.port,
                "weight": i.weight, "active_connections": i.active_connections,
                "total_requests": i.total_requests, "healthy": i.healthy,
                "version": i.version,
            }
            for i in instances
        ]

    # ----------------------------------------------------------
    # 负载均衡
    # ----------------------------------------------------------

    def select_instance(
        self,
        strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN,
        exclude_ids: Optional[list[str]] = None,
    ) -> Optional[ServerInstance]:
        """选择实例"""
        candidates = [
            i for i in self._instances.values()
            if i.healthy and (not exclude_ids or i.id not in exclude_ids)
        ]
        if not candidates:
            return None

        if strategy == LoadBalanceStrategy.ROUND_ROBIN:
            self._round_robin_index = (self._round_robin_index + 1) % len(candidates)
            return candidates[self._round_robin_index]

        elif strategy == LoadBalanceStrategy.WEIGHTED:
            total_weight = sum(i.weight for i in candidates)
            if total_weight == 0:
                return candidates[0]
            import random
            r = random.uniform(0, total_weight)
            cumulative = 0
            for inst in candidates:
                cumulative += inst.weight
                if r <= cumulative:
                    return inst
            return candidates[-1]

        elif strategy == LoadBalanceStrategy.LEAST_CONNECTIONS:
            return min(candidates, key=lambda i: i.active_connections)

        elif strategy == LoadBalanceStrategy.RANDOM:
            import random
            return random.choice(candidates)

        return candidates[0]

    # ----------------------------------------------------------
    # 限流
    # ----------------------------------------------------------

    def configure_rate_limit(self, config: RateLimitConfig):
        """配置限流"""
        self._rate_limit_config = config
        logger.info(f"Rate limit configured: {config.algorithm.value}, max={config.max_requests}/{config.window_seconds}s")

    async def check_rate_limit(self, server_id: str) -> bool:
        """检查是否允许请求"""
        if not self._rate_limit_config:
            return True

        config = self._rate_limit_config

        if config.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
            return await self._check_token_bucket(server_id, config)
        elif config.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
            return await self._check_sliding_window(server_id, config)
        return True

    async def _check_token_bucket(self, server_id: str, config: RateLimitConfig) -> bool:
        """令牌桶限流"""
        async with self._lock:
            now = time.time()
            current = self._rate_limit_buckets.get(server_id, float(config.burst_size))

            # 填充令牌
            elapsed = now - getattr(self, f"_last_refill_{server_id}", now)
            refill = elapsed * config.refill_rate
            current = min(float(config.burst_size), current + refill)
            setattr(self, f"_last_refill_{server_id}", now)

            if current >= 1:
                self._rate_limit_buckets[server_id] = current - 1
                return True
            else:
                self._rate_limit_buckets[server_id] = current
                return False

    async def _check_sliding_window(self, server_id: str, config: RateLimitConfig) -> bool:
        """滑动窗口限流"""
        async with self._lock:
            now = time.time()
            window_start = now - config.window_seconds

            if server_id not in self._rate_limit_windows:
                self._rate_limit_windows[server_id] = deque()

            window = self._rate_limit_windows[server_id]

            # 清除过期记录
            while window and window[0] < window_start:
                window.popleft()

            if len(window) < config.max_requests:
                window.append(now)
                return True
            return False

    def get_rate_limit_status(self, server_id: str) -> dict[str, Any]:
        """获取限流状态"""
        config = self._rate_limit_config
        if not config:
            return {"configured": False}

        if config.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
            tokens = self._rate_limit_buckets.get(server_id, float(config.burst_size))
            return {
                "configured": True,
                "algorithm": "token_bucket",
                "available_tokens": round(tokens, 1),
                "burst_size": config.burst_size,
                "refill_rate": config.refill_rate,
            }
        else:
            window = self._rate_limit_windows.get(server_id, deque())
            return {
                "configured": True,
                "algorithm": "sliding_window",
                "current_requests": len(window),
                "max_requests": config.max_requests,
                "window_seconds": config.window_seconds,
            }

    # ----------------------------------------------------------
    # 灰度发布
    # ----------------------------------------------------------

    def configure_canary(
        self,
        server_id: str,
        canary_version: str,
        stable_version: str,
        initial_percentage: int = 10,
    ) -> CanaryConfig:
        """配置金丝雀发布"""
        config = CanaryConfig(
            current_percentage=initial_percentage,
            canary_weight=initial_percentage,
            stable_weight=100 - initial_percentage,
        )
        self._canary_configs[server_id] = config
        logger.info(f"Canary configured for {server_id}: {initial_percentage}% → {canary_version}")
        return config

    async def advance_canary(self, server_id: str) -> Optional[CanaryConfig]:
        """推进灰度发布（增加百分比）"""
        config = self._canary_configs.get(server_id)
        if not config or config.status not in ("pending", "in_progress"):
            return None

        config.status = "in_progress"
        new_pct = min(config.current_percentage + config.rollout_increment, 100)
        config.current_percentage = new_pct
        config.canary_weight = new_pct
        config.stable_weight = 100 - new_pct

        if new_pct >= 100:
            config.status = "completed"
            logger.info(f"Canary deployment completed for {server_id}")

        return config

    async def rollback_canary(self, server_id: str) -> Optional[CanaryConfig]:
        """回滚灰度发布"""
        config = self._canary_configs.get(server_id)
        if not config:
            return None

        config.status = "rolled_back"
        config.current_percentage = 0
        config.canary_weight = 0
        config.stable_weight = 100
        logger.info(f"Canary rolled back for {server_id}")
        return config

    def get_canary_status(self, server_id: str) -> Optional[dict[str, Any]]:
        config = self._canary_configs.get(server_id)
        if not config:
            return None
        return {
            "strategy": config.strategy.value,
            "current_percentage": config.current_percentage,
            "canary_weight": config.canary_weight,
            "stable_weight": config.stable_weight,
            "status": config.status,
            "success_threshold": config.success_threshold,
        }

    # ----------------------------------------------------------
    # 调用审计
    # ----------------------------------------------------------

    def record_call(
        self,
        server_id: str,
        tool_name: str,
        caller_agent_id: str = "",
        request_id: str = "",
        status: str = "success",
        response_ms: float = 0,
        error_message: str = "",
    ):
        """记录调用"""
        entry = AuditEntry(
            server_id=server_id,
            tool_name=tool_name,
            caller_agent_id=caller_agent_id,
            request_id=request_id,
            status=status,
            response_ms=response_ms,
            timestamp=datetime.now(timezone.utc),
            error_message=error_message,
        )
        self._audit_log.append(entry)

        # 更新实例统计
        instance = self._instances.get(server_id)
        if instance:
            instance.total_requests += 1
            if status == "error":
                instance.total_errors += 1
            # 平均响应时间更新
            n = instance.total_requests
            instance.avg_response_ms = (
                instance.avg_response_ms * (n - 1) + response_ms
            ) / n

    def get_audit_log(
        self,
        server_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        logs = self._audit_log
        if server_id:
            logs = [l for l in logs if l.server_id == server_id]
        if tool_name:
            logs = [l for l in logs if l.tool_name == tool_name]
        return [
            {
                "id": l.id, "server_id": l.server_id, "tool_name": l.tool_name,
                "caller_agent_id": l.caller_agent_id, "status": l.status,
                "response_ms": round(l.response_ms, 1),
                "timestamp": l.timestamp.isoformat() if l.timestamp else None,
                "error_message": l.error_message,
            }
            for l in logs[-limit:]
        ]

    def get_call_stats(self, server_id: Optional[str] = None) -> dict[str, Any]:
        """调用统计"""
        logs = self._audit_log
        if server_id:
            logs = [l for l in logs if l.server_id == server_id]

        total = len(logs)
        errors = sum(1 for l in logs if l.status == "error")
        avg_ms = sum(l.response_ms for l in logs) / total if total > 0 else 0

        tool_counts = {}
        for l in logs:
            tool_counts[l.tool_name] = tool_counts.get(l.tool_name, 0) + 1

        return {
            "total_calls": total,
            "error_count": errors,
            "success_rate": round((total - errors) / total * 100, 1) if total > 0 else 100,
            "avg_response_ms": round(avg_ms, 1),
            "tool_breakdown": tool_counts,
        }
