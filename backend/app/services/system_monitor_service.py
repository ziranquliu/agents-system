"""
系统监控增强服务 - 系统健康/性能指标
"""
from collections import defaultdict
from datetime import datetime


# 性能指标存储
api_latencies = defaultdict(list)  # endpoint -> [duration_ms]


def record_api_latency(endpoint: str, duration_ms: float) -> None:
    """记录 API 延迟"""
    api_latencies[endpoint].append(duration_ms)
    if len(api_latencies[endpoint]) > 1000:
        api_latencies[endpoint] = api_latencies[endpoint][-1000:]


def get_api_latency_stats() -> dict:
    """获取 API 延迟统计"""
    stats = {}
    for endpoint, times in api_latencies.items():
        if times:
            stats[endpoint] = {
                "avg": round(sum(times) / len(times), 2),
                "min": round(min(times), 2),
                "max": round(max(times), 2),
                "count": len(times),
                "p95": round(sorted(times)[int(len(times) * 0.95)], 2) if len(times) > 20 else round(max(times), 2),
            }
    return stats


async def get_system_health() -> dict:
    """获取系统健康状态"""
    import psutil

    try:
        cpu_percent = psutil.cpu_percent(interval=0.5)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        return {
            "cpu": {
                "usage_percent": cpu_percent,
                "cores": psutil.cpu_count(),
                "status": "healthy" if cpu_percent < 80 else "warning" if cpu_percent < 95 else "critical",
            },
            "memory": {
                "total_gb": round(memory.total / (1024**3), 2),
                "used_gb": round(memory.used / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "usage_percent": memory.percent,
                "status": "healthy" if memory.percent < 80 else "warning" if memory.percent < 95 else "critical",
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "usage_percent": disk.percent,
                "status": "healthy" if disk.percent < 80 else "warning" if disk.percent < 95 else "critical",
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
    except ImportError:
        return {
            "cpu": {"status": "unavailable", "message": "psutil not installed"},
            "memory": {"status": "unavailable", "message": "psutil not installed"},
            "disk": {"status": "unavailable", "message": "psutil not installed"},
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}
