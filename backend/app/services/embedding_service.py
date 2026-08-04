"""
Embedding 服务 - 向量化工具与余弦相似度计算

- get_embeddings(): 调用 LLM 适配器的 embeddings 方法生成向量
- cosine_similarity(): 向量余弦相似度（Python 内计算，知识库规模不大足够用）
- 无 embedding 配置/调用失败时优雅降级（返回 None），调用方回退关键词检索
"""
import json
import logging
import math
from typing import Optional

from app.services.llm import create_adapter
from app.core.encryption import decrypt_secret
from app.models.agent import ModelConfigTemplate

logger = logging.getLogger("embedding")

# 默认 embedding 模型（无模板配置时使用）
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


def json_loads_vector(raw: Optional[str]) -> Optional[list[float]]:
    """解析 JSON 字符串为向量，失败返回 None"""
    if not raw:
        return None
    try:
        vec = json.loads(raw)
        if isinstance(vec, list) and vec and all(isinstance(x, (int, float)) for x in vec):
            return [float(x) for x in vec]
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return None


def serialize_vector(vec: list[float]) -> str:
    """向量序列化为 JSON 字符串（持久化用）"""
    return json.dumps([float(x) for x in vec], ensure_ascii=False)


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """计算两个向量的余弦相似度（归一化后点积）"""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    norm_a = math.sqrt(sum(x * x for x in vec_a))
    norm_b = math.sqrt(sum(x * x for x in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    return dot / (norm_a * norm_b)


def build_embedding_adapter_config(
    template: Optional["ModelConfigTemplate"] = None,
) -> dict:
    """构建 embedding 适配器配置。

    优先使用模板中的 endpoint/api_key/embedding_model；
    无模板时使用空配置 + 默认模型（调用方需自行处理失败降级）。
    """
    cfg: dict = {}
    if template is not None:
        try:
            template_cfg = json.loads(template.config) if template.config else {}
        except (json.JSONDecodeError, TypeError):
            template_cfg = {}
        cfg = {
            "provider": template.provider or "openai",
            "model_name": template.model or DEFAULT_EMBEDDING_MODEL,
            "embedding_model": template_cfg.get("embedding_model") or DEFAULT_EMBEDDING_MODEL,
            "endpoint": template_cfg.get("endpoint", ""),
            "api_key": decrypt_secret(template_cfg.get("api_key", "")),
        }
    else:
        cfg = {
            "provider": "openai",
            "model_name": DEFAULT_EMBEDDING_MODEL,
            "embedding_model": DEFAULT_EMBEDDING_MODEL,
            "endpoint": "",
            "api_key": "",
        }
    return cfg


async def get_embeddings(
    texts: list[str],
    adapter_config: Optional[dict] = None,
) -> Optional[list[list[float]]]:
    """批量文本向量化。

    参数:
        texts: 待向量化文本列表
        adapter_config: embedding 适配器配置；None 时使用默认（openai + text-embedding-3-small）

    返回:
        向量列表（与 texts 一一对应）；调用失败返回 None（调用方降级）
    """
    if not texts:
        return []
    cfg = adapter_config or build_embedding_adapter_config()
    provider = cfg.get("provider", "openai")
    try:
        adapter = create_adapter(provider, cfg)
        embeddings = await adapter.embeddings(texts)
        if not embeddings:
            logger.warning("[embedding] adapter returned empty embeddings")
            return None
        return [list(map(float, e)) for e in embeddings]
    except NotImplementedError:
        logger.warning("[embedding] provider %s does not support embeddings", provider)
        return None
    except Exception as e:
        logger.warning("[embedding] get_embeddings failed: %s", e)
        return None
