"""
模型选择建议矩阵服务

功能:
- 场景→模型推荐矩阵
- 按延迟/成本/质量三维推荐
- 上下文长度/多模态/函数调用能力匹配
- 级联链路推荐
- 推荐效果追踪
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ScenarioType(str, Enum):
    SIMPLE_QA = "simple_qa"           # 简单问答
    COMPLEX_REASONING = "complex_reasoning"  # 复杂推理
    CODE_GENERATION = "code_generation"     # 代码生成
    CREATIVE_WRITING = "creative_writing"   # 创意写作
    TRANSLATION = "translation"       # 翻译
    DATA_ANALYSIS = "data_analysis"   # 数据分析
    DOCUMENT_SUMMARY = "document_summary"   # 文档摘要
    MULTIMODAL = "multimodal"         # 多模态（图片/音频）
    FUNCTION_CALLING = "function_calling"   # 工具调用
    LONG_CONTEXT = "long_context"     # 长上下文
    REALTIME_CHAT = "realtime_chat"   # 实时聊天
    BATCH_PROCESSING = "batch_processing"   # 批量处理


class PriorityDimension(str, Enum):
    LATENCY = "latency"
    COST = "cost"
    QUALITY = "quality"
    BALANCED = "balanced"


@dataclass
class ModelProfile:
    """模型画像"""
    model_id: str = ""
    provider: str = ""
    display_name: str = ""
    # 能力维度 (0-100)
    quality_score: float = 0.0
    speed_score: float = 0.0     # 速度得分（越高越快）
    cost_score: float = 0.0      # 性价比得分（越高越便宜）
    # 技术参数
    max_context_tokens: int = 4096
    supports_multimodal: bool = False
    supports_function_calling: bool = False
    supports_streaming: bool = True
    # 价格（USD / 1M tokens）
    input_price: float = 0.0
    output_price: float = 0.0
    # 延迟
    avg_latency_ms: float = 0
    p99_latency_ms: float = 0
    # 适用场景
    suitable_scenarios: list[str] = field(default_factory=list)


@dataclass
class Recommendation:
    """推荐结果"""
    scenario: str = ""
    priority: str = "balanced"
    primary_model: Optional[dict[str, Any]] = None
    fallback_models: list[dict[str, Any]] = field(default_factory=list)
    cascade_chain: list[dict[str, Any]] = field(default_factory=list)
    estimated_cost_per_1k: float = 0.0
    estimated_latency_ms: float = 0
    reasoning: str = ""


class ModelRecommendationService:
    """
    模型选择建议矩阵

    推荐逻辑:
    1. 场景匹配 → 候选模型
    2. 优先级排序（延迟/成本/质量/均衡）
    3. 能力过滤（上下文长度/多模态/函数调用）
    4. 生成级联链路
    """

    def __init__(self):
        self._profiles: dict[str, ModelProfile] = {}
        self._recommendation_log: list[dict[str, Any]] = []
        self._setup_default_profiles()

    def _setup_default_profiles(self):
        """预置主流模型画像"""
        defaults = [
            ModelProfile(
                model_id="gpt-4o", provider="openai", display_name="GPT-4o",
                quality_score=95, speed_score=75, cost_score=40,
                max_context_tokens=128000, supports_multimodal=True,
                supports_function_calling=True, input_price=2.5, output_price=10,
                avg_latency_ms=2000, p99_latency_ms=8000,
                suitable_scenarios=["complex_reasoning", "code_generation", "creative_writing", "multimodal", "function_calling"],
            ),
            ModelProfile(
                model_id="gpt-4o-mini", provider="openai", display_name="GPT-4o Mini",
                quality_score=75, speed_score=90, cost_score=85,
                max_context_tokens=128000, supports_multimodal=True,
                supports_function_calling=True, input_price=0.15, output_price=0.6,
                avg_latency_ms=800, p99_latency_ms=3000,
                suitable_scenarios=["simple_qa", "translation", "realtime_chat", "batch_processing"],
            ),
            ModelProfile(
                model_id="claude-3.5-sonnet", provider="anthropic", display_name="Claude 3.5 Sonnet",
                quality_score=93, speed_score=80, cost_score=45,
                max_context_tokens=200000, supports_multimodal=True,
                supports_function_calling=True, input_price=3, output_price=15,
                avg_latency_ms=2500, p99_latency_ms=10000,
                suitable_scenarios=["complex_reasoning", "code_generation", "creative_writing", "long_context", "document_summary"],
            ),
            ModelProfile(
                model_id="claude-3-haiku", provider="anthropic", display_name="Claude 3 Haiku",
                quality_score=70, speed_score=95, cost_score=90,
                max_context_tokens=200000, supports_multimodal=True,
                supports_function_calling=True, input_price=0.25, output_price=1.25,
                avg_latency_ms=500, p99_latency_ms=2000,
                suitable_scenarios=["simple_qa", "translation", "realtime_chat", "batch_processing"],
            ),
            ModelProfile(
                model_id="deepseek-chat", provider="deepseek", display_name="DeepSeek Chat",
                quality_score=82, speed_score=85, cost_score=95,
                max_context_tokens=128000, supports_multimodal=False,
                supports_function_calling=True, input_price=0.14, output_price=0.28,
                avg_latency_ms=1000, p99_latency_ms=4000,
                suitable_scenarios=["simple_qa", "code_generation", "data_analysis", "batch_processing"],
            ),
            ModelProfile(
                model_id="gemini-2.0-flash", provider="google", display_name="Gemini 2.0 Flash",
                quality_score=80, speed_score=92, cost_score=88,
                max_context_tokens=1000000, supports_multimodal=True,
                supports_function_calling=True, input_price=0.1, output_price=0.4,
                avg_latency_ms=600, p99_latency_ms=2500,
                suitable_scenarios=["simple_qa", "translation", "document_summary", "multimodal", "long_context"],
            ),
        ]
        for p in defaults:
            self._profiles[p.model_id] = p

    # ----------------------------------------------------------
    # 推荐
    # ----------------------------------------------------------

    def recommend(
        self,
        scenario: ScenarioType,
        priority: PriorityDimension = PriorityDimension.BALANCED,
        required_context_tokens: int = 0,
        requires_multimodal: bool = False,
        requires_function_calling: bool = False,
        max_budget_per_1k: float = 0,
    ) -> Recommendation:
        """推荐模型"""
        # 1. 场景匹配
        candidates = [
            p for p in self._profiles.values()
            if scenario.value in p.suitable_scenarios
        ]

        # 2. 能力过滤
        if required_context_tokens > 0:
            candidates = [p for p in candidates if p.max_context_tokens >= required_context_tokens]
        if requires_multimodal:
            candidates = [p for p in candidates if p.supports_multimodal]
        if requires_function_calling:
            candidates = [p for p in candidates if p.supports_function_calling]
        if max_budget_per_1k > 0:
            candidates = [
                p for p in candidates
                if (p.input_price + p.output_price) / 2 * 1000 <= max_budget_per_1k
            ]

        if not candidates:
            # 无匹配时放宽条件
            candidates = list(self._profiles.values())

        # 3. 排序
        if priority == PriorityDimension.LATENCY:
            candidates.sort(key=lambda p: -p.speed_score)
        elif priority == PriorityDimension.COST:
            candidates.sort(key=lambda p: -p.cost_score)
        elif priority == PriorityDimension.QUALITY:
            candidates.sort(key=lambda p: -p.quality_score)
        else:  # balanced
            candidates.sort(
                key=lambda p: -(p.quality_score * 0.4 + p.speed_score * 0.3 + p.cost_score * 0.3)
            )

        primary = candidates[0] if candidates else None
        fallbacks = candidates[1:4] if len(candidates) > 1 else []

        # 4. 级联链路
        cascade = self._build_cascade_chain(candidates)

        # 5. 费用估算
        est_cost = 0
        est_latency = 0
        if primary:
            est_cost = (primary.input_price + primary.output_price) / 2  # per 1k tokens
            est_latency = primary.avg_latency_ms

        rec = Recommendation(
            scenario=scenario.value,
            priority=priority.value,
            primary_model=self._profile_to_dict(primary) if primary else None,
            fallback_models=[self._profile_to_dict(f) for f in fallbacks],
            cascade_chain=[self._profile_to_dict(c) for c in cascade],
            estimated_cost_per_1k=round(est_cost, 4),
            estimated_latency_ms=est_latency,
            reasoning=self._generate_reasoning(scenario, priority, primary),
        )

        self._recommendation_log.append({
            "scenario": scenario.value,
            "priority": priority.value,
            "primary_model": primary.model_id if primary else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return rec

    def _build_cascade_chain(self, candidates: list[ModelProfile]) -> list[ModelProfile]:
        """构建级联链路：小模型→中模型→大模型"""
        if len(candidates) < 2:
            return candidates

        by_cost = sorted(candidates, key=lambda p: p.input_price)
        chain = []
        seen = set()
        for p in by_cost:
            if p.model_id not in seen:
                chain.append(p)
                seen.add(p.model_id)
            if len(chain) >= 3:
                break
        return chain

    def _generate_reasoning(
        self,
        scenario: ScenarioType,
        priority: PriorityDimension,
        primary: Optional[ModelProfile],
    ) -> str:
        if not primary:
            return "无匹配模型，建议添加更多模型配置"

        reasons = []
        scenario_names = {
            "simple_qa": "简单问答", "complex_reasoning": "复杂推理",
            "code_generation": "代码生成", "creative_writing": "创意写作",
            "translation": "翻译", "data_analysis": "数据分析",
            "document_summary": "文档摘要", "multimodal": "多模态",
            "function_calling": "工具调用", "long_context": "长上下文",
            "realtime_chat": "实时聊天", "batch_processing": "批量处理",
        }
        priority_names = {
            "latency": "低延迟优先", "cost": "低成本优先",
            "quality": "高质量优先", "balanced": "均衡",
        }

        reasons.append(f"场景「{scenario_names.get(scenario.value, scenario.value)}」× 优先级「{priority_names.get(priority.value, priority.value)}」")
        reasons.append(f"推荐 {primary.display_name} ({primary.provider})")

        if priority == PriorityDimension.LATENCY:
            reasons.append(f"平均延迟 {primary.avg_latency_ms}ms，速度评分 {primary.speed_score}")
        elif priority == PriorityDimension.COST:
            reasons.append(f"输入${primary.input_price}/输出${primary.output_price} per 1M tokens，性价比评分 {primary.cost_score}")
        elif priority == PriorityDimension.QUALITY:
            reasons.append(f"质量评分 {primary.quality_score}，上下文 {primary.max_context_tokens} tokens")

        return "；".join(reasons)

    @staticmethod
    def _profile_to_dict(p: Optional[ModelProfile]) -> Optional[dict[str, Any]]:
        if not p:
            return None
        return {
            "model_id": p.model_id,
            "provider": p.provider,
            "display_name": p.display_name,
            "quality_score": p.quality_score,
            "speed_score": p.speed_score,
            "cost_score": p.cost_score,
            "max_context_tokens": p.max_context_tokens,
            "supports_multimodal": p.supports_multimodal,
            "supports_function_calling": p.supports_function_calling,
            "input_price": p.input_price,
            "output_price": p.output_price,
            "avg_latency_ms": p.avg_latency_ms,
        }

    # ----------------------------------------------------------
    # 查询
    # ----------------------------------------------------------

    def list_profiles(self) -> list[dict[str, Any]]:
        return [self._profile_to_dict(p) for p in self._profiles.values()]

    def add_profile(self, profile: ModelProfile):
        self._profiles[profile.model_id] = profile

    def get_matrix(self) -> dict[str, Any]:
        """获取推荐矩阵（场景×模型）"""
        scenarios = [s.value for s in ScenarioType]
        matrix = {}
        for scenario in scenarios:
            rec = self.recommend(ScenarioType(scenario))
            matrix[scenario] = {
                "primary": rec.primary_model["model_id"] if rec.primary_model else None,
                "cost_per_1k": rec.estimated_cost_per_1k,
                "latency_ms": rec.estimated_latency_ms,
            }
        return matrix

    def get_recommendation_log(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._recommendation_log[-limit:]
