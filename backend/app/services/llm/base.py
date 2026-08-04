"""
LLM 适配器抽象基类
"""
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional


class ChatMessage:
    """对话消息"""
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


class LLMResult:
    """模型调用结果"""
    def __init__(
        self,
        content: str,
        model: str,
        usage: Optional[dict] = None,
        finish_reason: Optional[str] = None,
    ):
        self.content = content
        self.model = model
        self.usage = usage or {}
        self.finish_reason = finish_reason


class BaseLLMAdapter(ABC):
    """LLM 适配器抽象基类"""

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResult:
        """非流式对话"""
        pass

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """流式对话 - 逐 chunk 返回内容字符串"""
        pass

    async def embeddings(
        self,
        texts: list[str],
        **kwargs,
    ) -> list[list[float]]:
        """文本向量化（可选实现）"""
        raise NotImplementedError("Embeddings not supported by this adapter")

    @property
    def provider_name(self) -> str:
        """提供商名称"""
        return "unknown"

    def validate_config(self) -> list[str]:
        """验证配置，返回错误信息列表"""
        return []
