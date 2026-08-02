"""
OpenAI 兼容 API 适配器 - 支持任何 OpenAI 兼容接口
（包括 OpenAI、DeepSeek、GLM、通义千问、Ollama 等）
"""
from typing import AsyncGenerator, Optional

import httpx

from app.services.llm.base import BaseLLMAdapter, LLMResult


class OpenAICompatibleAdapter(BaseLLMAdapter):
    """OpenAI 兼容 API 适配器"""

    @property
    def provider_name(self) -> str:
        return self.config.get("provider", "openai_compatible")

    def _get_endpoint(self) -> str:
        return self.config.get("endpoint", "https://api.openai.com/v1")

    def _get_api_key(self) -> str:
        return self.config.get("api_key", "")

    def _get_model(self) -> str:
        return self.config.get("model_name", "gpt-4o-mini")

    def _get_client_headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
        }
        api_key = self._get_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def validate_config(self) -> list[str]:
        errors = []
        if not self._get_endpoint():
            errors.append("endpoint is required")
        if not self._get_model():
            errors.append("model_name is required")
        return errors

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResult:
        endpoint = f"{self._get_endpoint()}/chat/completions"
        payload = {
            "model": self._get_model(),
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                endpoint,
                json=payload,
                headers=self._get_client_headers(),
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        return LLMResult(
            content=choice["message"]["content"],
            model=data.get("model", self._get_model()),
            usage=data.get("usage"),
            finish_reason=choice.get("finish_reason"),
        )

    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        endpoint = f"{self._get_endpoint()}/chat/completions"
        payload = {
            "model": self._get_model(),
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST",
                endpoint,
                json=payload,
                headers=self._get_client_headers(),
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    chunk = line[6:].strip()
                    if chunk == "[DONE]":
                        break
                    import json
                    try:
                        data = json.loads(chunk)
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    async def embeddings(
        self,
        texts: list[str],
        **kwargs,
    ) -> list[list[float]]:
        endpoint = f"{self._get_endpoint()}/embeddings"
        payload = {
            "model": self.config.get("embedding_model", "text-embedding-3-small"),
            "input": texts,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                endpoint,
                json=payload,
                headers=self._get_client_headers(),
            )
            resp.raise_for_status()
            data = resp.json()

        return [item["embedding"] for item in data["data"]]
