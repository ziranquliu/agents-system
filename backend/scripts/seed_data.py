"""
种子数据初始化脚本

用法: python seed_data.py

运行前确保:
1. 数据库已通过 alembic upgrade head 完成迁移
2. 基础设施 Docker 已启动 (make infra-up)

填充数据:
- 1 个管理员用户 (admin/admin123!@#)
- 1 个测试用户 (testuser/Test123!@#)
- 5 个 Agent 模板
- 5 个 Skill 模板
- 3 个模型配置模板
- 3 个 MCP 服务配置
- 2 个工作区
"""
import asyncio
import sys
import os

# 确保能找到 app 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import async_session_factory, engine
from app.models.user import User, Role
from app.models.agent import Agent, ModelConfigTemplate
from app.models.workspace import Workspace, WorkspaceMember
from app.models.skill import Skill, SkillBinding, MCPServer
from app.services.auth_service import hash_password
from datetime import datetime, timezone
import uuid


async def seed():
    print("=" * 50)
    print("开始填充种子数据...")
    print("=" * 50)

    async with async_session_factory() as db:
        # ============================================================
        # 1. 角色
        # ============================================================
        admin_role = Role(id="role_admin", name="admin", description="系统管理员")
        user_role = Role(id="role_user", name="user", description="普通用户")
        db.add_all([admin_role, user_role])
        await db.flush()
        print("✅ 角色: admin, user")

        # ============================================================
        # 2. 用户
        # ============================================================
        users_data = [
            User(
                id="user_admin",
                username="admin",
                email="admin@agents.local",
                hashed_password=hash_password("admin123!@#"),
                role="admin",
                is_active=True,
            ),
            User(
                id="user_test",
                username="testuser",
                email="test@agents.local",
                hashed_password=hash_password("Test123!@#"),
                role="user",
                is_active=True,
            ),
        ]
        db.add_all(users_data)
        await db.flush()
        print("✅ 用户: admin (admin123!@#), testuser (Test123!@#)")

        # ============================================================
        # 3. 模型配置模板
        # ============================================================
        model_templates = [
            ModelConfigTemplate(
                id="model_gpt4o_mini",
                name="GPT-4o-mini",
                provider="openai",
                model="gpt-4o-mini",
                config='{"endpoint": "https://api.openai.com/v1", "api_key": "", "temperature": 0.7, "max_tokens": 16384, "context_window": 128000}',
                is_default=True,
                description="OpenAI GPT-4o-mini，快速且经济的对话模型",
                created_by="user_admin",
            ),
            ModelConfigTemplate(
                id="model_deepseek",
                name="DeepSeek-V3",
                provider="deepseek",
                model="deepseek-chat",
                config='{"endpoint": "https://api.deepseek.com/v1", "api_key": "", "temperature": 0.7, "max_tokens": 8192, "context_window": 65536}',
                is_default=False,
                description="DeepSeek-V3，高性价比的国产大模型",
                created_by="user_admin",
            ),
            ModelConfigTemplate(
                id="model_ollama",
                name="Ollama 本地模型",
                provider="ollama",
                model="qwen2.5:7b",
                config='{"endpoint": "http://localhost:11434/v1", "api_key": "ollama", "temperature": 0.7, "max_tokens": 4096, "context_window": 32768}',
                is_default=False,
                description="本地运行的 Ollama 模型",
                created_by="user_admin",
            ),
        ]
        db.add_all(model_templates)
        await db.flush()
        print("✅ 模型配置模板: 3 个")

        # ============================================================
        # 4. Agent
        # ============================================================
        agents_data = [
            Agent(
                id="agent_helper",
                name="通用对话助手",
                description="全能对话助手，回答问题、闲聊、提供建议",
                system_prompt="你是一个友好的通用对话助手，用中文回答用户的问题。",
                welcome_message="你好！我是通用对话助手，有什么可以帮助你的吗？",
                status="draft",
                model_provider="openai",
                model_name="gpt-4o-mini",
                temperature=0.7,
                max_tokens=4096,
                context_window=8192,
                workspace_id="ws_personal",
                created_by="user_admin",
            ),
            Agent(
                id="agent_coder",
                name="编程开发助手",
                description="代码生成、调试、重构、技术问答",
                system_prompt="你是一个专业的编程助手，精通多种编程语言。提供清晰、可运行的代码示例。",
                welcome_message="你好！我是编程开发助手，可以帮你解决代码问题。",
                status="draft",
                model_provider="openai",
                model_name="gpt-4o-mini",
                temperature=0.3,
                max_tokens=8192,
                context_window=128000,
                workspace_id="ws_personal",
                created_by="user_admin",
            ),
            Agent(
                id="agent_writer",
                name="内容写作助手",
                description="文章撰写、文案创作、报告生成",
                system_prompt="你是一个专业的内容创作助手，擅长各类文章、文案和报告的撰写。",
                welcome_message="你好！需要写点什么？我可以帮你创作各类内容。",
                status="draft",
                model_provider="deepseek",
                model_name="deepseek-chat",
                temperature=0.8,
                max_tokens=4096,
                context_window=65536,
                workspace_id="ws_personal",
                created_by="user_admin",
            ),
            Agent(
                id="agent_translator",
                name="翻译助手",
                description="多语种翻译、本地化服务",
                system_prompt="你是一个专业的翻译助手，精通中英日韩法德等多国语言。",
                welcome_message="你好！需要翻译什么内容？",
                status="draft",
                model_provider="openai",
                model_name="gpt-4o-mini",
                temperature=0.3,
                max_tokens=4096,
                context_window=8192,
                workspace_id="ws_team",
                created_by="user_test",
            ),
            Agent(
                id="agent_analyst",
                name="数据分析师",
                description="数据清洗、分析、可视化建议",
                system_prompt="你是一个数据分析专家，擅长数据清洗、统计分析和可视化。",
                welcome_message="你好！需要分析什么数据？",
                status="running",
                model_provider="openai",
                model_name="gpt-4o-mini",
                temperature=0.5,
                max_tokens=4096,
                context_window=8192,
                workspace_id="ws_team",
                created_by="user_admin",
            ),
        ]
        db.add_all(agents_data)
        await db.flush()
        print("✅ Agent: 5 个")

        # ============================================================
        # 5. Skill
        # ============================================================
        skills_data = [
            Skill(
                id="skill_code",
                name="代码执行器",
                type="工具",
                version="1.2.0",
                category="开发",
                description="安全执行 Python/JavaScript 代码",
                enabled=True,
                created_by="user_admin",
            ),
            Skill(
                id="skill_web",
                name="网页摘要",
                type="自然语言处理",
                version="2.0.1",
                category="信息处理",
                description="自动抓取网页内容并生成摘要",
                enabled=True,
                created_by="user_admin",
            ),
            Skill(
                id="skill_image",
                name="图片识别",
                type="视觉",
                version="1.0.0",
                category="多媒体",
                description="图片内容识别和分析",
                enabled=False,
                created_by="user_admin",
            ),
            Skill(
                id="skill_search",
                name="知识库搜索",
                type="检索",
                version="1.1.0",
                category="信息处理",
                description="在知识库中搜索相关文档",
                enabled=True,
                created_by="user_admin",
            ),
            Skill(
                id="skill_translate",
                name="翻译",
                type="自然语言处理",
                version="1.3.0",
                category="语言",
                description="多语种互译支持",
                enabled=True,
                created_by="user_admin",
            ),
        ]
        db.add_all(skills_data)
        await db.flush()

        # 绑定 Skill 到 Agent
        bindings = [
            SkillBinding(agent_id="agent_helper", skill_id="skill_web", enabled=True),
            SkillBinding(agent_id="agent_coder", skill_id="skill_code", enabled=True),
            SkillBinding(agent_id="agent_writer", skill_id="skill_translate", enabled=True),
            SkillBinding(agent_id="agent_analyst", skill_id="skill_search", enabled=True),
        ]
        for i, b in enumerate(bindings):
            b.id = f"bind_{i}"
        db.add_all(bindings)
        await db.flush()
        print("✅ Skill: 5 个，绑定: 4 个")

        # ============================================================
        # 6. MCP Server
        # ============================================================
        mcps_data = [
            MCPServer(
                id="mcp_filesystem",
                name="文件系统 MCP",
                url="stdio://local",
                protocol="stdio",
                status="active",
                health_status="healthy",
                version="1.0.0",
                description="本地文件系统操作服务",
                created_by="user_admin",
            ),
            MCPServer(
                id="mcp_database",
                name="数据库查询服务",
                url="https://mcp.internal/api",
                protocol="sse",
                status="active",
                health_status="healthy",
                version="2.1.0",
                description="数据库查询和分析服务",
                created_by="user_admin",
            ),
            MCPServer(
                id="mcp_search",
                name="搜索服务",
                url="http://search-mcp:8080",
                protocol="streamable-http",
                status="inactive",
                health_status="unknown",
                version="0.9.0",
                description="网络搜索和信息检索服务",
                created_by="user_admin",
            ),
        ]
        db.add_all(mcps_data)
        await db.flush()
        print("✅ MCP Server: 3 个")

        # ============================================================
        # 7. 工作区
        # ============================================================
        workspaces_data = [
            Workspace(
                id="ws_personal",
                name="个人工作区",
                description="个人智能体实验场",
                owner_id="user_admin",
                is_active=True,
                member_count=1,
            ),
            Workspace(
                id="ws_team",
                name="团队协作空间",
                description="多人共享的智能体工作区",
                owner_id="user_admin",
                is_active=True,
                member_count=2,
            ),
        ]
        db.add_all(workspaces_data)
        await db.flush()

        # 工作区成员
        members = [
            WorkspaceMember(id="member_1", workspace_id="ws_personal", user_id="user_admin", role="owner"),
            WorkspaceMember(id="member_2", workspace_id="ws_team", user_id="user_admin", role="owner"),
            WorkspaceMember(id="member_3", workspace_id="ws_team", user_id="user_test", role="member"),
        ]
        db.add_all(members)
        await db.flush()
        print("✅ 工作区: 2 个，成员: 3 条")

        # ============================================================
        # 提交
        # ============================================================
        await db.commit()
        print("=" * 50)
        print("种子数据填充完成！")
        print(f"  用户: admin / testuser")
        print(f"  Agent: 5 个")
        print(f"  Skill: 5 个 + 4 绑定")
        print(f"  模型配置: 3 个")
        print(f"  MCP 服务: 3 个")
        print(f"  工作区: 2 个")
        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(seed())
