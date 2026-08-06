"""
Prometheus 指标收集器 — 标准 /metrics 端点

指标分类:
- Agent 指标: 请求数、成功率、延迟
- Token 指标: 使用量、成本
- 系统指标: 活跃连接、内存使用
"""
import time
import threading
from collections import defaultdict
from typing import Dict, Optional


class PrometheusMetrics:
    """
    轻量级 Prometheus 指标收集器。
    
    支持类型:
    - Counter: 单调递增计数器（请求数、错误数、Token 总量）
    - Gauge: 可增可减的量表（活跃连接、队列长度）
    - Histogram: 直方图（延迟分布、响应时间）
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauge: Dict[str, float] = defaultdict(float)
        self._histograms: Dict[str, Dict] = defaultdict(lambda: {
            "buckets": [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            "counts": defaultdict(float),
            "sum": 0.0,
            "count": 0,
        })
        self._start_time = time.time()

    # Counter
    def inc_counter(self, name: str, value: float = 1.0, **labels):
        key = self._label_key(name, labels)
        with self._lock:
            self._counters[key] += value

    def get_counter(self, name: str, **labels) -> float:
        key = self._label_key(name, labels)
        return self._counters.get(key, 0.0)

    # Gauge
    def set_gauge(self, name: str, value: float, **labels):
        key = self._label_key(name, labels)
        with self._lock:
            self._gauge[key] = value

    def inc_gauge(self, name: str, value: float = 1.0, **labels):
        key = self._label_key(name, labels)
        with self._lock:
            self._gauge[key] += value

    def dec_gauge(self, name: str, value: float = 1.0, **labels):
        key = self._label_key(name, labels)
        with self._lock:
            self._gauge[key] -= value

    # Histogram
    def observe_histogram(self, name: str, value: float, **labels):
        key = self._label_key(name, labels)
        with self._lock:
            h = self._histograms[key]
            h["sum"] += value
            h["count"] += 1
            for bucket in h["buckets"]:
                if value <= bucket:
                    h["counts"][bucket] += 1
            h["counts"]["+Inf"] += 1

    # 输出 Prometheus 文本格式
    def render(self) -> str:
        """生成 Prometheus exposition format 文本"""
        lines = []

        # Counters
        for key, value in sorted(self._counters.items()):
            name, labels_str = self._split_key(key)
            lines.append(f"# HELP {name} Counter")
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name}{labels_str} {value}")

        # Gauges
        for key, value in sorted(self._gauge.items()):
            name, labels_str = self._split_key(key)
            lines.append(f"# HELP {name} Gauge")
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name}{labels_str} {value}")

        # Histograms
        for key, h in sorted(self._histograms.items()):
            name, labels_str = self._split_key(key)
            lines.append(f"# HELP {name} Histogram")
            lines.append(f"# TYPE {name} histogram")
            for bucket in h["buckets"]:
                count = h["counts"].get(bucket, 0)
                label_suffix = f'_bucket{{le="{bucket}"}}'
                base_labels = labels_str.lstrip("{").rstrip("}")
                if base_labels:
                    lines.append(f"{name}_bucket{{{base_labels},le=\"{bucket}\"}} {count}")
                else:
                    lines.append(f"{name}_bucket{{le=\"{bucket}\"}} {count}")
            lines.append(f"{name}_sum{labels_str} {h['sum']}")
            lines.append(f"{name}_count{labels_str} {h['count']}")

        # 进程指标
        uptime = time.time() - self._start_time
        lines.append(f"# HELP process_uptime_seconds Process uptime")
        lines.append(f"# TYPE process_uptime_seconds gauge")
        lines.append(f"process_uptime_seconds {uptime:.1f}")

        return "\n".join(lines) + "\n"

    @staticmethod
    def _label_key(name: str, labels: dict) -> str:
        if not labels:
            return name
        parts = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f'{name}{{{parts}}}'

    @staticmethod
    def _split_key(key: str) -> tuple:
        if "{" in key:
            idx = key.index("{")
            return key[:idx], key[idx:]
        return key, ""


# 全局指标实例
metrics = PrometheusMetrics()


def record_request(agent_id: str, model: str, endpoint: str, status: str, latency: float):
    """记录一次 API 请求的 Prometheus 指标"""
    metrics.inc_counter("agent_requests_total", agent_id=agent_id, model=model, endpoint=endpoint, status=status)
    metrics.observe_histogram("agent_request_duration_seconds", latency, agent_id=agent_id, endpoint=endpoint)


def record_tokens(model: str, input_tokens: int, output_tokens: int, cost: float):
    """记录 Token 使用量"""
    metrics.inc_counter("token_input_total", model=model, value=float(input_tokens))
    metrics.inc_counter("token_output_total", model=model, value=float(output_tokens))
    metrics.inc_counter("token_cost_usd_total", model=model, value=cost)


def record_active_connections(count: int):
    """更新活跃连接数"""
    metrics.set_gauge("active_websocket_connections", float(count))


def record_agent_status(agent_id: str, status: str):
    """记录 Agent 状态"""
    status_val = 1.0 if status == "running" else 0.0
    metrics.set_gauge("agent_status", status_val, agent_id=agent_id)
