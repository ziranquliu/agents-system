"""
限流中间件
基于Redis令牌桶算法实现多级限流: IP / 用户 / 接口 / 全局
Redis 不可用时静默降级(不阻断请求)，避免单点故障影响可用性
"""
import functools
from typing import Optional

from jose import jwt  # python-jose
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from redis import Redis

from app.core.config import settings

_redis_client: Optional[Redis] = None


class RateLimitExceeded(Exception):
    """限流超限（中间件内部使用；由 dispatch 捕获并返回 429 响应）"""

    def __init__(self, window: int, limit: int):
        self.window = window
        self.limit = limit


def _get_redis() -> Optional[Redis]:
    """懒初始化 Redis 客户端（失败返回 None，限流降级为放行；下次调用重试）"""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = Redis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            _redis_client.ping()
        except Exception:
            # 启动时 Redis 可能未就绪：置空，下次调用重新尝试
            _redis_client = None
    return _redis_client


class RateLimitMiddleware(BaseHTTPMiddleware):
    """限流中间件"""

    # 默认限流配置
    DEFAULT_LIMITS = {
        "user": {"requests": 300, "window": 60},     # 每用户300次/分钟（业务操作）
        "ip": {"requests": 600, "window": 60},       # 每IP 600次/分钟（SPA页面加载友好）
        "global": {"requests": 10000, "window": 60}, # 全局10000次/分钟
    }

    def __init__(self, app, redis_client: Redis = None):
        super().__init__(app)
        self.redis = redis_client

    async def dispatch(self, request: Request, call_next):
        # WebSocket 请求透传，不参与 HTTP 限流
        if request.scope.get("type") != "http":
            return await call_next(request)

        # 启动时 Redis 可能未就绪而拿到 None：每次请求尝试懒重连（恢复后自动启用限流）
        if self.redis is None:
            self.redis = _get_redis()

        client_ip = self._get_client_ip(request)
        user_id = self._get_user_id(request)

        try:
            # 接口级限制（登录/注册等敏感接口）
            api_cfg = API_RATE_LIMITS.get(request.url.path)
            if api_cfg:
                await self._check_limit(
                    f"rate:api:{request.url.path}",
                    api_cfg["requests"],
                    api_cfg["window"],
                )

            # IP 级限制
            await self._check_limit(
                f"rate:ip:{client_ip}",
                self.DEFAULT_LIMITS["ip"]["requests"],
                self.DEFAULT_LIMITS["ip"]["window"],
            )

            # 用户级限制
            if user_id:
                await self._check_limit(
                    f"rate:user:{user_id}",
                    self.DEFAULT_LIMITS["user"]["requests"],
                    self.DEFAULT_LIMITS["user"]["window"],
                )
        except RateLimitExceeded as e:
            # 中间件位于异常处理链外，HTTPException 会冒泡；直接构造 429 响应
            return JSONResponse(
                status_code=429,
                content={"detail": f"请求过于频繁，请{e.window}秒后重试"},
                headers={
                    "Retry-After": str(e.window),
                    "X-RateLimit-Limit": str(e.limit),
                    "X-RateLimit-Remaining": "0",
                },
            )
        except Exception:
            # Redis 不可用等异常：降级放行，不阻断服务
            pass

        response = await call_next(request)

        # 限流响应头（真实剩余值）
        try:
            if self.redis:
                key = f"rate:user:{user_id}" if user_id else f"rate:ip:{client_ip}"
                limit = (
                    self.DEFAULT_LIMITS["user"]["requests"]
                    if user_id
                    else self.DEFAULT_LIMITS["ip"]["requests"]
                )
                remaining = self._remaining(key, limit)
                response.headers["X-RateLimit-Limit"] = str(limit)
                response.headers["X-RateLimit-Remaining"] = str(max(remaining, 0))
            else:
                response.headers["X-RateLimit-Remaining"] = "-1"
        except Exception:
            pass

        return response

    async def _check_limit(self, key: str, limit: int, window: int):
        """检查限流（Redis 不可用时直接放行；超限抛 RateLimitExceeded）"""
        if not self.redis:
            return

        current = self.redis.incr(key)
        if current == 1:
            self.redis.expire(key, window)

        if current > limit:
            raise RateLimitExceeded(window, limit)

    def _remaining(self, key: str, limit: int) -> int:
        cur = self.redis.get(key)
        if cur is None:
            return limit
        try:
            return limit - int(cur)
        except (TypeError, ValueError):
            return limit

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP（信任 X-Forwarded-For 第一个值）"""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _get_user_id(self, request: Request) -> Optional[str]:
        """从 Bearer token 解析用户ID（无效 token 返回 None，仅走 IP 级）"""
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return None
        try:
            token = auth.split(" ", 1)[1]
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
            sub = payload.get("sub")
            return str(sub) if sub else None
        except Exception:
            return None


def rate_limit(requests: int = 60, window: int = 60):
    """接口级限流装饰器（Redis 不可用时放行）"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request = kwargs.get("request")
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request:
                redis = _get_redis()
                if redis is not None:
                    try:
                        client_ip = request.client.host if request.client else "unknown"
                        key = f"rate:deco:ip:{client_ip}"
                        current = redis.incr(key)
                        if current == 1:
                            redis.expire(key, window)
                        if current > requests:
                            raise HTTPException(
                                status_code=429,
                                detail="请求过于频繁，请稍后重试",
                                headers={"Retry-After": str(window)},
                            )
                    except HTTPException:
                        raise
                    except Exception:
                        pass

            return await func(*args, **kwargs)
        return wrapper
    return decorator


# 按接口限流配置（敏感接口更严格，但需容忍误操作/重试）
API_RATE_LIMITS = {
    "/api/v1/auth/login": {"requests": 20, "window": 60},    # 登录 20次/分钟
    "/api/v1/auth/register": {"requests": 10, "window": 60}, # 注册 10次/分钟
    "/api/v1/chat/stream": {"requests": 60, "window": 60},   # 对话流式 60次/分钟
    "/api/v1/models": {"requests": 120, "window": 60},       # 模型列表 120次/分钟
}
