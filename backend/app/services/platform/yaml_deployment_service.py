"""
YAML 自动部署 — 读取 YAML 配置文件,自动创建/更新 Agent、Skill、MCP

YAML 格式示例:
```yaml
apiVersion: agent/v1
kind: Agent
metadata:
  name: my-agent
  labels:
    env: production
    team: ai
spec:
  description: "我的智能体"
  system_prompt: "你是一个有用的助手"
  model_provider: openai
  model_name: gpt-4o
  temperature: 0.7
  max_tokens: 4096
  status: running
  skills:
    - skill-name-1
    - skill-name-2
  mcp_servers:
    - mcp-name-1
```

支持的 kind: Agent, Skill, MCP, Collaboration
"""
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)


class YAMLParseError(Exception):
    pass


class YAMLDeploymentResult:
    def __init__(self):
        self.created: List[dict] = []
        self.updated: List[dict] = []
        self.skipped: List[dict] = []
        self.errors: List[dict] = []

    def to_dict(self) -> dict:
        return {
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
            "summary": {
                "total": len(self.created) + len(self.updated) + len(self.skipped) + len(self.errors),
                "created": len(self.created),
                "updated": len(self.updated),
                "skipped": len(self.skipped),
                "errors": len(self.errors),
            },
        }


class YAMLDeploymentService:
    """YAML 自动部署服务"""

    SUPPORTED_KINDS = {"Agent", "Skill", "MCP", "Collaboration"}
    API_VERSION = "agent/v1"

    @staticmethod
    def parse_yaml(yaml_content: str) -> List[dict]:
        """
        解析 YAML 内容,支持多文档(---分隔)。

        返回: [manifest_dict, ...]
        """
        try:
            documents = list(yaml.safe_load_all(yaml_content))
        except yaml.YAMLError as e:
            raise YAMLParseError(f"YAML 解析失败: {str(e)}")

        manifests = []
        for doc in documents:
            if doc is None:
                continue
            if not isinstance(doc, dict):
                raise YAMLParseError(f"YAML 文档必须是字典格式,获取: {type(doc).__name__}")

            # 校验必要字段
            api_version = doc.get("apiVersion", "")
            kind = doc.get("kind", "")
            metadata = doc.get("metadata", {})
            spec = doc.get("spec", {})

            if not kind:
                raise YAMLParseError("缺少 kind 字段")
            if kind not in YAMLDeploymentService.SUPPORTED_KINDS:
                raise YAMLParseError(f"不支持的 kind: {kind}, 支持: {YAMLDeploymentService.SUPPORTED_KINDS}")
            if not metadata.get("name"):
                raise YAMLParseError("缺少 metadata.name")

            manifests.append({
                "apiVersion": api_version,
                "kind": kind,
                "metadata": metadata,
                "spec": spec,
            })

        return manifests

    @staticmethod
    def validate_manifest(manifest: dict) -> Tuple[bool, str]:
        """校验单个 manifest"""
        kind = manifest.get("kind", "")
        spec = manifest.get("spec", {})
        name = manifest.get("metadata", {}).get("name", "")

        if not name:
            return False, "metadata.name 不能为空"

        if kind == "Agent":
            if not spec.get("model_provider"):
                return False, "Agent 必须指定 model_provider"
            if not spec.get("model_name"):
                return False, "Agent 必须指定 model_name"

        elif kind == "Skill":
            if not spec.get("type"):
                return False, "Skill 必须指定 type"

        elif kind == "MCP":
            if not spec.get("protocol"):
                return False, "MCP 必须指定 protocol"
            if not spec.get("endpoint"):
                return False, "MCP 必须指定 endpoint"

        elif kind == "Collaboration":
            if not spec.get("mode"):
                return False, "Collaboration 必须指定 mode"

        return True, "valid"

    @staticmethod
    async def apply_manifests(
        db, manifests: List[dict], user_id: str
    ) -> YAMLDeploymentResult:
        """应用 manifest 列表(创建或更新)"""
        from app.models.agent import Agent
        from app.services.agent_service import AgentService
        from sqlalchemy import select

        result = YAMLDeploymentResult()

        for manifest in manifests:
            kind = manifest["kind"]
            name = manifest["metadata"]["name"]
            spec = manifest.get("spec", {})
            labels = manifest.get("metadata", {}).get("labels", {})

            try:
                if kind == "Agent":
                    await _apply_agent(db, name, spec, labels, user_id, result)
                elif kind == "Skill":
                    await _apply_skill(db, name, spec, labels, user_id, result)
                elif kind == "MCP":
                    await _apply_mcp(db, name, spec, labels, user_id, result)
                elif kind == "Collaboration":
                    await _apply_collaboration(db, name, spec, labels, user_id, result)
            except Exception as e:
                result.errors.append({
                    "kind": kind,
                    "name": name,
                    "error": str(e)[:500],
                })
                logger.error("YAML部署 %s/%s 失败: %s", kind, name, str(e))

        return result

    @staticmethod
    async def export_to_yaml(db, kind: str, item_id: Optional[str] = None) -> str:
        """导出现有资源为 YAML"""
        from sqlalchemy import select

        manifests = []

        if kind == "Agent":
            from app.models.agent import Agent
            if item_id:
                result = await db.execute(select(Agent).where(Agent.id == item_id))
            else:
                result = await db.execute(select(Agent))
            for agent in result.scalars().all():
                manifests.append({
                    "apiVersion": YAMLDeploymentService.API_VERSION,
                    "kind": "Agent",
                    "metadata": {"name": agent.name, "id": agent.id},
                    "spec": {
                        "description": agent.description or "",
                        "system_prompt": agent.system_prompt or "",
                        "model_provider": agent.model_provider or "",
                        "model_name": agent.model_name or "",
                        "temperature": agent.temperature or 0.7,
                        "max_tokens": agent.max_tokens or 4096,
                        "status": agent.status or "draft",
                    },
                })

        output = "---\n".join(yaml.dump(m, allow_unicode=True, default_flow_style=False) for m in manifests)
        return output


async def _apply_agent(db, name, spec, labels, user_id, result):
    """应用 Agent manifest"""
    from app.models.agent import Agent
    from sqlalchemy import select

    # 查找同名 Agent
    existing = await db.execute(
        select(Agent).where(Agent.name == name)
    )
    agent = existing.scalar_one_or_none()

    if agent:
        # 更新
        for field in ("description", "system_prompt", "model_provider", "model_name",
                       "temperature", "max_tokens", "status"):
            if field in spec:
                setattr(agent, field, spec[field])
        agent.updated_at = datetime.now(timezone.utc)
        result.updated.append({"kind": "Agent", "name": name, "id": agent.id})
    else:
        # 创建
        agent = Agent(
            id=str(uuid.uuid4()),
            name=name,
            description=spec.get("description", ""),
            system_prompt=spec.get("system_prompt", ""),
            model_provider=spec.get("model_provider", "openai"),
            model_name=spec.get("model_name", ""),
            temperature=spec.get("temperature", 0.7),
            max_tokens=spec.get("max_tokens", 4096),
            status=spec.get("status", "draft"),
            created_by=user_id,
        )
        db.add(agent)
        result.created.append({"kind": "Agent", "name": name, "id": agent.id})

    await db.flush()


async def _apply_skill(db, name, spec, labels, user_id, result):
    """应用 Skill manifest"""
    from app.models.skill import Skill
    from sqlalchemy import select

    existing = await db.execute(
        select(Skill).where(Skill.name == name)
    )
    skill = existing.scalar_one_or_none()

    if skill:
        for field in ("description", "type", "content"):
            if field in spec:
                setattr(skill, field, spec[field])
        skill.updated_at = datetime.now(timezone.utc)
        result.updated.append({"kind": "Skill", "name": name, "id": skill.id})
    else:
        skill = Skill(
            id=str(uuid.uuid4()),
            name=name,
            description=spec.get("description", ""),
            type=spec.get("type", "tool"),
            content=json.dumps(spec.get("content", {}), ensure_ascii=False),
            created_by=user_id,
        )
        db.add(skill)
        result.created.append({"kind": "Skill", "name": name, "id": skill.id})

    await db.flush()


async def _apply_mcp(db, name, spec, labels, user_id, result):
    """应用 MCP manifest"""
    from app.models.mcp_server import MCPServer
    from sqlalchemy import select

    existing = await db.execute(
        select(MCPServer).where(MCPServer.name == name)
    )
    mcp = existing.scalar_one_or_none()

    if mcp:
        for field in ("description", "protocol", "endpoint", "enabled"):
            if field in spec:
                setattr(mcp, field, spec[field])
        mcp.updated_at = datetime.now(timezone.utc)
        result.updated.append({"kind": "MCP", "name": name, "id": mcp.id})
    else:
        mcp = MCPServer(
            id=str(uuid.uuid4()),
            name=name,
            description=spec.get("description", ""),
            protocol=spec.get("protocol", "mcp"),
            endpoint=spec.get("endpoint", ""),
            enabled=spec.get("enabled", True),
            created_by=user_id,
        )
        db.add(mcp)
        result.created.append({"kind": "MCP", "name": name, "id": mcp.id})

    await db.flush()


async def _apply_collaboration(db, name, spec, labels, user_id, result):
    """应用 Collaboration manifest"""
    from app.models.collaboration import Collaboration
    from sqlalchemy import select

    existing = await db.execute(
        select(Collaboration).where(Collaboration.name == name)
    )
    collab = existing.scalar_one_or_none()

    if collab:
        for field in ("description", "mode"):
            if field in spec:
                setattr(collab, field, spec[field])
        if "config" in spec:
            collab.config = json.dumps(spec["config"], ensure_ascii=False)
        collab.updated_at = datetime.now(timezone.utc)
        result.updated.append({"kind": "Collaboration", "name": name, "id": collab.id})
    else:
        collab = Collaboration(
            id=str(uuid.uuid4()),
            name=name,
            description=spec.get("description", ""),
            mode=spec.get("mode", "sequential"),
            config=json.dumps(spec.get("config", {}), ensure_ascii=False),
            status="draft",
            created_by=user_id,
        )
        db.add(collab)
        result.created.append({"kind": "Collaboration", "name": name, "id": collab.id})

    await db.flush()
