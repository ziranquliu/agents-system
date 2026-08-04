"""
本地 AI 服务发现服务
扫描 Ollama、OpenAI-compatible 端点等本地运行的 AI 服务
"""
import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent


# 默认扫描的目标
DEFAULT_TARGETS = [
    {"name": "Ollama (本地)", "url": "http://localhost:11434", "type": "ollama"},
]

# Ollama 模型 → Provider 映射
OLLAMA_MODEL_PROVIDER_MAP = {
    "qwen": "ollama",
    "llama": "ollama",
    "mistral": "ollama",
    "deepseek": "ollama",
    "gemma": "ollama",
    "phi": "ollama",
    "yi": "ollama",
    "codellama": "ollama",
}

OLLAMA_AGENT_CONFIGS = {
    "聊天对话": {"temperature": 0.7, "system_prompt": "你是一个友好的对话助手，用中文回答用户的问题。"},
    "代码生成": {"temperature": 0.3, "system_prompt": "你是一个专业的编程助手，精通多种编程语言。"},
    "内容创作": {"temperature": 0.8, "system_prompt": "你是一个专业的内容创作助手，擅长各类文章和文案的撰写。"},
}


async def scan_ollama(endpoint: str = "http://localhost:11434") -> list[dict]:
    """扫描 Ollama 实例，获取可用模型列表"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{endpoint}/api/tags")
            if resp.status_code != 200:
                return []
            data = resp.json()
            models = data.get("models", [])
            result = []
            for m in models:
                name = m.get("name", "unknown")
                # 提取模型家族名称（: 前的部分）
                family = name.split(":")[0] if ":" in name else name
                provider = OLLAMA_MODEL_PROVIDER_MAP.get(family.split("-")[0], "ollama")
                result.append({
                    "source": "ollama",
                    "source_name": f"Ollama ({endpoint})",
                    "model_name": name,
                    "provider": provider,
                    "size": m.get("size", 0),
                    "modified_at": m.get("modified_at", ""),
                    "endpoint": endpoint,
                })
            return result
    except Exception:
        return []


async def scan_openai_compatible(endpoint: str, api_key: str = "") -> list[dict]:
    """扫描 OpenAI-compatible 端点的可用模型"""
    try:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{endpoint}/models", headers=headers)
            if resp.status_code != 200:
                return []
            data = resp.json()
            models = data.get("data", data.get("models", []))
            result = []
            for m in models:
                name = m.get("id", m.get("name", "unknown"))
                result.append({
                    "source": "openai-compatible",
                    "source_name": f"OpenAI兼容 ({endpoint})",
                    "model_name": name,
                    "provider": "openai",
                    "endpoint": endpoint,
                })
            return result
    except Exception:
        return []


async def discover_agents(db: AsyncSession) -> list[dict]:
    """执行全面扫描，返回所有发现的可用 Agent 信息"""
    discovered = []

    # 1. 扫描 Ollama
    for target in DEFAULT_TARGETS:
        if target["type"] == "ollama":
            models = await scan_ollama(target["url"])
            discovered.extend(models)

    # 2. 从数据库中读取已注册的自定义端点
    # TODO: 后续可以从配置表读取

    return discovered


async def register_discovered_agent(
    db: AsyncSession,
    model_name: str,
    provider: str,
    endpoint: str,
    user_id: str,
    workspace_id: str = "ws_personal",
) -> Agent:
    """将发现的模型注册为一个 Agent"""
    # 判断模型类型，选择角色配置
    family = model_name.split(":")[0] if ":" in model_name else model_name
    family_base = family.split("-")[0]

    if "code" in family_base.lower() or "coder" in family_base.lower():
        role = "代码生成"
    elif "chat" in family_base.lower() or "qwen" in family_base.lower():
        role = "聊天对话"
    else:
        role = "内容创作"

    config = OLLAMA_AGENT_CONFIGS.get(role, OLLAMA_AGENT_CONFIGS["聊天对话"])

    agent_id = f"agent_{model_name.replace(':', '_').replace('.', '_')}_{uuid.uuid4().hex[:6]}"

    agent = Agent(
        id=agent_id,
        name=f"{model_name} ({provider})",
        description=f"从本地发现的 {provider} 模型: {model_name}",
        system_prompt=config["system_prompt"],
        welcome_message=f"你好！我是 {model_name} 助手，有什么可以帮助你的吗？",
        status="draft",
        model_provider=provider,
        model_name=model_name,
        temperature=config["temperature"],
        max_tokens=4096,
        context_window=8192,
        workspace_id=workspace_id,
        created_by=user_id,
    )
    db.add(agent)
    await db.flush()
    return agent
