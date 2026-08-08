"""
健康评分服务 — 5 维度加权健康评分

功能:
- 5 维度健康评分（可用性/性能/资源/依赖/业务）
- 权重配置模板
- Top-N 健康/亚健康 Agent 排名
- 历史趋势分析
- Agent 间对比（雷达图数据）
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class HealthLevel(str, Enum):
    HEALTHY = "healthy"       # ≥80
    DEGRADED = "degraded"     # 60-79
    UNHEALTHY = "unhealthy"   # 40-59
    CRITICAL = "critical"     # <40


class HealthDimension(str, Enum):
    AVAILABILITY = "availability"     # 可用性
    PERFORMANCE = "performance"       # 性能
    RESOURCES = "resources"           # 资源
    DEPENDENCIES = "dependencies"     # 依赖
    BUSINESS = "business"             # 业务指标


@dataclass
class HealthWeights:
    """维度权重"""
    availability: float = 0.30
    performance: float = 0.25
    resources: float = 0.15
    dependencies: float = 0.15
    business: float = 0.15

    def to_dict(self) -> dict[str, float]:
        return {
            "availability": self.availability,
            "performance": self.performance,
            "resources": self.resources,
            "dependencies": self.dependencies,
            "business": self.business,
        }


# 预设权重模板
WEIGHT_TEMPLATES = {
    "balanced": HealthWeights(),
    "performance_first": HealthWeights(
        availability=0.25, performance=0.35, resources=0.15, dependencies=0.10, business=0.15,
    ),
    "stability_first": HealthWeights(
        availability=0.40, performance=0.20, resources=0.15, dependencies=0.15, business=0.10,
    ),
    "business_first": HealthWeights(
        availability=0.20, performance=0.20, resources=0.10, dependencies=0.10, business=0.40,
    ),
}


@dataclass
class DimensionScore:
    """维度评分明细"""
    dimension: str = ""
    score: float = 0.0  # 0-100
    weight: float = 0.0
    weighted_score: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthScore:
    """Agent 健康评分"""
    agent_id: str = ""
    overall_score: float = 0.0
    level: HealthLevel = HealthLevel.CRITICAL
    dimensions: list[DimensionScore] = field(default_factory=list)
    # 原始指标
    uptime_pct: float = 0.0
    avg_response_ms: float = 0.0
    p99_response_ms: float = 0.0
    error_rate: float = 0.0
    cpu_usage_pct: float = 0.0
    memory_usage_pct: float = 0.0
    dependency_health: float = 0.0
    request_count: int = 0
    success_count: int = 0
    timestamp: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "overall_score": round(self.overall_score, 1),
            "level": self.level.value,
            "dimensions": [
                {
                    "name": d.dimension,
                    "score": round(d.score, 1),
                    "weight": d.weight,
                    "weighted_score": round(d.weighted_score, 1),
                    "details": d.details,
                }
                for d in self.dimensions
            ],
            "metrics": {
                "uptime_pct": round(self.uptime_pct, 2),
                "avg_response_ms": round(self.avg_response_ms, 1),
                "p99_response_ms": round(self.p99_response_ms, 1),
                "error_rate": round(self.error_rate, 4),
                "cpu_usage_pct": round(self.cpu_usage_pct, 1),
                "memory_usage_pct": round(self.memory_usage_pct, 1),
                "dependency_health": round(self.dependency_health, 1),
                "request_count": self.request_count,
                "success_count": self.success_count,
            },
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


@dataclass
class RadarData:
    """雷达图数据（Agent 间对比）"""
    agents: list[str] = field(default_factory=list)
    dimensions: list[str] = field(default_factory=list)
    scores: dict[str, list[float]] = field(default_factory=dict)  # agent_id → scores


class HealthScoringService:
    """
    健康评分服务

    5 维度公式:
    overall = Σ(dimension_score × weight)

    等级:
    - healthy: ≥80
    - degraded: 60-79
    - unhealthy: 40-59
    - critical: <40
    """

    def __init__(self, weights_template: str = "balanced"):
        self._weights = WEIGHT_TEMPLATES.get(weights_template, HealthWeights())
        self._scores: dict[str, HealthScore] = {}
        self._history: dict[str, list[dict[str, Any]]] = {}  # agent_id → score history

    def set_weights(self, weights: HealthWeights):
        self._weights = weights

    def set_weights_template(self, template_name: str):
        if template_name in WEIGHT_TEMPLATES:
            self._weights = WEIGHT_TEMPLATES[template_name]

    # ----------------------------------------------------------
    # 评分
    # ----------------------------------------------------------

    def score_agent(
        self,
        agent_id: str,
        metrics: dict[str, Any],
    ) -> HealthScore:
        """
        为 Agent 生成健康评分

        metrics 示例:
        {
            "uptime_pct": 99.5,
            "avg_response_ms": 1500,
            "p99_response_ms": 5000,
            "error_rate": 0.02,
            "cpu_usage_pct": 65,
            "memory_usage_pct": 70,
            "dependency_health": 85,
            "request_count": 1000,
            "success_count": 980,
        }
        """
        score = HealthScore(
            agent_id=agent_id,
            timestamp=datetime.now(timezone.utc),
            uptime_pct=metrics.get("uptime_pct", 100),
            avg_response_ms=metrics.get("avg_response_ms", 0),
            p99_response_ms=metrics.get("p99_response_ms", 0),
            error_rate=metrics.get("error_rate", 0),
            cpu_usage_pct=metrics.get("cpu_usage_pct", 0),
            memory_usage_pct=metrics.get("memory_usage_pct", 0),
            dependency_health=metrics.get("dependency_health", 100),
            request_count=metrics.get("request_count", 0),
            success_count=metrics.get("success_count", 0),
        )

        # 1. 可用性
        avail_score = self._score_availability(
            uptime_pct=score.uptime_pct,
            error_rate=score.error_rate,
            request_count=score.request_count,
            success_count=score.success_count,
        )

        # 2. 性能
        perf_score = self._score_performance(
            avg_response_ms=score.avg_response_ms,
            p99_response_ms=score.p99_response_ms,
        )

        # 3. 资源
        res_score = self._score_resources(
            cpu_usage_pct=score.cpu_usage_pct,
            memory_usage_pct=score.memory_usage_pct,
        )

        # 4. 依赖
        dep_score = score.dependency_health

        # 5. 业务
        biz_score = self._score_business(
            request_count=score.request_count,
            success_count=score.success_count,
            error_rate=score.error_rate,
        )

        dims = [
            DimensionScore(
                dimension=HealthDimension.AVAILABILITY.value,
                score=avail_score,
                weight=self._weights.availability,
                weighted_score=avail_score * self._weights.availability,
            ),
            DimensionScore(
                dimension=HealthDimension.PERFORMANCE.value,
                score=perf_score,
                weight=self._weights.performance,
                weighted_score=perf_score * self._weights.performance,
            ),
            DimensionScore(
                dimension=HealthDimension.RESOURCES.value,
                score=res_score,
                weight=self._weights.resources,
                weighted_score=res_score * self._weights.resources,
            ),
            DimensionScore(
                dimension=HealthDimension.DEPENDENCIES.value,
                score=dep_score,
                weight=self._weights.dependencies,
                weighted_score=dep_score * self._weights.dependencies,
            ),
            DimensionScore(
                dimension=HealthDimension.BUSINESS.value,
                score=biz_score,
                weight=self._weights.business,
                weighted_score=biz_score * self._weights.business,
            ),
        ]

        score.dimensions = dims
        score.overall_score = sum(d.weighted_score for d in dims)
        score.level = self._compute_level(score.overall_score)

        # 存储
        self._scores[agent_id] = score
        if agent_id not in self._history:
            self._history[agent_id] = []
        self._history[agent_id].append({
            "score": round(score.overall_score, 1),
            "level": score.level.value,
            "timestamp": score.timestamp.isoformat() if score.timestamp else None,
        })
        # 保留最近 500 条
        if len(self._history[agent_id]) > 500:
            self._history[agent_id] = self._history[agent_id][-500:]

        return score

    # ----------------------------------------------------------
    # 维度评分算法
    # ----------------------------------------------------------

    def _score_availability(
        self,
        uptime_pct: float,
        error_rate: float,
        request_count: int,
        success_count: int,
    ) -> float:
        """可用性评分"""
        score = 0.0

        # Uptime 占 60%
        score += min(uptime_pct, 100) * 0.6

        # 错误率占 40%
        error_score = max(0, 100 - error_rate * 1000)  # 1% error → -10 分
        score += error_score * 0.4

        return min(max(score, 0), 100)

    def _score_performance(
        self,
        avg_response_ms: float,
        p99_response_ms: float,
    ) -> float:
        """性能评分"""
        # 平均响应时间
        if avg_response_ms <= 500:
            avg_score = 100
        elif avg_response_ms <= 1000:
            avg_score = 90
        elif avg_response_ms <= 2000:
            avg_score = 80
        elif avg_response_ms <= 5000:
            avg_score = 60
        elif avg_response_ms <= 10000:
            avg_score = 40
        else:
            avg_score = max(0, 20 - (avg_response_ms - 10000) / 1000)

        # P99 响应时间
        if p99_response_ms <= 1000:
            p99_score = 100
        elif p99_response_ms <= 3000:
            p99_score = 85
        elif p99_response_ms <= 5000:
            p99_score = 70
        elif p99_response_ms <= 10000:
            p99_score = 50
        else:
            p99_score = max(0, 30 - (p99_response_ms - 10000) / 2000)

        return avg_score * 0.6 + p99_score * 0.4

    def _score_resources(
        self,
        cpu_usage_pct: float,
        memory_usage_pct: float,
    ) -> float:
        """资源评分"""
        # CPU 使用率（越低越好，但不能太低）
        if cpu_usage_pct <= 70:
            cpu_score = 100 - (cpu_usage_pct * 0.3)  # 0%→100, 70%→79
        elif cpu_usage_pct <= 85:
            cpu_score = 79 - (cpu_usage_pct - 70) * 3  # 70→79, 85→34
        else:
            cpu_score = max(0, 34 - (cpu_usage_pct - 85) * 5)

        # 内存使用率
        if memory_usage_pct <= 70:
            mem_score = 100 - (memory_usage_pct * 0.3)
        elif memory_usage_pct <= 85:
            mem_score = 79 - (memory_usage_pct - 70) * 3
        else:
            mem_score = max(0, 34 - (memory_usage_pct - 85) * 5)

        return cpu_score * 0.5 + mem_score * 0.5

    def _score_business(
        self,
        request_count: int,
        success_count: int,
        error_rate: float,
    ) -> float:
        """业务指标评分"""
        if request_count == 0:
            return 50.0  # 无数据给基准分

        success_rate = success_count / request_count if request_count > 0 else 0
        score = success_rate * 100

        # 请求量奖励（越多说明服务越活跃）
        volume_bonus = min(request_count / 1000, 10)  # 最多加 10 分
        return min(score + volume_bonus, 100)

    def _compute_level(self, score: float) -> HealthLevel:
        if score >= 80:
            return HealthLevel.HEALTHY
        elif score >= 60:
            return HealthLevel.DEGRADED
        elif score >= 40:
            return HealthLevel.UNHEALTHY
        else:
            return HealthLevel.CRITICAL

    # ----------------------------------------------------------
    # 查询与分析
    # ----------------------------------------------------------

    def get_score(self, agent_id: str) -> Optional[dict[str, Any]]:
        score = self._scores.get(agent_id)
        return score.to_dict() if score else None

    def get_top_healthy(self, limit: int = 5) -> list[dict[str, Any]]:
        """Top-N 健康 Agent"""
        sorted_scores = sorted(
            self._scores.values(),
            key=lambda s: s.overall_score,
            reverse=True,
        )
        return [s.to_dict() for s in sorted_scores[:limit] if s.level == HealthLevel.HEALTHY]

    def get_top_degraded(self, limit: int = 5) -> list[dict[str, Any]]:
        """Top-N 亚健康 Agent（需要关注）"""
        sorted_scores = sorted(
            self._scores.values(),
            key=lambda s: s.overall_score,
        )
        return [s.to_dict() for s in sorted_scores[:limit] if s.level in (HealthLevel.DEGRADED, HealthLevel.UNHEALTHY)]

    def get_history(
        self,
        agent_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """获取 Agent 健康历史"""
        return self._history.get(agent_id, [])[-limit:]

    def get_radar_data(
        self,
        agent_ids: Optional[list[str]] = None,
    ) -> RadarData:
        """获取雷达图数据（Agent 间对比）"""
        if agent_ids is None:
            agent_ids = list(self._scores.keys())

        dimensions = [d.value for d in HealthDimension]
        radar = RadarData(
            agents=agent_ids,
            dimensions=dimensions,
        )

        for agent_id in agent_ids:
            score = self._scores.get(agent_id)
            if score:
                radar.scores[agent_id] = [
                    round(d.score, 1) for d in score.dimensions
                ]
            else:
                radar.scores[agent_id] = [0.0] * len(dimensions)

        return radar

    def get_overall_stats(self) -> dict[str, Any]:
        """获取整体健康统计"""
        if not self._scores:
            return {"total_agents": 0}

        level_counts = {}
        all_scores = []
        for s in self._scores.values():
            level_counts[s.level.value] = level_counts.get(s.level.value, 0) + 1
            all_scores.append(s.overall_score)

        return {
            "total_agents": len(self._scores),
            "avg_health_score": round(sum(all_scores) / len(all_scores), 1) if all_scores else 0,
            "level_distribution": level_counts,
            "healthy_count": level_counts.get("healthy", 0),
            "degraded_count": level_counts.get("degraded", 0),
            "unhealthy_count": level_counts.get("unhealthy", 0),
            "critical_count": level_counts.get("critical", 0),
        }
