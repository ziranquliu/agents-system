"""
模型热切换服务

功能:
- 运行时动态切换模型
- 无缝过渡 (请求级别)
- 回滚机制
- 切换历史
- 灰度发布
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """模型配置"""
    model_id: str = ""
    provider: str = ""
    api_key: str = ""
    endpoint: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: float = 30
    is_active: bool = True
    priority: int = 0  # 越大优先级越高


@dataclass
class SwitchRecord:
    """切换记录"""
    id: str = ""
    from_model: str = ""
    to_model: str = ""
    reason: str = ""
    triggered_by: str = "system"  # system / manual / auto / rollback
    timestamp: float = 0
    status: str = "completed"  # completed / failed / rolled_back
    traffic_percent: int = 100
    rollback_available: bool = True


@dataclass
class TrafficSplit:
    """流量分配"""
    model_id: str = ""
    percent: int = 0
    is_active: bool = True


class ModelHotswapService:
    """
    模型热切换服务

    - 运行时无停机切换
    - 请求级别粒度
    - 灰度发布 (traffic_percent)
    - 自动回滚 (错误率 > 阈值)
    - 切换历史
    """

    ERROR_RATE_THRESHOLD = 0.10  # 10% 错误率触发回滚
    MIN_EVALUATION_TRAFFIC = 100  # 最少评估 100 个请求

    def __init__(self):
        self._models: dict[str, ModelConfig] = {}
        self._active_model: str = ""
        self._fallback_chain: list[str] = []
        self._history: list[SwitchRecord] = []
        self._traffic_splits: list[TrafficSplit] = []
        self._error_counts: dict[str, int] = defaultdict(int)
        self._request_counts: dict[str, int] = defaultdict(int)
        self._call_fn: Optional[Callable] = None

    # ----------------------------------------------------------
    # 模型管理
    # ----------------------------------------------------------

    def register_model(self, config: dict) -> dict:
        """注册模型"""
        mc = ModelConfig(**config)
        self._models[mc.model_id] = mc
        if not self._active_model:
            self._active_model = mc.model_id
        return {"model_id": mc.model_id, "registered": True}

    def get_model(self, model_id: str) -> Optional[dict]:
        m = self._models.get(model_id)
        if not m:
            return None
        return {
            "model_id": m.model_id,
            "provider": m.provider,
            "endpoint": m.endpoint,
            "max_tokens": m.max_tokens,
            "temperature": m.temperature,
            "is_active": m.is_active,
            "priority": m.priority,
        }

    def list_models(self) -> list[dict]:
        return [
            {
                "model_id": m.model_id,
                "provider": m.provider,
                "is_active": m.is_active,
                "is_current": m.model_id == self._active_model,
                "priority": m.priority,
            }
            for m in self._models.values()
        ]

    def set_fallback_chain(self, chain: list[str]):
        """设置降级链"""
        self._fallback_chain = chain

    # ----------------------------------------------------------
    # 切换
    # ----------------------------------------------------------

    def switch(
        self,
        to_model: str,
        reason: str = "",
        triggered_by: str = "manual",
        traffic_percent: int = 100,
    ) -> dict:
        """切换模型"""
        if to_model not in self._models:
            return {"error": f"模型 {to_model} 未注册"}

        from_model = self._active_model
        record = SwitchRecord(
            id=f"sw_{int(time.time() * 1000)}",
            from_model=from_model,
            to_model=to_model,
            reason=reason,
            triggered_by=triggered_by,
            timestamp=time.time(),
            traffic_percent=traffic_percent,
        )

        if traffic_percent < 100:
            # 灰度发布
            self._traffic_splits = [
                TrafficSplit(model_id=from_model, percent=100 - traffic_percent, is_active=True),
                TrafficSplit(model_id=to_model, percent=traffic_percent, is_active=True),
            ]
            record.status = "canary"
        else:
            self._active_model = to_model
            self._traffic_splits = [TrafficSplit(model_id=to_model, percent=100, is_active=True)]
            record.status = "completed"

        self._history.append(record)
        logger.info("模型切换: %s → %s, 原因: %s", from_model, to_model, reason)

        return {
            "switch_id": record.id,
            "from_model": from_model,
            "to_model": to_model,
            "status": record.status,
            "traffic_percent": traffic_percent,
        }

    def rollback(self, reason: str = "manual_rollback") -> dict:
        """回滚到上一个模型"""
        completed = [
            h for h in reversed(self._history)
            if h.status in ("completed", "canary")
        ]
        if not completed:
            return {"error": "无可回滚记录"}

        last = completed[0]
        result = self.switch(
            last.from_model,
            reason=reason,
            triggered_by="rollback",
        )
        if "error" not in result:
            # 标记原记录
            last.status = "rolled_back"
        return result

    # ----------------------------------------------------------
    # 路由
    # ----------------------------------------------------------

    def get_current_model(self) -> str:
        """获取当前模型"""
        return self._active_model

    def route_request(self) -> str:
        """根据流量分配路由请求"""
        if not self._traffic_splits:
            return self._active_model

        r = __import__("random").random() * 100
        cumulative = 0
        for split in self._traffic_splits:
            if split.is_active:
                cumulative += split.percent
                if r <= cumulative:
                    return split.model_id
        return self._active_model

    def record_request_result(self, model_id: str, success: bool):
        """记录请求结果"""
        self._request_counts[model_id] += 1
        if not success:
            self._error_counts[model_id] += 1
        self._check_auto_rollback(model_id)

    def _check_auto_rollback(self, model_id: str):
        """检查是否需要自动回滚"""
        total = self._request_counts.get(model_id, 0)
        errors = self._error_counts.get(model_id, 0)
        if total >= self.MIN_EVALUATION_TRAFFIC:
            error_rate = errors / total
            if error_rate > self.ERROR_RATE_THRESHOLD:
                logger.warning(
                    "模型 %s 错误率 %.1f%% 超过阈值, 自动回滚",
                    model_id, error_rate * 100,
                )
                self.rollback(reason=f"auto_rollback_error_rate_{error_rate:.1%}")

    # ----------------------------------------------------------
    # 历史
    # ----------------------------------------------------------

    def get_history(self, limit: int = 50) -> list[dict]:
        return [
            {
                "id": h.id,
                "from_model": h.from_model,
                "to_model": h.to_model,
                "reason": h.reason,
                "triggered_by": h.triggered_by,
                "timestamp": h.timestamp,
                "status": h.status,
                "traffic_percent": h.traffic_percent,
            }
            for h in self._history[-limit:]
        ]

    def get_stats(self) -> dict:
        """获取切换统计"""
        return {
            "total_switches": len(self._history),
            "active_model": self._active_model,
            "models_registered": len(self._models),
            "traffic_splits": [
                {"model_id": s.model_id, "percent": s.percent}
                for s in self._traffic_splits
            ],
            "request_counts": dict(self._request_counts),
            "error_counts": dict(self._error_counts),
        }


# 全局实例
_hotswap_service: Optional[ModelHotswapService] = None


def get_hotswap_service() -> ModelHotswapService:
    global _hotswap_service
    if _hotswap_service is None:
        _hotswap_service = ModelHotswapService()
    return _hotswap_service
