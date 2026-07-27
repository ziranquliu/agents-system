"""
本地智能体管理系统 - FastAPI 应用入口
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.router import api_router
from app.core.exception_handlers import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理"""
    try:
        from app.db.session import check_db_connection
        await check_db_connection()
        print(f"Server started: {settings.PROJECT_NAME} v{settings.PROJECT_VERSION}")
    except Exception as e:
        print(f"Startup error: {e}")
        raise
    yield
    from app.db.session import close_db_connections
    await close_db_connections()
    print("Server shutdown complete")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="一站式本地化智能体管理平台 API",
    lifespan=lifespan,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册统一异常处理
register_exception_handlers(app)

# 注册路由
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "version": settings.PROJECT_VERSION}
