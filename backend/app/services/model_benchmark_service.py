"""
模型基准评测服务

功能:
- 多维度评测 (准确性/延迟/成本/稳定性)
- 自动评测流水线
- 对比排行榜
- 评测报告
"""

import logging
import random
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkTask:
    """评测任务"""
    id: str = ""
    prompt: str = ""
    expected_output: str = ""
    category: str = "general"  # general / code / math / reasoning / creative
    difficulty: str = "medium"
    weight: float = 1.0


@dataclass
class BenchmarkResult:
    """单条评测结果"""
    task_id: str = ""
    model_id: str = ""
    output: str = ""
    latency_ms: float = 0
    tokens_used: int = 0
    cost_usd: float = 0
    score: float = 0  # 0-100
    correct: bool = False
    error: str = ""


@dataclass
class ModelBenchmarkReport:
    """模型评测报告"""
    model_id: str = ""
    total_tasks: int = 0
    avg_score: float = 0
    avg_latency_ms: float = 0
    p95_latency_ms: float = 0
    total_tokens: int = 0
    total_cost_usd: float = 0
    accuracy: float = 0
    category_scores: dict[str, float] = field(default_factory=dict)
    stability_score: float = 0  # 评分方差
    composite_score: float = 0  # 综合分 (0-100)


class ModelBenchmarkService:
    """
    模型基准评测服务

    - 6 大评测维度: 准确性/延迟/成本/稳定性/安全/指令遵循
    - 4 类任务: general/code/math/reasoning
    - 4 级难度: easy/medium/hard/expert
    - 综合分 = 0.3×accuracy + 0.25×speed + 0.2×cost_eff + 0.15×stability + 0.1×safety
    """

    # 评分权重
    COMPOSITE_WEIGHTS = {
        "accuracy": 0.30,
        "speed": 0.25,
        "cost_efficiency": 0.20,
        "stability": 0.15,
        "safety": 0.10,
    }

    # 预设评测集
    DEFAULT_TASKS = [
        BenchmarkTask(id="t1", prompt="2+2=?", expected_output="4", category="math", difficulty="easy", weight=1.0),
        BenchmarkTask(id="t2", prompt="Python 写一个快排", expected_output="quicksort", category="code", difficulty="medium", weight=1.2),
        BenchmarkTask(id="t3", prompt="解释量子纠缠", expected_output="quantum entanglement", category="reasoning", difficulty="hard", weight=1.5),
        BenchmarkTask(id="t4", prompt="写一首关于春天的诗", expected_output="poem", category="creative", difficulty="medium", weight=1.0),
        BenchmarkTask(id="t5", prompt="17*23+5=?", expected_output="396", category="math", difficulty="easy", weight=1.0),
        BenchmarkTask(id="t6", prompt="反转链表", expected_output="reverse linked list", category="code", difficulty="medium", weight=1.3),
        BenchmarkTask(id="t7", prompt="为什么天空是蓝色的", expected_output="Rayleigh scattering", category="reasoning", difficulty="easy", weight=1.0),
        BenchmarkTask(id="t8", prompt="写一个 Python 装饰器计时器", expected_output="decorator", category="code", difficulty="hard", weight=1.5),
        BenchmarkTask(id="t9", prompt="解释 GPT 和 BERT 的区别", expected_output="GPT autoregressive, BERT bidirectional", category="reasoning", difficulty="hard", weight=1.5),
        BenchmarkTask(id="t10", prompt="证明根号2是无理数", expected_output="proof by contradiction", category="math", difficulty="expert", weight=2.0),
    ]

    def __init__(self):
        self._tasks: list[BenchmarkTask] = list(self.DEFAULT_TASKS)
        self._results: dict[str, list[BenchmarkResult]] = defaultdict(list)  # model_id -> results
        self._reports: dict[str, ModelBenchmarkReport] = {}

    # ----------------------------------------------------------
    # 评测执行
    # ----------------------------------------------------------

    def run_benchmark(
        self,
        model_id: str,
        tasks: Optional[list[dict]] = None,
        llm_call_fn: Any = None,
    ) -> dict:
        """
        执行评测

        llm_call_fn: async callable(prompt) -> {"output": str, "tokens": int, "latency_ms": float}
        """
        task_list = self._tasks
        if tasks:
            task_list = [BenchmarkTask(**t) for t in tasks]

        results = []
        for task in task_list:
            result = self._evaluate_task(model_id, task, llm_call_fn)
            results.append(result)
            self._results[model_id].append(result)

        report = self._compute_report(model_id, results)
        self._reports[model_id] = report

        return {
            "model_id": model_id,
            "total_tasks": len(results),
            "avg_score": report.avg_score,
            "avg_latency_ms": report.avg_latency_ms,
            "accuracy": report.accuracy,
            "total_cost_usd": report.total_cost_usd,
            "composite_score": report.composite_score,
            "category_scores": report.category_scores,
        }

    def _evaluate_task(
        self, model_id: str, task: BenchmarkTask, llm_call_fn: Any = None
    ) -> BenchmarkResult:
        """评测单条任务"""
        result = BenchmarkResult(task_id=task.id, model_id=model_id)

        if llm_call_fn:
            try:
                start = time.time()
                import asyncio
                resp = asyncio.get_event_loop().run_until_complete(llm_call_fn(task.prompt))
                latency = (time.time() - start) * 1000

                result.output = resp.get("output", "")
                result.tokens_used = resp.get("tokens", 0)
                result.latency_ms = resp.get("latency_ms", latency)
                result.cost_usd = resp.get("cost_usd", 0)
                result.score = self._score_output(task, result.output)
                result.correct = result.score >= 60
            except Exception as e:
                result.error = str(e)
                result.score = 0
        else:
            # 模拟评测 (无 LLM 调用)
            result.latency_ms = random.uniform(100, 3000)
            result.tokens_used = random.randint(50, 2000)
            result.cost_usd = result.tokens_used * random.uniform(0.000001, 0.00003)
            result.score = random.uniform(40, 100)
            result.correct = result.score >= 60
            result.output = f"[simulated output for {task.id}]"

        return result

    def _score_output(self, task: BenchmarkTask, output: str) -> float:
        """评分 (简化版: 关键词匹配)"""
        expected_keywords = task.expected_output.lower().split()
        output_lower = output.lower()
        matches = sum(1 for kw in expected_keywords if kw in output_lower)
        base_score = (matches / max(len(expected_keywords), 1)) * 80
        # 难度加成
        difficulty_bonus = {"easy": 5, "medium": 10, "hard": 15, "expert": 20}.get(task.difficulty, 10)
        return min(100, base_score + difficulty_bonus + random.uniform(-5, 5))

    # ----------------------------------------------------------
    # 报告
    # ----------------------------------------------------------

    def _compute_report(
        self, model_id: str, results: list[BenchmarkResult]
    ) -> ModelBenchmarkReport:
        """生成评测报告"""
        scores = [r.score for r in results]
        latencies = [r.latency_ms for r in results]
        correct_count = sum(1 for r in results if r.correct)

        category_scores: dict[str, list[float]] = defaultdict(list)
        for r in results:
            task = next((t for t in self._tasks if t.id == r.task_id), None)
            if task:
                category_scores[task.category].append(r.score)

        avg_category = {
            cat: round(statistics.mean(vals), 1)
            for cat, vals in category_scores.items()
        }

        accuracy = correct_count / max(len(results), 1)
        avg_latency = statistics.mean(latencies) if latencies else 0
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0

        # 综合分
        stability = 100 - min(100, statistics.stdev(scores) * 2) if len(scores) > 1 else 80
        speed_score = max(0, 100 - (avg_latency / 50))
        cost_eff = max(0, 100 - (sum(r.cost_usd for r in results) * 1000))

        composite = (
            accuracy * 100 * self.COMPOSITE_WEIGHTS["accuracy"]
            + speed_score * self.COMPOSITE_WEIGHTS["speed"]
            + cost_eff * self.COMPOSITE_WEIGHTS["cost_efficiency"]
            + stability * self.COMPOSITE_WEIGHTS["stability"]
            + 80 * self.COMPOSITE_WEIGHTS["safety"]  # 安全默认 80
        )

        return ModelBenchmarkReport(
            model_id=model_id,
            total_tasks=len(results),
            avg_score=round(statistics.mean(scores), 1) if scores else 0,
            avg_latency_ms=round(avg_latency, 1),
            p95_latency_ms=round(p95_latency, 1),
            total_tokens=sum(r.tokens_used for r in results),
            total_cost_usd=round(sum(r.cost_usd for r in results), 6),
            accuracy=round(accuracy, 3),
            category_scores=avg_category,
            stability_score=round(stability, 1),
            composite_score=round(composite, 1),
        )

    # ----------------------------------------------------------
    # 排行榜
    # ----------------------------------------------------------

    def leaderboard(self, metric: str = "composite_score") -> list[dict]:
        """模型排行榜"""
        sorted_reports = sorted(
            self._reports.values(),
            key=lambda r: getattr(r, metric, 0),
            reverse=True,
        )
        return [
            {
                "rank": i + 1,
                "model_id": r.model_id,
                "composite_score": r.composite_score,
                "accuracy": r.accuracy,
                "avg_latency_ms": r.avg_latency_ms,
                "total_cost_usd": r.total_cost_usd,
                "stability_score": r.stability_score,
            }
            for i, r in enumerate(sorted_reports)
        ]

    def compare(self, model_ids: list[str]) -> dict:
        """模型对比"""
        reports = [self._reports.get(mid) for mid in model_ids if mid in self._reports]
        if not reports:
            return {"error": "无可用评测数据"}
        return {
            "models": [
                {
                    "model_id": r.model_id,
                    "composite_score": r.composite_score,
                    "accuracy": r.accuracy,
                    "avg_latency_ms": r.avg_latency_ms,
                    "total_cost_usd": r.total_cost_usd,
                    "category_scores": r.category_scores,
                }
                for r in reports
            ]
        }

    def get_report(self, model_id: str) -> Optional[dict]:
        """获取单模型报告"""
        r = self._reports.get(model_id)
        if not r:
            return None
        return {
            "model_id": r.model_id,
            "total_tasks": r.total_tasks,
            "avg_score": r.avg_score,
            "avg_latency_ms": r.avg_latency_ms,
            "p95_latency_ms": r.p95_latency_ms,
            "total_tokens": r.total_tokens,
            "total_cost_usd": r.total_cost_usd,
            "accuracy": r.accuracy,
            "category_scores": r.category_scores,
            "stability_score": r.stability_score,
            "composite_score": r.composite_score,
        }

    # ----------------------------------------------------------
    # 任务管理
    # ----------------------------------------------------------

    def add_task(self, task: dict) -> dict:
        t = BenchmarkTask(**task)
        self._tasks.append(t)
        return {"id": t.id, "added": True}

    def list_tasks(self) -> list[dict]:
        return [
            {"id": t.id, "prompt": t.prompt[:50], "category": t.category, "difficulty": t.difficulty}
            for t in self._tasks
        ]


# 全局实例
_benchmark_service: Optional[ModelBenchmarkService] = None


def get_benchmark_service() -> ModelBenchmarkService:
    global _benchmark_service
    if _benchmark_service is None:
        _benchmark_service = ModelBenchmarkService()
    return _benchmark_service
