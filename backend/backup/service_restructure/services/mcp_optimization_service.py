"""
MCP 使用优化服务 - 连接池/熔断/负载均衡/安全
"""
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


# ---- 熔断器 ----
@dataclass
class CircuitBreakerState:
    """熔断器状态"""
    failures: int = 0
    last_failure_time: float = 0
    state: str = "closed"  # closed / open / half-open
    threshold: int = 5  # 连续失败次数阈值
    recovery_timeout: float = 30  # 恢复超时（秒）


circuit_breakers: dict[str, CircuitBreakerState] = defaultdict(CircuitBreakerState)


def check_circuit_breaker(server_id: str) -> dict:
    """检查熔断器状态"""
    cb = circuit_breakers[server_id]
    now = time.time()

    if cb.state == "open":
        if now - cb.last_failure_time > cb.recovery_timeout:
            cb.state = "half-open"
            return {"allowed": True, "state": "half-open", "message": "熔断器半开，允许探测请求"}
        return {"allowed": False, "state": "open", "message": f"熔断器开启，将在 {int(cb.recovery_timeout - (now - cb.last_failure_time))} 秒后尝试恢复"}

    return {"allowed": True, "state": cb.state, "message": "正常"}


def record_failure(server_id: str) -> dict:
    """记录失败"""
    cb = circuit_breakers[server_id]
    cb.failures += 1
    cb.last_failure_time = time.time()
    if cb.failures >= cb.threshold:
        cb.state = "open"
    return {"failures": cb.failures, "state": cb.state, "threshold": cb.threshold}


def record_success(server_id: str) -> dict:
    """记录成功"""
    cb = circuit_breakers[server_id]
    cb.failures = 0
    if cb.state == "half-open":
        cb.state = "closed"
    return {"state": cb.state}


def reset_circuit_breaker(server_id: str) -> dict:
    """重置熔断器"""
    if server_id in circuit_breakers:
        del circuit_breakers[server_id]
    return {"message": f"熔断器已重置"}


# ---- 连接池统计 ----
connection_pool_stats = {
    "total_connections": 0,
    "active_connections": 0,
    "max_pool_size": 10,
    "created_at": datetime.utcnow().isoformat(),
}


def get_pool_stats() -> dict:
    """获取连接池统计"""
    return connection_pool_stats


def update_pool_stats(active: Optional[int] = None, total: Optional[int] = None) -> None:
    """更新连接池统计"""
    if active is not None:
        connection_pool_stats["active_connections"] = active
    if total is not None:
        connection_pool_stats["total_connections"] = total


# ---- 负载均衡 ----
@dataclass
class LoadBalancerState:
    """负载均衡器状态"""
    servers: list[str] = field(default_factory=list)
    current_index: int = 0
    strategy: str = "round-robin"  # round-robin / least-connections / random


load_balancer = LoadBalancerState()


def set_load_balancer_servers(server_ids: list[str]) -> dict:
    """设置负载均衡服务器列表"""
    load_balancer.servers = server_ids
    load_balancer.current_index = 0
    return {"servers": server_ids, "count": len(server_ids)}


def get_next_server(strategy: Optional[str] = None) -> dict:
    """获取下一个服务器"""
    if not load_balancer.servers:
        return {"error": "无可用服务器"}

    strategy = strategy or load_balancer.strategy

    if strategy == "round-robin":
        idx = load_balancer.current_index % len(load_balancer.servers)
        load_balancer.current_index += 1
        return {"server": load_balancer.servers[idx], "strategy": strategy, "index": idx}

    elif strategy == "random":
        import random
        idx = random.randint(0, len(load_balancer.servers) - 1)
        return {"server": load_balancer.servers[idx], "strategy": strategy, "index": idx}

    return {"error": f"未知策略: {strategy}"}


def get_load_balancer_status() -> dict:
    """获取负载均衡状态"""
    return {
        "servers": load_balancer.servers,
        "current_index": load_balancer.current_index,
        "strategy": load_balancer.strategy,
        "available": len(load_balancer.servers),
    }


# ---- 安全配置 ----
security_config = {
    "tls_enabled": False,
    "api_key_required": True,
    "rate_limit_per_minute": 60,
    "allowed_origins": ["*"],
    "max_request_size_mb": 10,
}


def get_security_config() -> dict:
    """获取安全配置"""
    return security_config


def update_security_config(config: dict) -> dict:
    """更新安全配置"""
    for k, v in config.items():
        if k in security_config:
            security_config[k] = v
    return {"message": "安全配置已更新", "config": security_config}
