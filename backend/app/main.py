"""
本地智能体管理系统 - FastAPI 应用入口
"""
import logging
import sys

logger = logging.getLogger(__name__)

# Force UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from contextlib import asynccontextmanager
from typing import AsyncGenerator
import asyncio
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.api.v1.router import api_router
from app.core.exception_handlers import register_exception_handlers
from app.core.error_handler import custom_exception_handler


# ============================================================
# 安全响应头中间件
# ============================================================
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """添加安全相关的HTTP 响应头"""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        # 基本安全头
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # HSTS（仅生产环境启用）
        if settings.SECURITY_HSTS_ENABLED and settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # 移除 Server 头
        if "server" in response.headers:
            del response.headers["server"]
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理"""
    try:
        from app.db.session import check_db_connection
        # 使用应用 SECRET_KEY 初始化敏感字段加密（B3.1）
        from app.core.encryption import EncryptionHelper
        EncryptionHelper.initialize(settings.SECRET_KEY or None)
        await check_db_connection()
        print(f"[INFO] Server started: {settings.PROJECT_NAME} v{settings.PROJECT_VERSION}")
    except Exception as e:
        print(f"[WARN] Startup warning: {e}")
    # 启动全局定时调度器
    try:
        from app.core.scheduler import start_scheduler
        sched = start_scheduler()
        print(f"[INFO] Scheduler started with {len(sched.get_jobs())} jobs")
    except Exception as e:
        print(f"[WARN] Scheduler start failed (non-fatal): {e}")
    yield
    from app.core.scheduler import stop_scheduler
    stop_scheduler()
    from app.db.session import close_db_connections
    await close_db_connections()
    print("[INFO] Server shutdown complete")


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

# 安全响应头
app.add_middleware(SecurityHeadersMiddleware)

# 限流中间件（按配置启用；Redis 不可用时自动降级为放行）
from app.core.ratelimit import RateLimitMiddleware, _get_redis

if settings.RATE_LIMIT_ENABLED:
    app.add_middleware(RateLimitMiddleware, redis_client=_get_redis())

# 注册统一异常处理
register_exception_handlers(app)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return await custom_exception_handler(request, exc)

# 注册路由（api_router 已包含 /api/v1 前缀）
app.include_router(api_router)


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "version": settings.PROJECT_VERSION}


# ============================================================
# WebSocket - 实时对话
# ============================================================
@app.websocket("/ws/chat/{conversation_id}")
async def websocket_chat(websocket: WebSocket, conversation_id: str):
    """WebSocket 实时对话"""
    # 鉴权：从 query 参数取 token（WebSocket 无法带 Header）
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=4401, reason="Missing token")
        return
    try:
        from app.services.auth_service import decode_access_token
        from sqlalchemy import select as sa_select
        from app.db.session import async_session_factory
        from app.models.user import User

        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4401, reason="Invalid token")
            return
        async with async_session_factory() as db:
            res = await db.execute(sa_select(User).where(User.id == user_id))
            user = res.scalar_one_or_none()
        if user is None or not user.is_active:
            await websocket.close(code=4401, reason="User not found or inactive")
            return
    except Exception:
        await websocket.close(code=4401, reason="Invalid token")
        return

    await websocket.accept()
    conversation_messages = []

    try:
        while True:
            raw = await websocket.receive_text()
            import json
            data = json.loads(raw)

            if data.get("type") == "message":
                content = data.get("content", "")
                model_str = data.get("model", "openai:gpt-4o-mini")

                conversation_messages.append({"role": "user", "content": content})

                # 解析模型配置
                from app.services.llm import create_adapter
                if ":" in model_str:
                    provider, model_name = model_str.split(":", 1)
                else:
                    provider, model_name = "openai", model_str

                adapter_config = {
                    "provider": provider,
                    "model_name": model_name,
                    "endpoint": "",
                    "api_key": "",
                }

                try:
                    adapter = create_adapter(provider, adapter_config)
                    full_response = ""

                    async for chunk in adapter.chat_stream(
                        messages=conversation_messages,
                        temperature=data.get("temperature", 0.7),
                    ):
                        full_response += chunk
                        await websocket.send_json({
                            "type": "chunk",
                            "content": chunk,
                            "done": False,
                        })

                    conversation_messages.append({"role": "assistant", "content": full_response})
                    await websocket.send_json({
                        "type": "done",
                        "content": full_response,
                        "model": model_name,
                    })

                except Exception as e:
                    logger.warning("WebSocket LLM error: %s", e)
                    await websocket.send_json({"type": "error", "content": "模型调用失败，请重试"})

            elif data.get("type") == "clear":
                conversation_messages = []
                await websocket.send_json({"type": "cleared"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            logger.warning("WebSocket error: %s", e)
            await websocket.send_json({"type": "error", "content": "连接异常，请重试"})
        except Exception:
            pass


# ============================================================
# WebSocket - 实时监控（B2.6）
# ============================================================
_monitor_clients: set = set()
_monitor_lock = asyncio.Lock()


async def _build_monitor_snapshot() -> dict:
    """构建监控快照：健康评分 / QPS / Token / 资源占用"""
    from app.db.session import async_session_factory
    from app.services.monitoring_service import MonitoringService
    from app.services.token_service import TokenService

    async with async_session_factory() as db:
        monitor = MonitoringService(db)
        latest = await monitor.get_latest_metrics()
        agents = list(latest.values())

        health_scores = [a.get("health_score") for a in agents if a.get("health_score") is not None]
        qps_values = [a.get("qps") for a in agents if a.get("qps") is not None]
        cpu_values = [a.get("cpu_percent") for a in agents if a.get("cpu_percent") is not None]
        mem_values = [a.get("memory_mb") for a in agents if a.get("memory_mb") is not None]

        token_stats = await TokenService.get_stats(db, days=1)

        snapshot = {
            "type": "monitor_snapshot",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "health_score": round(sum(health_scores) / len(health_scores), 2) if health_scores else 0,
            "qps": round(sum(qps_values), 2) if qps_values else 0,
            "token": {
                "total_tokens": token_stats.get("total_tokens", 0),
                "total_cost": round(token_stats.get("total_cost", 0), 4),
                "total_records": token_stats.get("total_records", 0),
                "cached_tokens": token_stats.get("cached_tokens", 0),
                "compressed_tokens": token_stats.get("compressed_tokens", 0),
            },
            "resources": {
                "avg_cpu": round(sum(cpu_values) / len(cpu_values), 2) if cpu_values else 0,
                "avg_memory_mb": round(sum(mem_values) / len(mem_values), 2) if mem_values else 0,
                "agent_count": len(agents),
            },
            "agents": agents,
        }
        return snapshot


async def _monitor_broadcast_loop():
    """后台广播任务：每 5s 向所有已连接客户端推送监控快照"""
    while True:
        try:
            if _monitor_clients:
                snapshot = await _build_monitor_snapshot()
                disconnected = []
                for ws in list(_monitor_clients):
                    try:
                        await ws.send_json(snapshot)
                    except Exception:
                        disconnected.append(ws)
                for ws in disconnected:
                    _monitor_clients.discard(ws)
        except Exception as e:
            logger.warning("Monitor broadcast error: %s", e)
        await asyncio.sleep(5)


@app.websocket("/ws/monitor")
async def websocket_monitor(websocket: WebSocket):
    """WebSocket 实时监控：连接后每 5s 推送一次监控快照"""
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=4401, reason="Missing token")
        return
    try:
        from app.services.auth_service import decode_access_token
        from sqlalchemy import select as sa_select
        from app.db.session import async_session_factory
        from app.models.user import User

        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=4401, reason="Invalid token")
            return
        async with async_session_factory() as db:
            res = await db.execute(sa_select(User).where(User.id == user_id))
            user = res.scalar_one_or_none()
        if user is None or not user.is_active:
            await websocket.close(code=4401, reason="User not found or inactive")
            return
    except Exception:
        await websocket.close(code=4401, reason="Invalid token")
        return

    await websocket.accept()
    _monitor_clients.add(websocket)
    logger.info("Monitor client connected, total=%d", len(_monitor_clients))

    # 首次连接启动后台广播任务
    async def _start_broadcaster():
        if not any(t.get_name() == "monitor_broadcast" for t in asyncio.all_tasks()):
            await asyncio.create_task(_monitor_broadcast_loop(), name="monitor_broadcast")

    try:
        await _start_broadcaster()
        while True:
            # 等待客户端消息（心跳/断开检测）
            await websocket.receive_text()
    except WebSocketDisconnect:
        _monitor_clients.discard(websocket)
        logger.info("Monitor client disconnected, total=%d", len(_monitor_clients))
        # 如果没有客户端了，停止广播任务
        if not _monitor_clients:
            for t in asyncio.all_tasks():
                if t.get_name() == "monitor_broadcast":
                    t.cancel()
                    break
    except WebSocketDisconnect:
        pass
    finally:
        _monitor_clients.discard(websocket)
        print(f"[monitor] client disconnected, total={len(_monitor_clients)}")
