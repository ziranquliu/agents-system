"""
本地智能体管理系统 - FastAPI 应用入口
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.api.v1.router import api_router
from app.core.exception_handlers import register_exception_handlers


# ============================================================
# 安全响应头中间件
# ============================================================
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """添加安全相关的 HTTP 响应头"""

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

# 安全响应头
app.add_middleware(SecurityHeadersMiddleware)

# 注册统一异常处理
register_exception_handlers(app)

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
    """
    WebSocket 实时对话

    客户端发送 JSON:
    ```json
    {"type": "message", "content": "Hello!", "model": "openai:gpt-4o-mini"}
    ```

    服务端返回流式响应片段:
    ```json
    {"type": "chunk", "content": "Hello! ", "done": false}
    {"type": "chunk", "content": "How can I ", "done": false}
    {"type": "done", "content": "How can I help you today?", "model": "gpt-4o-mini"}
    {"type": "error", "content": "错误信息"}
    ```
    """
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
                    await websocket.send_json({"type": "error", "content": str(e)})

            elif data.get("type") == "clear":
                conversation_messages = []
                await websocket.send_json({"type": "cleared"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "content": f"Connection error: {str(e)}"})
        except Exception:
            pass
