"""
内置 MCP 模板服务 — 8 类预置模板

功能:
- 8 大类 MCP Server 预置模板
- 一键安装
- 配置自定义
- 版本管理
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class MCPTemplate:
    """MCP 模板"""
    id: str = ""
    name: str = ""
    category: str = ""
    description: str = ""
    icon: str = ""
    config_schema: dict[str, Any] = field(default_factory=dict)
    default_config: dict[str, Any] = field(default_factory=dict)
    tools: list[dict[str, Any]] = field(default_factory=list)
    version: str = "1.0.0"
    author: str = "AgentSystem"
    tags: list[str] = field(default_factory=list)
    install_count: int = 0


class MCPTemplateService:
    """
    内置 MCP 模板（8 类）

    1. 文件系统 — 文件读写/搜索
    2. 数据库 — SQL 查询/表管理
    3. 搜索引擎 — Web 搜索/爬虫
    4. 代码执行 — Python/JS 沙箱
    5. API 网关 — REST/GraphQL 调用
    6. 消息队列 — Pub/Sub
    7. 邮件 — SMTP 发送
    8. 存储 — S3/MinIO
    """

    def __init__(self):
        self._templates: dict[str, MCPTemplate] = {}
        self._installations: list[dict[str, Any]] = []
        self._setup_defaults()

    def _setup_defaults(self):
        templates = [
            MCPTemplate(
                id="tpl_filesystem",
                name="文件系统",
                category="storage",
                description="文件读写、搜索、目录管理",
                icon="📁",
                config_schema={"type": "object", "properties": {"root_path": {"type": "string"}}},
                default_config={"root_path": "/data"},
                tools=[
                    {"name": "read_file", "description": "读取文件内容"},
                    {"name": "write_file", "description": "写入文件"},
                    {"name": "search_files", "description": "搜索文件"},
                    {"name": "list_directory", "description": "列出目录"},
                ],
                tags=["file", "storage", "basic"],
            ),
            MCPTemplate(
                id="tpl_database",
                name="数据库",
                category="data",
                description="SQL 查询、表管理、数据迁移",
                icon="🗄️",
                config_schema={
                    "type": "object",
                    "properties": {
                        "connection_string": {"type": "string"},
                        "read_only": {"type": "boolean"},
                    },
                },
                default_config={"connection_string": "", "read_only": True},
                tools=[
                    {"name": "execute_query", "description": "执行 SQL 查询"},
                    {"name": "list_tables", "description": "列出所有表"},
                    {"name": "describe_table", "description": "表结构描述"},
                    {"name": "get_row_count", "description": "获取行数"},
                ],
                tags=["database", "sql", "data"],
            ),
            MCPTemplate(
                id="tpl_search",
                name="搜索引擎",
                category="web",
                description="Web 搜索、页面抓取、内容提取",
                icon="🔍",
                config_schema={
                    "type": "object",
                    "properties": {
                        "search_engine": {"type": "string", "enum": ["google", "bing", "duckduckgo"]},
                        "api_key": {"type": "string"},
                    },
                },
                default_config={"search_engine": "duckduckgo", "api_key": ""},
                tools=[
                    {"name": "web_search", "description": "网页搜索"},
                    {"name": "fetch_page", "description": "抓取页面内容"},
                    {"name": "extract_text", "description": "提取正文"},
                ],
                tags=["search", "web", "scraping"],
            ),
            MCPTemplate(
                id="tpl_code_executor",
                name="代码执行",
                category="compute",
                description="Python/JS 沙箱执行、代码评估",
                icon="💻",
                config_schema={
                    "type": "object",
                    "properties": {
                        "language": {"type": "string", "enum": ["python", "javascript"]},
                        "timeout_seconds": {"type": "integer"},
                        "sandbox": {"type": "boolean"},
                    },
                },
                default_config={"language": "python", "timeout_seconds": 30, "sandbox": True},
                tools=[
                    {"name": "run_python", "description": "执行 Python 代码"},
                    {"name": "run_javascript", "description": "执行 JavaScript 代码"},
                    {"name": "install_package", "description": "安装包"},
                ],
                tags=["code", "execute", "sandbox"],
            ),
            MCPTemplate(
                id="tpl_api_gateway",
                name="API 网关",
                category="integration",
                description="REST/GraphQL API 调用、认证管理",
                icon="🌐",
                config_schema={
                    "type": "object",
                    "properties": {
                        "base_url": {"type": "string"},
                        "auth_type": {"type": "string", "enum": ["none", "bearer", "api_key"]},
                        "auth_token": {"type": "string"},
                    },
                },
                default_config={"base_url": "", "auth_type": "none", "auth_token": ""},
                tools=[
                    {"name": "http_get", "description": "GET 请求"},
                    {"name": "http_post", "description": "POST 请求"},
                    {"name": "graphql_query", "description": "GraphQL 查询"},
                ],
                tags=["api", "rest", "integration"],
            ),
            MCPTemplate(
                id="tpl_message_queue",
                name="消息队列",
                category="messaging",
                description="Pub/Sub 消息发布/订阅",
                icon="📨",
                config_schema={
                    "type": "object",
                    "properties": {
                        "broker_url": {"type": "string"},
                        "default_topic": {"type": "string"},
                    },
                },
                default_config={"broker_url": "redis://localhost:6379", "default_topic": "default"},
                tools=[
                    {"name": "publish", "description": "发布消息"},
                    {"name": "subscribe", "description": "订阅主题"},
                    {"name": "consume", "description": "消费消息"},
                ],
                tags=["message", "pubsub", "queue"],
            ),
            MCPTemplate(
                id="tpl_email",
                name="邮件服务",
                category="communication",
                description="SMTP 邮件发送、模板渲染",
                icon="📧",
                config_schema={
                    "type": "object",
                    "properties": {
                        "smtp_host": {"type": "string"},
                        "smtp_port": {"type": "integer"},
                        "username": {"type": "string"},
                        "password": {"type": "string"},
                    },
                },
                default_config={"smtp_host": "", "smtp_port": 587, "username": "", "password": ""},
                tools=[
                    {"name": "send_email", "description": "发送邮件"},
                    {"name": "send_template", "description": "发送模板邮件"},
                    {"name": "check_inbox", "description": "检查收件箱"},
                ],
                tags=["email", "smtp", "communication"],
            ),
            MCPTemplate(
                id="tpl_object_storage",
                name="对象存储",
                category="storage",
                description="S3/MinIO 文件上传/下载/管理",
                icon="☁️",
                config_schema={
                    "type": "object",
                    "properties": {
                        "endpoint": {"type": "string"},
                        "bucket": {"type": "string"},
                        "access_key": {"type": "string"},
                        "secret_key": {"type": "string"},
                    },
                },
                default_config={"endpoint": "", "bucket": "", "access_key": "", "secret_key": ""},
                tools=[
                    {"name": "upload_file", "description": "上传文件"},
                    {"name": "download_file", "description": "下载文件"},
                    {"name": "list_objects", "description": "列出对象"},
                    {"name": "delete_object", "description": "删除对象"},
                ],
                tags=["s3", "minio", "storage", "cloud"],
            ),
        ]
        for t in templates:
            self._templates[t.id] = t

    def list_templates(self, category: str = "") -> list[dict[str, Any]]:
        templates = list(self._templates.values())
        if category:
            templates = [t for t in templates if t.category == category]
        return [self._to_dict(t) for t in templates]

    def get_template(self, template_id: str) -> Optional[dict[str, Any]]:
        t = self._templates.get(template_id)
        return self._to_dict(t) if t else None

    def install_template(
        self,
        template_id: str,
        agent_id: str,
        config_overrides: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """一键安装模板"""
        tpl = self._templates.get(template_id)
        if not tpl:
            return {"error": "Template not found"}

        config = {**tpl.default_config, **(config_overrides or {})}
        tpl.install_count += 1

        installation = {
            "template_id": template_id,
            "agent_id": agent_id,
            "config": config,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "version": tpl.version,
        }
        self._installations.append(installation)
        return installation

    def get_installations(self, agent_id: Optional[str] = None) -> list[dict[str, Any]]:
        result = self._installations
        if agent_id:
            result = [i for i in result if i["agent_id"] == agent_id]
        return result

    def get_categories(self) -> dict[str, int]:
        cats = {}
        for t in self._templates.values():
            cats[t.category] = cats.get(t.category, 0) + 1
        return cats

    @staticmethod
    def _to_dict(t: MCPTemplate) -> dict[str, Any]:
        return {
            "id": t.id, "name": t.name, "category": t.category,
            "description": t.description, "icon": t.icon,
            "tools": t.tools, "version": t.version, "tags": t.tags,
            "install_count": t.install_count,
            "default_config": t.default_config,
        }
