# 本地多智能体管理系统 (Local Agent Management System)

一站式本地化智能体管理平台 —— 支持 Agent 创建、Skill 编排、MCP 管理、在线市场、多智能体协作及全链路监控运维。

## 技术栈

| 层级 | 技术 | 说明 |
|:-----|:-----|:-----|
| **后端** | Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Alembic | 异步高性能 Web 框架 |
| **前端** | React 18 + TypeScript + Vite + Zustand + Tailwind CSS | 现代前端技术栈 |
| **数据库** | PostgreSQL 17 / Redis 7 / Qdrant | 关系型 + 缓存 + 向量数据库 |
| **认证** | JWT (python-jose) + PBKDF2-SHA256 | 无状态认证 |
| **容器** | Docker Compose | 本地开发基础设施 |

## 项目结构

```
agents-system/
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/          # API 路由层
│   │   │   ├── router.py    # 路由聚合
│   │   │   ├── auth.py      # 认证 API
│   │   │   ├── agents.py    # Agent CRUD API
│   │   │   ├── models.py    # 模型配置 API (TODO)
│   │   │   ├── conversations.py  # 对话 API (TODO)
│   │   │   └── workspaces.py     # 工作区 API (TODO)
│   │   ├── core/
│   │   │   ├── config.py    # 应用配置 (pydantic-settings)
│   │   │   └── exception_handlers.py  # 统一异常处理
│   │   ├── db/
│   │   │   └── session.py   # 异步数据库会话
│   │   ├── models/          # SQLAlchemy ORM 模型
│   │   │   ├── user.py      # 用户 / 角色 / 操作日志
│   │   │   ├── agent.py     # Agent / 模型配置模板
│   │   │   ├── conversation.py  # 会话 / 消息
│   │   │   ├── workspace.py     # 工作区 / 成员
│   │   │   └── skill.py     # 技能 / MCP 服务
│   │   ├── schemas/         # Pydantic 数据模型
│   │   │   ├── auth.py      # 认证相关
│   │   │   └── agent.py     # Agent 相关
│   │   └── services/        # 业务逻辑层
│   │       ├── auth_service.py   # 认证服务
│   │       ├── agent_service.py  # Agent 服务
│   │       └── llm/             # 模型适配器 (TODO)
│   ├── alembic/             # 数据库迁移
│   ├── requirements.txt     # Python 依赖
│   └── .env.example         # 环境变量模板
├── frontend/                 # React 前端
│   ├── src/
│   │   ├── components/      # 通用组件
│   │   │   ├── MainLayout   # 主布局 (侧边栏+顶栏)
│   │   │   ├── Sidebar      # 侧边导航
│   │   │   └── Header       # 顶部栏
│   │   ├── pages/           # 页面组件
│   │   │   ├── Login.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Agents.tsx / AgentDetail.tsx
│   │   │   ├── Conversations.tsx / ConversationDetail.tsx
│   │   │   ├── Models.tsx / Skills.tsx / MCPServers.tsx
│   │   │   └── Workspaces.tsx / NotFound.tsx
│   │   ├── api/             # API 服务层 (TODO)
│   │   ├── stores/          # Zustand 状态管理 (TODO)
│   │   └── App.tsx          # 路由配置
│   ├── vite.config.ts       # Vite 配置 (含 API 代理)
│   └── package.json
├── docker/
│   └── docker-compose.dev.yml  # 开发环境编排
├── docs/                    # 项目文档
│   ├── 智能体管理系统构建计划书.md  # 完整计划书 v1.6
│   ├── architecture/        # 架构图
│   └── design/              # 设计文档
├── data/                    # 数据目录 (.gitignore)
│   ├── postgres/
│   ├── redis/
│   └── qdrant/
├── Makefile                 # 常用命令
└── README.md
```

## 快速开始

### 前置要求

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose (推荐 Docker Desktop 或 Docker Engine 24+)
- npm

### 环境配置

```bash
# 复制环境变量模板
cp backend/.env.example backend/.env
```

默认配置连接本地 Docker 服务，直接使用即可。

### 启动开发环境

```bash
# 1. 启动基础设施 (PostgreSQL + Redis + Qdrant)
make infra-up

# 2. 安装后端依赖并启动
make backend-dev

# 3. 新开终端，安装前端依赖并启动
make frontend-dev

# 4. 访问
#    前端: http://localhost:5173
#    后端: http://localhost:8000
#    API 文档: http://localhost:8000/docs
#    ReDoc: http://localhost:8000/redoc
```

### 数据库迁移

```bash
# 执行待处理的迁移
make migrate

# 生成新的迁移 (修改 ORM 模型后)
cd backend && alembic revision --autogenerate -m "描述你的变更"

# 查看迁移历史
cd backend && alembic history

# 回滚迁移
cd backend && alembic downgrade -1
```

## Makefile 命令速查

| 命令 | 说明 |
|:-----|:------|
| `make infra-up` | 启动基础设施 (PostgreSQL / Redis / Qdrant) |
| `make infra-down` | 停止基础设施 |
| `make infra-logs` | 查看基础设施日志 |
| `make backend-install` | 安装后端依赖 |
| `make backend-dev` | 启动后端开发服务器 (热重载) |
| `make backend-test` | 运行后端测试 |
| `make frontend-install` | 安装前端依赖 |
| `make frontend-dev` | 启动前端开发服务器 |
| `make frontend-build` | 构建前端生产版本 |
| `make migrate` | 执行数据库迁移 |
| `make lint` | 运行代码检查 |
| `make test` | 运行全部测试 |
| `make clean` | 清理临时文件 |
| `make psql` | 进入 PostgreSQL 命令行 |
| `make redis-cli` | 进入 Redis 命令行 |

## 已完成的 API

| 端点 | 方法 | 说明 |
|:-----|:-----|:------|
| `/api/v1/auth/register` | POST | 用户注册 |
| `/api/v1/auth/login` | POST | 用户登录 |
| `/api/v1/auth/me` | GET | 获取当前用户信息 |
| `/api/v1/auth/logout` | POST | 登出 |
| `/api/v1/agents/` | GET | Agent 列表 (分页+筛选) |
| `/api/v1/agents/` | POST | 创建 Agent |
| `/api/v1/agents/{id}` | GET | Agent 详情 |
| `/api/v1/agents/{id}` | PUT | 更新 Agent |
| `/api/v1/agents/{id}` | DELETE | 删除 Agent |
| `/api/v1/agents/{id}/status` | PATCH | 变更 Agent 状态 |
| `/health` | GET | 健康检查 |

> 完整 API 文档见: `docs/design/api_spec.md`

## 数据库

当前已创建 12 张表：

- `users` — 用户
- `roles` — 角色
- `operation_logs` — 操作审计日志
- `agents` — 智能体
- `model_config_templates` — 模型配置模板
- `conversations` — 会话
- `messages` — 消息
- `workspaces` — 工作区
- `workspace_members` — 工作区成员
- `skills` — 技能
- `skill_bindings` — 技能绑定
- `mcp_servers` — MCP 服务

## 常见问题

### Docker 镜像拉取慢

使用国内的镜像加速器，修改 Docker 配置：

```json
{
  "registry-mirrors": ["https://docker.m.daocloud.io"]
}
```

### 中文乱码

项目使用 UTF-8 (无 BOM) 编码。如果出现乱码，请确认：
1. 文件保存为 UTF-8 without BOM
2. Git 配置 `core.autocrlf = false`
3. `.gitattributes` 已配置文本文件编码

### Python 依赖安装超时

使用清华镜像源：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### bcrypt 兼容性

项目使用 PBKDF2-SHA256 替代 bcrypt，避免 passlib 不兼容问题。如果遇到密码相关错误，确认 `auth_service.py` 使用 `hash_password()` / `verify_password()` 函数。

## 开发规范

- **后端**: 遵循 RESTful 设计，Service 层与 API 层分离，使用 async/await
- **前端**: 使用 Zustand 管理全局状态，axios 封装 API 调用
- **数据库**: 使用 Alembic 管理迁移，ORM 模型修改后生成迁移文件
- **编码**: UTF-8 without BOM，缩进 4 空格 (Python) / 2 空格 (TypeScript)

## 许可

MIT
