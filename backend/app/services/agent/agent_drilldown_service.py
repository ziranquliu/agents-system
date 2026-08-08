"""
单 Agent 下钻分析服务

功能:
- 多维度指标聚合 (性能/健康/资源/交互/成本)
- 时间范围分析
- 瓶颈检测
- 趋势分析
- 优化建议
"""

import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class DrilldownMetrics:
    """Agent 下钻指标"""
    agent_id: str = ""
    # 性能
    avg_response_time: float = 0
    p50_response_time: float = 0
    p95_response_time: float = 0
    p99_response_time: float = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    # 资源
    avg_cpu_usage: float = 0
    avg_memory_usage: float = 0
    peak_memory_usage: float = 0
    # 成本
    total_tokens: int = 0
    total_cost_usd: float = 0
    avg_tokens_per_request: float = 0
    # 交互
    avg_user_satisfaction: float = 0
    resolution_rate: float = 0
    avg_conversation_length: float = 0
    escalation_rate: float = 0
    # 健康
    uptime_percent: float = 99.9
    circuit_breaker_trips: int = 0
    recovery_count: int = 0


@dataclass
class Bottleneck:
    """瓶颈"""
    dimension: str = ""
    metric_name: str = ""
    current_value: float = 0
    threshold: float = 0
    severity: str = "warning"
    description: str = ""
    suggestion: str = ""


@dataclass
class TrendPoint:
    """趋势数据点"""
    timestamp: str = ""
    metric_name: str = ""
    value: float = 0


@dataclass
class OptimizationRecommendation:
    """优化建议"""
    category: str = ""
    priority: str = "medium"
    title: str = ""
    description: str = ""
    expected_improvement: str = ""


class AgentDrilldownService:
    """
    单 Agent 下钻分析服务

    多维度聚合 + 瓶颈检测 + 趋势分析 + 优化建议
    """

    # 瓶颈阈值
    THRESHOLDS = {
        "response_time_p99": 10.0,
        "error_rate": 0.05,
        "cpu_usage": 0.80,
        "memory_usage": 0.85,
        "circuit_breaker_trips": 3,
        "escalation_rate": 0.20,
        "avg_tokens_per_request": 4000,
    }

    def __init__(self):
        self._agent_data: dict[str, list[dict]] = defaultdict(list)
        self._response_times: dict[str, list[float]] = defaultdict(list)
        self._cost_data: dict[str, list[dict]] = defaultdict(list)
        self._health_data: dict[str, list[dict]] = defaultdict(list)
        self._bottlenecks: dict[str, list[Bottleneck]] = defaultdict(list)

    # ----------------------------------------------------------
    # 数据收集
    # ----------------------------------------------------------

    def record_request(
        self,
        agent_id: str,
        response_time: float,
        tokens_used: int,
        cost_usd: float,
        success: bool,
        user_satisfaction: float = 0,
        timestamp: Optional[str] = None,
    ):
        """记录请求数据"""
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        self._agent_data[agent_id].append({
            "timestamp": ts,
            "response_time": response_time,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd,
            "success": success,
            "user_satisfaction": user_satisfaction,
        })
        self._response_times[agent_id].append(response_time)
        self._cost_data[agent_id].append({
            "timestamp": ts,
            "tokens": tokens_used,
            "cost": cost_usd,
        })

    def record_health(self, agent_id: str, health_data: dict):
        """记录健康数据"""
        self._health_data[agent_id].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **health_data,
        })

    # ----------------------------------------------------------
    # 下钻分析
    # ----------------------------------------------------------

    def drilldown(
        self,
        agent_id: str,
        time_range_start: Optional[str] = None,
        time_range_end: Optional[str] = None,
    ) -> dict[str, Any]:
        """完整下钻分析"""
        data = self._agent_data.get(agent_id, [])
        if not data:
            return {"agent_id": agent_id, "status": "no_data", "message": "无可用数据"}

        # 时间范围过滤
        if time_range_start or time_range_end:
            data = self._filter_by_time_range(data, time_range_start, time_range_end)

        metrics = self._compute_metrics(agent_id, data)
        bottlenecks = self._detect_bottlenecks(agent_id, metrics)
        trends = self._analyze_trends(agent_id, data)
        recommendations = self._generate_recommendations(metrics, bottlenecks)

        return {
            "agent_id": agent_id,
            "time_range": {
                "start": data[0]["timestamp"] if data else "",
                "end": data[-1]["timestamp"] if data else "",
            },
            "metrics": {
                "avg_response_time": metrics.avg_response_time,
                "p50_response_time": metrics.p50_response_time,
                "p95_response_time": metrics.p95_response_time,
                "p99_response_time": metrics.p99_response_time,
                "total_requests": metrics.total_requests,
                "successful_requests": metrics.successful_requests,
                "failed_requests": metrics.failed_requests,
                "error_rate": 1 - (metrics.successful_requests / max(metrics.total_requests, 1)),
                "avg_tokens_per_request": metrics.avg_tokens_per_request,
                "total_tokens": metrics.total_tokens,
                "total_cost_usd": metrics.total_cost_usd,
                "avg_user_satisfaction": metrics.avg_user_satisfaction,
                "resolution_rate": metrics.resolution_rate,
            },
            "bottlenecks": [
                {
                    "dimension": b.dimension,
                    "metric": b.metric_name,
                    "current_value": b.current_value,
                    "threshold": b.threshold,
                    "severity": b.severity,
                    "description": b.description,
                    "suggestion": b.suggestion,
                }
                for b in bottlenecks
            ],
            "trends": trends,
            "recommendations": [
                {
                    "category": r.category,
                    "priority": r.priority,
                    "title": r.title,
                    "description": r.description,
                    "expected_improvement": r.expected_improvement,
                }
                for r in recommendations
            ],
            "overall_health_score": self._compute_health_score(metrics, bottlenecks),
        }

    def _compute_metrics(self, agent_id: str, data: list[dict]) -> DrilldownMetrics:
        """计算聚合指标"""
        response_times = [d["response_time"] for d in data]
        tokens = [d["tokens_used"] for d in data]
        costs = [d["cost_usd"] for d in data]
        satisfactions = [d["user_satisfaction"] for d in data if d.get("user_satisfaction", 0) > 0]

        successful = sum(1 for d in data if d["success"])
        failed = sum(1 for d in data if not d["success"])

        sorted_rt = sorted(response_times)
        n = len(sorted_rt)

        metrics = DrilldownMetrics(
            agent_id=agent_id,
            total_requests=len(data),
            successful_requests=successful,
            failed_requests=failed,
        )

        if response_times:
            metrics.avg_response_time = statistics.mean(response_times)
            metrics.p50_response_time = sorted_rt[n // 2] if n > 0 else 0
            metrics.p95_response_time = sorted_rt[int(n * 0.95)] if n > 0 else 0
            metrics.p99_response_time = sorted_rt[int(n * 0.99)] if n > 0 else 0

        metrics.total_tokens = sum(tokens)
        metrics.total_cost_usd = sum(costs)
        metrics.avg_tokens_per_request = metrics.total_tokens / max(len(data), 1)

        if satisfactions:
            metrics.avg_user_satisfaction = statistics.mean(satisfactions)

        if successful + failed > 0:
            metrics.resolution_rate = successful / (successful + failed)

        return metrics

    def _detect_bottlenecks(
        self, agent_id: str, metrics: DrilldownMetrics
    ) -> list[Bottleneck]:
        """检测瓶颈"""
        bottlenecks = []

        if metrics.p99_response_time > self.THRESHOLDS["response_time_p99"]:
            bottlenecks.append(Bottleneck(
                dimension="performance",
                metric_name="p99_response_time",
                current_value=metrics.p99_response_time,
                threshold=self.THRESHOLDS["response_time_p99"],
                severity="critical" if metrics.p99_response_time > 20 else "warning",
                description=f"P99 响应时间 {metrics.p99_response_time:.1f}s 超过阈值",
                suggestion="考虑优化 prompt、使用更小的模型、或添加缓存",
            ))

        total = metrics.total_requests or 1
        error_rate = metrics.failed_requests / total
        if error_rate > self.THRESHOLDS["error_rate"]:
            bottlenecks.append(Bottleneck(
                dimension="reliability",
                metric_name="error_rate",
                current_value=error_rate,
                threshold=self.THRESHOLDS["error_rate"],
                severity="critical" if error_rate > 0.10 else "warning",
                description=f"错误率 {error_rate:.1%} 超过阈值",
                suggestion="检查错误日志, 增加重试机制, 改进输入验证",
            ))

        if metrics.avg_tokens_per_request > self.THRESHOLDS["avg_tokens_per_request"]:
            bottlenecks.append(Bottleneck(
                dimension="cost",
                metric_name="avg_tokens_per_request",
                current_value=metrics.avg_tokens_per_request,
                threshold=self.THRESHOLDS["avg_tokens_per_request"],
                severity="warning",
                description=f"平均 Token 用量 {metrics.avg_tokens_per_request:.0f} 偏高",
                suggestion="启用 token 优化、压缩上下文、或使用模型级联",
            ))

        if metrics.avg_user_satisfaction > 0 and metrics.avg_user_satisfaction < 3:
            bottlenecks.append(Bottleneck(
                dimension="quality",
                metric_name="avg_user_satisfaction",
                current_value=metrics.avg_user_satisfaction,
                threshold=3.0,
                severity="warning",
                description=f"用户满意度 {metrics.avg_user_satisfaction:.1f}/5 偏低",
                suggestion="改进响应质量, 增加上下文理解, 优化回复格式",
            ))

        return bottlenecks

    def _analyze_trends(self, agent_id: str, data: list[dict]) -> list[dict]:
        """分析趋势 (最近 50 个数据点的线性回归斜率)"""
        if len(data) < 10:
            return []

        recent = data[-50:]
        response_times = [d["response_time"] for d in recent]
        costs = [d["cost_usd"] for d in recent]

        rt_slope = self._linear_slope(response_times)
        cost_slope = self._linear_slope(costs)

        trends = []
        if abs(rt_slope) > 0.01:
            trends.append({
                "metric": "response_time",
                "direction": "increasing" if rt_slope > 0 else "decreasing",
                "slope": round(rt_slope, 4),
                "description": f"响应时间{'持续上升' if rt_slope > 0 else '持续下降'}",
            })
        if abs(cost_slope) > 0.0001:
            trends.append({
                "metric": "cost",
                "direction": "increasing" if cost_slope > 0 else "decreasing",
                "slope": round(cost_slope, 6),
                "description": f"成本{'持续上升' if cost_slope > 0 else '持续下降'}",
            })
        return trends

    def _generate_recommendations(
        self, metrics: DrilldownMetrics, bottlenecks: list[Bottleneck]
    ) -> list[OptimizationRecommendation]:
        """生成优化建议"""
        recs = []
        dims = {b.dimension for b in bottlenecks}

        if "performance" in dims:
            recs.append(OptimizationRecommendation(
                category="performance",
                priority="high",
                title="启用模型级联",
                description="使用小模型处理简单请求, 复杂请求才升级到大模型",
                expected_improvement="响应时间降低 40-60%",
            ))
            recs.append(OptimizationRecommendation(
                category="performance",
                priority="medium",
                title="添加语义缓存",
                description="对相似问题启用 3 级缓存 (L1 LRU → L2 Redis → L3 向量)",
                expected_improvement="缓存命中请求延迟降低 90%+",
            ))

        if "cost" in dims:
            recs.append(OptimizationRecommendation(
                category="cost",
                priority="high",
                title="启用 Token 优化",
                description="启用 prompt 压缩和上下文窗口策略",
                expected_improvement="Token 消耗降低 30-50%",
            ))

        if "reliability" in dims:
            recs.append(OptimizationRecommendation(
                category="reliability",
                priority="high",
                title="增强错误恢复",
                description="启用自愈服务和熔断器保护",
                expected_improvement="错误率降低至 <1%",
            ))

        if "quality" in dims:
            recs.append(OptimizationRecommendation(
                category="quality",
                priority="medium",
                title="优化回复质量",
                description="调整 system prompt, 增加 few-shot 示例",
                expected_improvement="用户满意度提升 1-2 分",
            ))

        if not recs:
            recs.append(OptimizationRecommendation(
                category="general",
                priority="low",
                title="性能表现良好",
                description="当前指标均在正常范围, 继续保持",
                expected_improvement="N/A",
            ))

        return recs

    def _compute_health_score(
        self, metrics: DrilldownMetrics, bottlenecks: list[Bottleneck]
    ) -> float:
        """综合健康评分 (0-100)"""
        score = 100.0

        for b in bottlenecks:
            if b.severity == "critical":
                score -= 20
            else:
                score -= 10

        total = metrics.total_requests or 1
        error_rate = metrics.failed_requests / total
        if error_rate > 0:
            score -= error_rate * 50

        if metrics.avg_user_satisfaction > 0:
            satisfaction_score = (metrics.avg_user_satisfaction / 5) * 100
            score = score * 0.7 + satisfaction_score * 0.3

        return max(0, min(100, round(score, 1)))

    # ----------------------------------------------------------
    # 工具方法
    # ----------------------------------------------------------

    def _filter_by_time_range(
        self, data: list[dict], start: Optional[str], end: Optional[str]
    ) -> list[dict]:
        """按时间范围过滤"""
        result = data
        if start:
            result = [d for d in result if d["timestamp"] >= start]
        if end:
            result = [d for d in result if d["timestamp"] <= end]
        return result

    def _linear_slope(self, values: list[float]) -> float:
        """计算线性回归斜率"""
        n = len(values)
        if n < 2:
            return 0
        x_mean = (n - 1) / 2
        y_mean = statistics.mean(values)
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        return numerator / denominator if denominator > 0 else 0


# 全局实例
_drilldown_service: Optional[AgentDrilldownService] = None


def get_drilldown_service() -> AgentDrilldownService:
    global _drilldown_service
    if _drilldown_service is None:
        _drilldown_service = AgentDrilldownService()
    return _drilldown_service
