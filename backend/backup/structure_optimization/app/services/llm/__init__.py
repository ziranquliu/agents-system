"""
LLM 适配器工厂 - 根据 provider 返回对应适配器实例
"""
from typing import Optional
from app.services.llm.base import BaseLLMAdapter
from app.services.llm.openai_compatible import OpenAICompatibleAdapter


_adapter_registry: dict[str, type[BaseLLMAdapter]] = {
    "openai": OpenAICompatibleAdapter,
    "openai_compatible": OpenAICompatibleAdapter,
    "ollama": OpenAICompatibleAdapter,
    "deepseek": OpenAICompatibleAdapter,
    "openrouter": OpenAICompatibleAdapter,
    "glm": OpenAICompatibleAdapter,
    "qwen": OpenAICompatibleAdapter,
}


def register_adapter(provider: str, adapter_class: type[BaseLLMAdapter]):
    """注册自定义适配器"""
    _adapter_registry[provider.lower()] = adapter_class


def create_adapter(
    provider: str,
    config: dict,
) -> Optional[BaseLLMAdapter]:
    """
    创建 LLM 适配器实例

    Args:
        provider: 提供商名称 (openai, ollama, deepseek, glm, qwen, etc.)
        config: 配置字典，包含 endpoint, api_key, model_name 等

    Returns:
        BaseLLMAdapter 实例，如果 provider 不支持则返回 None
    """
    provider_lower = provider.lower()
    adapter_class = _adapter_registry.get(provider_lower)

    if not adapter_class:
        # 尝试作为通用 OpenAI 兼容 API 处理
        adapter_class = OpenAICompatibleAdapter

    adapter = adapter_class(config)
    errors = adapter.validate_config()
    if errors:
        raise ValueError(f"Adapter config validation failed for {provider}: {', '.join(errors)}")

    return adapter


def list_supported_providers() -> list[str]:
    """列出所有支持的提供商"""
    return list(_adapter_registry.keys())
