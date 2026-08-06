"""
Token 优化效果评估服务

功能:
- 前后对比：优化前 vs 优化后
- Token 节省率统计
- 缓存命中率统计
- 级联降级率统计
- Prompt 压缩率统计
- 综合 ROI 评分
- 趋势分析
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class OptimizationMetrics:
    """优化指标"""
    period: str = ""        # daily / weekly / monthly
    # Token 使用
    total_tokens_before: int = 0
    total_tokens_after: int = 0
    token_savings: int = 0
    token_savings_pct: float = 0.0
    # 成本
    total_cost_before: float = 0.0
    total_cost_after: float = 0.0
    cost_savings: float = 0.0
    cost_savings_pct: float = 0.0
    # 缓存
    cache_total_queries: int = 0
    cache_hits: int = 0
    cache_hit_rate: float = 0.0
    # 级联
    cascade_total: int = 0
    cascade_downgrades: int = 0
    cascade_downgrade_rate: float = 0.0
    cascade_upgrade_rate: float = 0.0
    # Prompt 压缩
    compression_total: int = 0
    compression_tokens_saved: int = 0
    compression_rate: float = 0.0
    # 质量
    avg_quality_before: float = 0.0
    avg_quality_after: float = 0.0
    quality_delta: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {k: round(v, 2) if isinstance(v, float) else v
                for k, v in self.__dict__.items()}


@dataclass
class EvaluationReport:
    """评估报告"""
    id: str = ""
    generated_at: Optional[datetime] = None
    metrics: Optional[OptimizationMetrics] = None
    roi_score: float = 0.0       # 0-100 综合评分
    grade: str = ""              # A/B/C/D/F
    insights: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "metrics": self.metrics.to_dict() if self.metrics else {},
            "roi_score": self.roi_score,
            "grade": self.grade,
            "insights": self.insights,
            "recommendations": self.recommendations,
        }


class OptimizationEvalService:
    """
    Token 优化效果评估服务
    """

    def __init__(self):
        self._baselines: dict[str, dict[str, Any]] = {}
        self._current: dict[str, dict[str, Any]] = {}
        self._reports: list[EvaluationReport] = []

    # ----------------------------------------------------------
    # 数据录入
    # ----------------------------------------------------------

    def set_baseline(self, period: str = "monthly", data: Optional[dict[str, Any]] = None):
        """设置优化前基线"""
        self._baselines[period] = data or {}
        logger.info(f"Baseline set for {period}")

    def record_current(self, period: str = "monthly", data: Optional[dict[str, Any]] = None):
        """记录当前数据"""
        self._current[period] = data or {}

    def update_metric(self, key: str, value: Any, period: str = "monthly"):
        """更新单个指标"""
        if period not in self._current:
            self._current[period] = {}
        self._current[period][key] = value

    # ----------------------------------------------------------
    # 评估
    # ----------------------------------------------------------

    def evaluate(self, period: str = "monthly") -> EvaluationReport:
        """生成优化效果评估报告"""
        import uuid
        baseline = self._baselines.get(period, {})
        current = self._current.get(period, {})

        metrics = OptimizationMetrics(period=period)

        # Token 节省
        metrics.total_tokens_before = baseline.get("total_tokens", 0)
        metrics.total_tokens_after = current.get("total_tokens", 0)
        if metrics.total_tokens_before > 0:
            metrics.token_savings = metrics.total_tokens_before - metrics.total_tokens_after
            metrics.token_savings_pct = metrics.token_savings / metrics.total_tokens_before * 100

        # 成本节省
        metrics.total_cost_before = baseline.get("total_cost", 0)
        metrics.total_cost_after = current.get("total_cost", 0)
        if metrics.total_cost_before > 0:
            metrics.cost_savings = metrics.total_cost_before - metrics.total_cost_after
            metrics.cost_savings_pct = metrics.cost_savings / metrics.total_cost_before * 100

        # 缓存命中率
        metrics.cache_total_queries = current.get("cache_total_queries", 0)
        metrics.cache_hits = current.get("cache_hits", 0)
        if metrics.cache_total_queries > 0:
            metrics.cache_hit_rate = metrics.cache_hits / metrics.cache_total_queries * 100

        # 级联统计
        metrics.cascade_total = current.get("cascade_total", 0)
        metrics.cascade_downgrades = current.get("cascade_downgrades", 0)
        if metrics.cascade_total > 0:
            metrics.cascade_downgrade_rate = metrics.cascade_downgrades / metrics.cascade_total * 100

        # 压缩统计
        metrics.compression_total = current.get("compression_total", 0)
        metrics.compression_tokens_saved = current.get("compression_tokens_saved", 0)
        if metrics.compression_total > 0:
            metrics.compression_rate = metrics.compression_tokens_saved / max(
                current.get("compression_total_input", metrics.compression_total * 500), 1
            ) * 100

        # 质量
        metrics.avg_quality_before = baseline.get("avg_quality_score", 0)
        metrics.avg_quality_after = current.get("avg_quality_score", 0)
        metrics.quality_delta = metrics.avg_quality_after - metrics.avg_quality_before

        # ROI 评分
        roi = self._compute_roi(metrics)
        grade = self._compute_grade(roi)

        # 生成洞察
        insights = self._generate_insights(metrics)
        recommendations = self._generate_recommendations(metrics)

        report = EvaluationReport(
            id=str(uuid.uuid4()),
            generated_at=datetime.now(timezone.utc),
            metrics=metrics,
            roi_score=roi,
            grade=grade,
            insights=insights,
            recommendations=recommendations,
        )
        self._reports.append(report)
        return report

    def _compute_roi(self, m: OptimizationMetrics) -> float:
        """计算综合 ROI 评分 (0-100)"""
        score = 50.0  # 基准分

        # 成本节省 (+20)
        if m.cost_savings_pct > 30:
            score += 20
        elif m.cost_savings_pct > 10:
            score += 10
        elif m.cost_savings_pct > 0:
            score += 5

        # 缓存命中率 (+15)
        if m.cache_hit_rate > 30:
            score += 15
        elif m.cache_hit_rate > 10:
            score += 8
        elif m.cache_hit_rate > 0:
            score += 3

        # 质量保持 (+15)
        if m.quality_delta >= 0:
            score += 15
        elif m.quality_delta > -5:
            score += 5
        else:
            score -= 10

        return min(max(score, 0), 100)

    @staticmethod
    def _compute_grade(roi: float) -> str:
        if roi >= 90:
            return "A"
        elif roi >= 75:
            return "B"
        elif roi >= 60:
            return "C"
        elif roi >= 40:
            return "D"
        return "F"

    def _generate_insights(self, m: OptimizationMetrics) -> list[str]:
        insights = []
        if m.token_savings_pct > 20:
            insights.append(f"Token 节省 {m.token_savings_pct:.1f}%，优化效果显著")
        elif m.token_savings_pct > 0:
            insights.append(f"Token 节省 {m.token_savings_pct:.1f}%，优化有效")
        else:
            insights.append("Token 使用未减少，建议检查优化策略")

        if m.cache_hit_rate > 20:
            insights.append(f"缓存命中率 {m.cache_hit_rate:.1f}%，语义缓存效果好")
        elif m.cache_hit_rate > 0:
            insights.append(f"缓存命中率 {m.cache_hit_rate:.1f}%，有提升空间")
        else:
            insights.append("缓存命中率为0，建议检查缓存配置")

        if m.quality_delta >= 5:
            insights.append(f"质量提升 {m.quality_delta:.1f} 分，优化同时提升了质量")
        elif m.quality_delta < -5:
            insights.append(f"⚠️ 质量下降 {abs(m.quality_delta):.1f} 分，需关注")
        return insights

    def _generate_recommendations(self, m: OptimizationMetrics) -> list[str]:
        recs = []
        if m.cache_hit_rate < 10:
            recs.append("建议增大语义缓存 TTL 或调整相似度阈值")
        if m.cascade_downgrade_rate > 30:
            recs.append("级联降级率偏高，建议调整小模型置信度阈值")
        if m.compression_rate < 10:
            recs.append("压缩率偏低，建议调整压缩策略或 chunk 大小")
        if m.quality_delta < -3:
            recs.append("质量下降，建议回滚部分激进优化策略")
        if not recs:
            recs.append("各项指标良好，建议维持当前策略")
        return recs

    # ----------------------------------------------------------
    # 查询
    # ----------------------------------------------------------

    def get_reports(self, limit: int = 10) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self._reports[-limit:]]

    def get_latest(self) -> Optional[dict[str, Any]]:
        return self._reports[-1].to_dict() if self._reports else None
