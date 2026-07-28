"""
对话补全接口 - 支持 SSE 流式响应
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.llm import create_adapter, list_supported_providers
from app.services.model_service import get_template

router = APIRouter()


class ChatMessage(BaseModel):
    role: str = Field(..., pattern=r"^(system|user|assistant|tool)$")
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = Field(default="gpt-4o-mini", description="模型名称或模板ID")
    messages: list[ChatMessage]
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=128000)
    stream: bool = Field(default=False, description="是否使用 SSE 流式响应")


class ChatCompletionResponse(BaseModel):
    id: str
    model: str
    choices: list[dict]
    usage: dict
    created: int


class StreamChunk(BaseModel):
    """SSE 流式数据块"""
    id: str
    model: str
    choices: list[dict]


@router.post("/completions")
async def chat_completions(
    data: ChatCompletionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    对话补全接口

    支持:
    - 非流式: POST /api/v1/chat/completions
    - 流式 (SSE): POST /api/v1/chat/completions?stream=true
    """
    # 构建适配器配置
    # 支持通过 model 参数直接指定 provider:model_name 格式
    adapter_config = _resolve_model_config(data.model)

    try:
        adapter = create_adapter(
            adapter_config["provider"],
            adapter_config,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    messages_dict = [m.model_dump() for m in data.messages]

    # 流式响应
    if data.stream:
        return _stream_response(adapter, messages_dict, data)

    # 非流式响应
    try:
        result = await adapter.chat(
            messages=messages_dict,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Model request failed: {str(e)}")

    resp_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    return ChatCompletionResponse(
        id=resp_id,
        model=result.model,
        choices=[{
            "index": 0,
            "message": {"role": "assistant", "content": result.content},
            "finish_reason": result.finish_reason or "stop",
        }],
        usage=result.usage or {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
        created=int(datetime.now(timezone.utc).timestamp()),
    )


def _resolve_model_config(model_str: str) -> dict:
    """
    解析模型配置:
    1. 如果 model_str 包含 ':' 则视为 provider:model_name
    2. 否则作为 model_name 使用默认配置
    """
    if ":" in model_str:
        parts = model_str.split(":", 1)
        return {
            "provider": parts[0],
            "model_name": parts[1],
            "endpoint": "",
            "api_key": "",
        }
    return {
        "provider": "openai",
        "model_name": model_str,
        "endpoint": "",
        "api_key": "",
    }


async def _stream_response(adapter, messages: list[dict], data: ChatCompletionRequest):
    """生成 SSE 流式响应"""
    resp_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    async def generate():
        try:
            async for chunk in adapter.chat_stream(
                messages=messages,
                temperature=data.temperature,
                max_tokens=data.max_tokens,
            ):
                payload = {
                    "id": resp_id,
                    "model": adapter.config.get("model_name", "unknown"),
                    "choices": [{
                        "index": 0,
                        "delta": {"content": chunk},
                        "finish_reason": None,
                    }],
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            # 结束标记
            yield f"data: {json.dumps({'id': resp_id, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/embeddings")
async def create_embeddings(
    input_texts: list[str] = Field(..., min_length=1, max_length=100),
    model: str = Query("text-embedding-3-small"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """文本向量化"""
    adapter_config = {
        "provider": "openai",
        "model_name": model,
        "embedding_model": model,
        "endpoint": "",
        "api_key": "",
    }
    try:
        adapter = create_adapter("openai", adapter_config)
        embeddings = await adapter.embeddings(input_texts)
    except NotImplementedError:
        raise HTTPException(400, "Embeddings not supported by this provider")
    except Exception as e:
        raise HTTPException(502, f"Embeddings request failed: {str(e)}")

    return {
        "model": model,
        "data": [
            {"index": i, "embedding": emb}
            for i, emb in enumerate(embeddings)
        ],
        "usage": {"total_tokens": 0},
    }
