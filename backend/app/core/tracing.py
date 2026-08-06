"""
OpenTelemetry 分布式追踪集成

功能:
- Tracer 初始化（OTLP gRPC/HTTP）
- Span 自动创建与属性填充
- LLM 调用追踪
- Skill/MCP 调用追踪
- 工作流/协作追踪
- 上下文传播（inject/extract）
- 慢调用自动标记
- 错误 Span 记录
"""

import asyncio
import functools
import logging
import time
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ============================================================
# 追踪上下文（不依赖 OTel SDK 也可用的轻量级实现）
# ============================================================


class SpanContext:
    """Span 上下文（当 OTel 不可用时的降级实现）"""

    def __init__(
        self,
        trace_id: str,
        span_id: str,
        parent_span_id: Optional[str] = None,
        operation_name: str = "",
        service_name: str = "agent-system",
    ):
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.operation_name = operation_name
        self.service_name = service_name
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.attributes: dict[str, Any] = {}
        self.events: list[dict[str, Any]] = []
        self.status = "OK"
        self.status_message = ""

    def set_attribute(self, key: str, value: Any):
        self.attributes[key] = value

    def set_status(self, status: str, message: str = ""):
        self.status = status
        self.status_message = message

    def add_event(self, name: str, attributes: Optional[dict[str, Any]] = None):
        self.events.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {},
        })

    def finish(self):
        self.end_time = time.time()

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return (time.time() - self.start_time) * 1000

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation_name": self.operation_name,
            "service_name": self.service_name,
            "start_time": datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat(),
            "duration_ms": round(self.duration_ms, 2),
            "attributes": self.attributes,
            "events": self.events,
            "status": self.status,
            "status_message": self.status_message,
        }


class TraceContext:
    """线程/协程安全的追踪上下文管理"""

    def __init__(self):
        self._current_trace_id: Optional[str] = None
        self._span_stack: list[SpanContext] = []

    @property
    def current_span(self) -> Optional[SpanContext]:
        return self._span_stack[-1] if self._span_stack else None

    @property
    def trace_id(self) -> Optional[str]:
        return self._current_trace_id

    def push_span(self, span: SpanContext):
        self._span_stack.append(span)

    def pop_span(self) -> Optional[SpanContext]:
        return self._span_stack.pop() if self._span_stack else None


# 每个协程的追踪上下文
_trace_contexts: dict[int, TraceContext] = {}


def _get_context_id() -> int:
    """获取当前协程 ID"""
    task = asyncio.current_task()
    return id(task) if task else 0


def get_trace_context() -> TraceContext:
    """获取当前追踪上下文"""
    ctx_id = _get_context_id()
    if ctx_id not in _trace_contexts:
        _trace_contexts[ctx_id] = TraceContext()
    return _trace_contexts[ctx_id]


def _generate_trace_id() -> str:
    import uuid
    return uuid.uuid4().hex


def _generate_span_id() -> str:
    import uuid
    return uuid.uuid4().hex[:16]


# ============================================================
# OTel SDK 封装（可选依赖）
# ============================================================

_otel_available = False
_otel_tracer = None

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.trace import StatusCode, Status
    _otel_available = True
except ImportError:
    logger.info("OpenTelemetry SDK not installed, using built-in tracing")


class Tracer:
    """
    统一 Tracer 接口

    优先使用 OTel SDK，不可用时使用内置轻量级追踪
    """

    def __init__(self, service_name: str = "agent-system", endpoint: Optional[str] = None):
        self.service_name = service_name
        self._otel_tracer = None
        self._spans: list[dict[str, Any]] = []

        if _otel_available:
            try:
                resource = Resource.create({SERVICE_NAME: service_name})
                provider = TracerProvider(resource=resource)

                if endpoint:
                    exporter = OTLPSpanExporter(endpoint=endpoint)
                    processor = BatchSpanProcessor(exporter)
                    provider.add_span_processor(processor)

                trace.set_tracer_provider(provider)
                self._otel_tracer = trace.get_tracer(service_name)
                logger.info(f"OTel tracer initialized for {service_name}")
            except Exception as e:
                logger.warning(f"OTel init failed: {e}, using built-in tracing")
        else:
            logger.info(f"Built-in tracer initialized for {service_name}")

    def start_span(
        self,
        name: str,
        parent: Optional[SpanContext] = None,
        attributes: Optional[dict[str, Any]] = None,
    ) -> "Span":
        """创建新的 Span"""
        if self._otel_tracer:
            otel_span = self._otel_tracer.start_span(name)
            span = Span(otel_span=otel_span, name=name)
        else:
            ctx = get_trace_context()
            parent_span_id = parent.span_id if parent else (
                ctx.current_span.span_id if ctx.current_span else None
            )
            trace_id = parent.trace_id if parent else (
                ctx.trace_id or _generate_trace_id()
            )
            span_ctx = SpanContext(
                trace_id=trace_id,
                span_id=_generate_span_id(),
                parent_span_id=parent_span_id,
                operation_name=name,
                service_name=self.service_name,
            )
            if not ctx.trace_id:
                ctx._current_trace_id = trace_id
            span = Span(builtin_context=span_ctx, name=name)

        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, v)

        return span

    @asynccontextmanager
    async def trace_async(
        self,
        name: str,
        attributes: Optional[dict[str, Any]] = None,
    ):
        """异步追踪上下文管理器"""
        ctx = get_trace_context()
        parent = ctx.current_span
        span = self.start_span(name, parent=parent, attributes=attributes)
        ctx.push_span(span)
        try:
            span.start()
            yield span
            span.set_status("OK")
        except Exception as e:
            span.set_status("ERROR", str(e))
            span.record_exception(e)
            raise
        finally:
            span.finish()
            ctx.pop_span()
            self._record_span(span)

    @contextmanager
    def trace_sync(
        self,
        name: str,
        attributes: Optional[dict[str, Any]] = None,
    ):
        """同步追踪上下文管理器"""
        ctx = get_trace_context()
        parent = ctx.current_span
        span = self.start_span(name, parent=parent, attributes=attributes)
        ctx.push_span(span)
        try:
            span.start()
            yield span
            span.set_status("OK")
        except Exception as e:
            span.set_status("ERROR", str(e))
            span.record_exception(e)
            raise
        finally:
            span.finish()
            ctx.pop_span()
            self._record_span(span)

    def _record_span(self, span: Span):
        """记录 Span 到内存（用于查询和导出）"""
        span_dict = span.to_dict()
        self._spans.append(span_dict)
        # 保留最近 10000 条
        if len(self._spans) > 10000:
            self._spans = self._spans[-5000:]

    def get_recent_spans(self, limit: int = 100) -> list[dict[str, Any]]:
        """获取最近的 Span"""
        return self._spans[-limit:]

    def get_trace(self, trace_id: str) -> list[dict[str, Any]]:
        """获取指定 trace 的所有 Span"""
        return [s for s in self._spans if s.get("trace_id") == trace_id]


class Span:
    """统一 Span 接口"""

    def __init__(
        self,
        otel_span=None,
        builtin_context: Optional[SpanContext] = None,
        name: str = "",
    ):
        self._otel_span = otel_span
        self._builtin = builtin_context
        self.name = name
        self._start_time: Optional[float] = None

    def start(self):
        self._start_time = time.time()

    def set_attribute(self, key: str, value: Any):
        if self._otel_span:
            self._otel_span.set_attribute(key, str(value))
        elif self._builtin:
            self._builtin.set_attribute(key, value)

    def set_status(self, status: str, message: str = ""):
        if self._otel_span:
            from opentelemetry.trace import StatusCode, Status
            if status == "OK":
                self._otel_span.set_status(Status(StatusCode.OK))
            else:
                self._otel_span.set_status(Status(StatusCode.ERROR, message))
        elif self._builtin:
            self._builtin.set_status(status, message)

    def add_event(self, name: str, attributes: Optional[dict[str, Any]] = None):
        if self._otel_span:
            self._otel_span.add_event(name, attributes=attributes or {})
        elif self._builtin:
            self._builtin.add_event(name, attributes)

    def record_exception(self, exception: Exception):
        """记录异常到 Span"""
        attrs = {
            "exception.type": type(exception).__name__,
            "exception.message": str(exception),
        }
        self.add_event("exception", attrs)

    def finish(self):
        if self._otel_span:
            self._otel_span.end()
        elif self._builtin:
            self._builtin.finish()

    def to_dict(self) -> dict[str, Any]:
        if self._otel_span:
            # 从 OTel span 导出
            return {
                "name": self.name,
                "trace_id": getattr(self._otel_span.get_span_context(), "trace_id", "unknown"),
                "span_id": getattr(self._otel_span.get_span_context(), "span_id", "unknown"),
            }
        elif self._builtin:
            return self._builtin.to_dict()
        return {"name": self.name}

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.set_status("ERROR", str(exc_val))
            self.record_exception(exc_val)
        else:
            self.set_status("OK")
        self.finish()
        return False

    async def __aenter__(self):
        self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.set_status("ERROR", str(exc_val))
            self.record_exception(exc_val)
        else:
            self.set_status("OK")
        self.finish()
        return False


# ============================================================
# 全局 Tracer 实例
# ============================================================

_global_tracer: Optional[Tracer] = None


def get_tracer() -> Tracer:
    """获取全局 Tracer"""
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = Tracer()
    return _global_tracer


def init_tracer(service_name: str = "agent-system", endpoint: Optional[str] = None) -> Tracer:
    """初始化全局 Tracer"""
    global _global_tracer
    _global_tracer = Tracer(service_name=service_name, endpoint=endpoint)
    return _global_tracer


# ============================================================
# 预定义追踪装饰器
# ============================================================


def trace_llm_call(provider: str, model: str):
    """追踪 LLM 调用的装饰器"""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                tracer = get_tracer()
                async with tracer.trace_async(
                    f"llm.{provider}.{model}",
                    attributes={
                        "llm.provider": provider,
                        "llm.model": model,
                        "llm.operation": func.__name__,
                    },
                ) as span:
                    result = await func(*args, **kwargs)
                    if isinstance(result, dict):
                        if "usage" in result:
                            usage = result["usage"]
                            span.set_attribute("llm.input_tokens", usage.get("prompt_tokens", 0))
                            span.set_attribute("llm.output_tokens", usage.get("completion_tokens", 0))
                            span.set_attribute("llm.total_tokens", usage.get("total_tokens", 0))
                        if "duration_ms" in result:
                            span.set_attribute("llm.duration_ms", result["duration_ms"])
                    return result
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                tracer = get_tracer()
                with tracer.trace_sync(
                    f"llm.{provider}.{model}",
                    attributes={
                        "llm.provider": provider,
                        "llm.model": model,
                        "llm.operation": func.__name__,
                    },
                ) as span:
                    result = func(*args, **kwargs)
                    return result
            return sync_wrapper
    return decorator


def trace_skill(skill_name: str, skill_version: str = "latest"):
    """追踪 Skill 调用的装饰器"""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                tracer = get_tracer()
                async with tracer.trace_async(
                    f"skill.{skill_name}",
                    attributes={
                        "skill.name": skill_name,
                        "skill.version": skill_version,
                    },
                ) as span:
                    start = time.time()
                    result = await func(*args, **kwargs)
                    duration = (time.time() - start) * 1000
                    span.set_attribute("skill.duration_ms", round(duration, 2))
                    return result
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                tracer = get_tracer()
                with tracer.trace_sync(
                    f"skill.{skill_name}",
                    attributes={
                        "skill.name": skill_name,
                        "skill.version": skill_version,
                    },
                ) as span:
                    result = func(*args, **kwargs)
                    return result
            return sync_wrapper
    return decorator


def trace_mcp(mcp_server: str, operation: str = "call"):
    """追踪 MCP 调用的装饰器"""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                tracer = get_tracer()
                async with tracer.trace_async(
                    f"mcp.{mcp_server}.{operation}",
                    attributes={
                        "mcp.server": mcp_server,
                        "mcp.operation": operation,
                    },
                ) as span:
                    result = await func(*args, **kwargs)
                    return result
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                tracer = get_tracer()
                with tracer.trace_sync(
                    f"mcp.{mcp_server}.{operation}",
                    attributes={
                        "mcp.server": mcp_server,
                        "mcp.operation": operation,
                    },
                ) as span:
                    result = func(*args, **kwargs)
                    return result
            return sync_wrapper
    return decorator


def trace_workflow(workflow_id: str, workflow_name: str = ""):
    """追踪工作流执行的装饰器"""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                tracer = get_tracer()
                async with tracer.trace_async(
                    f"workflow.{workflow_name or workflow_id}",
                    attributes={
                        "workflow.id": workflow_id,
                        "workflow.name": workflow_name,
                    },
                ) as span:
                    result = await func(*args, **kwargs)
                    return result
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                tracer = get_tracer()
                with tracer.trace_sync(
                    f"workflow.{workflow_name or workflow_id}",
                    attributes={
                        "workflow.id": workflow_id,
                        "workflow.name": workflow_name,
                    },
                ) as span:
                    result = func(*args, **kwargs)
                    return result
            return sync_wrapper
    return decorator
