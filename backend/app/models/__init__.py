# SQLAlchemy ORM 模型 — 占位
# 完整模型定义详见 ../plan/design/database_design.md
# 后续通过 Alembic 迁移自动生成

from app.db.session import Base

# 导入各模块模型确保注册
from app.models.user import User
from app.models.agent import Agent
from app.models.conversation import Conversation, Message
from app.models.workspace import Workspace, WorkspaceMember
from app.models.skill import Skill
from app.models.mcp import MCPServer
