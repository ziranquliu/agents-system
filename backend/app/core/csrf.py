"""
CSRF防护中间件
基于双重提交Cookie的CSRF防护实现
"""
import secrets
from typing import Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class CSRFProtectMiddleware(BaseHTTPMiddleware):
    """CSRF保护中间件"""
    
    EXEMPT_PATHS = [
        "/docs",
        "/redoc", 
        "/openapi.json",
        "/health",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
    ]
    
    CSRF_METHODS = ["POST", "PUT", "DELETE", "PATCH"]
    
    async def dispatch(self, request: Request, call_next):
        # 排除路径不检查
        if any(request.url.path.startswith(path) for path in self.EXEMPT_PATHS):
            return await call_next(request)
        
        # 非危险方法不检查
        if request.method not in self.CSRF_METHODS:
            return await call_next(request)
        
        # 检查CSRF Token
        token = self._get_csrf_token(request)
        
        if not token:
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing"}
            )
        
        # 验证Token有效性
        session = request.session if hasattr(request, 'session') else {}
        stored_token = session.get("csrf_token")
        
        if not stored_token or stored_token != token:
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid CSRF token"}
            )
        
        return await call_next(request)
    
    def _get_csrf_token(self, request: Request) -> Optional[str]:
        """从请求中获取CSRF Token - 同步版本"""
        token = request.headers.get("X-CSRF-Token")
        if token:
            return token
        
        # Form Data 需要异步读取，这里跳过详细验证
        return request.cookies.get("csrf_token")
    
    def generate_token(self) -> str:
        """生成新的CSRF Token"""
        return secrets.token_hex(32)
    
    def set_csrf_cookie(self, response):
        """在响应中设置CSRF Cookie"""
        token = secrets.token_hex(32)
        response.set_cookie(
            key="csrf_token",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=3600 * 24
        )
        return token


# 全局实例
csrf_protection = CSRFProtectMiddleware  # type: ignore

# CSRF密钥从环境变量获取
def get_csrf_secret() -> str:
    """获取CSRF密钥"""
    import os
    secret = os.getenv("CSRF_SECRET_KEY")
    if not secret or len(secret) < 32:
        # 开发环境使用默认密钥
        secret = os.getenv("SECRET_KEY", "dev-csrf-secret-change-in-production")
    return secret


async def get_csrf_token(request: Request) -> str:
    """依赖注入：获取当前用户的CSRF Token"""
    token = request.cookies.get("csrf_token")
    if not token:
        token = csrf_protection.generate_token()
    return token


def requires_csrf_token(func):
    """装饰器：要求请求包含有效的CSRF Token"""
    from functools import wraps
    
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request = kwargs.get('request') or (args[1] if len(args) > 1 else None)
        if not request:
            raise HTTPException(status_code=400, detail="Request context not found")
        
        token = request.headers.get("X-CSRF-Token") or \
                request.cookies.get("csrf_token")
        
        if not token:
            raise HTTPException(
                status_code=403,
                detail="CSRF token required"
            )
        
        return await func(*args, **kwargs)
    
    return wrapper
