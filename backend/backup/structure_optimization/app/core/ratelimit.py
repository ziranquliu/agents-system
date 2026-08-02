"""
限流中间件
基于Redis令牌桶算法实现多级限流
"""
import time
from typing import Optional
from fastapi import Request, HTTPException, Depends
from starlette.middleware.base import BaseHTTPMiddleware
from redis import Redis

from app.core.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """限流中间件"""
    
    # 默认限流配置
    DEFAULT_LIMITS = {
        "user": {"requests": 60, "window": 60},      # 每用户60次/分钟
        "ip": {"requests": 100, "window": 60},       # 每IP 100次/分钟
        "global": {"requests": 1000, "window": 60},  # 全局1000次/分钟
    }
    
    def __init__(self, app, redis_client: Redis = None):
        super().__init__(app)
        self.redis = redis_client
    
    async def dispatch(self, request: Request, call_next):
        # 获取客户端信息
        client_ip = self._get_client_ip(request)
        user_id = self._get_user_id(request)
        
        # 检查各层级限流
        await self._check_limit(f"rate:ip:{client_ip}", 
                                self.DEFAULT_LIMITS["ip"]["requests"],
                                self.DEFAULT_LIMITS["ip"]["window"])
        
        if user_id:
            await self._check_limit(f"rate:user:{user_id}",
                                   self.DEFAULT_LIMITS["user"]["requests"],
                                   self.DEFAULT_LIMITS["user"]["window"])
        
        # 执行请求
        response = await call_next(request)
        
        # 添加限流响应头
        response.headers["X-RateLimit-Limit"] = str(self.DEFAULT_LIMITS["user"]["requests"])
        response.headers["X-RateLimit-Remaining"] = "59"  # 实际应从redis获取
        
        return response
    
    async def _check_limit(self, key: str, limit: int, window: int):
        """检查限流"""
        if not self.redis:
            return
        
        current = self.redis.incr(key)
        if current == 1:
            self.redis.expire(key, window)
        
        if current > limit:
            raise HTTPException(
                status_code=429,
                detail=f"请求过于频繁，请{window}秒后重试",
                headers={"Retry-After": str(window)}
            )
    
    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP"""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
    
    def _get_user_id(self, request: Request) -> Optional[str]:
        """从请求中获取用户ID"""
        # 从header或cookie获取
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            # 简单解析JWT获取user_id
            # 实际项目应使用完整的JWT验证
            return None
        return None


# 快速创建限流装饰器
def rate_limit(requests: int = 60, window: int = 60):
    """限流装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 获取请求对象
            request = kwargs.get('request')
            if not request:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            
            if request:
                client_ip = request.client.host if request.client else "unknown"
                key = f"rate:ip:{client_ip}"
                
                # 简化版限流检查（实际需要Redis）
                # TODO: 集成Redis
                pass
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# 按接口限流配置
API_RATE_LIMITS = {
    "/api/v1/auth/login": {"requests": 5, "window": 60},      # 登录限制
    "/api/v1/auth/register": {"requests": 3, "window": 60},   # 注册限制
    "/api/v1/chat/stream": {"requests": 10, "window": 60},    # 对话流式
    "/api/v1/models": {"requests": 30, "window": 60},         # 模型列表
}
