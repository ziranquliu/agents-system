# 项目代码目录结构

> 配套文档：智能体管理系统构建计划书 v1.7 — 第9章
> 技术栈：FastAPI + React + PostgreSQL + Redis + Qdrant + MinIO

---

## 1. 后端项目结构

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI 入口
│   ├── config.py                   # 配置管理（环境变量/Pydantic Settings）
│   ├── database.py                 # 数据库连接（SQLAlchemy async）
│   ├── dependencies.py             # 通用依赖注入
│   │
│   ├── api/                        # API 路由层
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── router.py           # v1 路由聚合
│   │   │   ├── auth.py             # 认证接口
│   │   │   ├── workspaces.py       # 工作空间
│   │   │   ├── agents.py           # 智能体
│   │   │   ├── model_templates.py  # 模型配置模板
│   │   │   ├── skills.py           # Skill
│   │   │   ├── mcps.py             # MCP
│   │   │   ├── sessions.py         # 会话
│   │   │   ├── messages.py         # 消息
│   │   │   ├── token_usage.py      # Token
│   │   │   ├── knowledge.py        # 知识库
│   │   │   ├── memories.py         # Agent 记忆
│   │   │   ├── dashboard.py        # 监控看板
│   │   │   ├── health.py           # 健康检查
│   │   │   ├── ops.py              # 自动化运维
│   │   │   ├── backups.py          # 备份
│   │   │   ├── audit.py            # 审计
│   │   │   ├── collaboration.py    # 协作
│   │   │   ├── scanner.py          # 扫描器
│   │   │   ├── updates.py          # 更新中心
│   │   │   ├── market_agents.py    # Agent 市场
│   │   │   ├── market_skills.py    # Skill 市场
│   │   │   ├── market_mcps.py      # MCP 市场
│   │   │   └── market_models.py    # 模型市场
│   │   │
│   │   └── ws/                     # WebSocket 路由
│   │       ├── __init__.py
│   │       ├── chat.py             # 对话流式接口
│   │       └── dashboard.py        # 实时看板推送
│   │
│   ├── models/                    # SQLAlchemy ORM 模型
│   │   ├── __init__.py
│   │   ├── base.py                 # 基类（UUID/时间戳混入）
│   │   ├── user.py                 # 用户
│   │   ├── workspace.py            # 工作空间
│   │   ├── agent.py                # 智能体
│   │   ├── agent_config.py         # Agent 配置
│   │   ├── model_template.py       # 模型配置模板
│   │   ├── model_template_version.py
│   │   ├── agent_model_binding.py  # Agent 模型绑定
│   │   ├── skill.py                # Skill
│   │   ├── agent_skill.py          # Agent-Skill 关联
│   │   ├── mcp.py                  # MCP
│   │   ├── agent_mcp.py            # Agent-MCP 关联
│   │   ├── session.py              # 会话
│   │   ├── session_message.py      # 消息
│   │   ├── token_usage.py          # Token 消耗
│   │   ├── knowledge_base.py       # 知识库
│   │   ├── agent_memory.py         # Agent 记忆
│   │   ├── audit_log.py            # 审计日志
│   │   ├── backup_record.py        # 备份记录
│   │   ├── health_check.py         # 健康检查
│   │   ├── collaboration_task.py   # 协作任务
│   │   └── scanner_result.py       # 扫描结果
│   │
│   ├── schemas/                    # Pydantic 请求/响应模型
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── agent.py
│   │   ├── model_template.py
│   │   ├── skill.py
│   │   ├── mcp.py
│   │   ├── session.py
│   │   ├── chat.py
│   │   └── ...
│   │
│   ├── services/                   # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── auth_service.py         # 认证/授权
│   │   ├── agent_service.py        # Agent CRUD
│   │   ├── model_template_service.py  # 模型配置模板
│   │   ├── model_binding_service.py   # 模型绑定与同步
│   │   ├── skill_service.py        # Skill 管理
│   │   ├── mcp_service.py          # MCP 管理
│   │   ├── session_service.py      # 会话管理
│   │   ├── chat_service.py         # 对话引擎
│   │   ├── token_service.py        # Token 管理
│   │   ├── memory_service.py       # 记忆管理
│   │   ├── audit_service.py        # 审计服务
│   │   ├── backup_service.py       # 备份服务
│   │   ├── health_service.py       # 健康检查
│   │   ├── collaboration_service.py # 协作引擎
│   │   ├── scanner_service.py      # 扫描器
│   │   └── update_service.py       # 更新检测
│   │
│   ├── engine/                     # 核心引擎
│   │   ├── __init__.py
│   │   ├── agent_engine.py         # Agent 运行时引擎
│   │   ├── collaboration_engine.py # 多 Agent 协作引擎
│   │   ├── token_optimizer.py      # Token 优化器
│   │   └── skill_runner.py         # Skill 执行器
│   │
│   ├── core/                       # 核心基础设施
│   │   ├── __init__.py
│   │   ├── security.py             # JWT/密码/API Key 加密
│   │   ├── exceptions.py           # 自定义异常
│   │   ├── response.py             # 统一响应格式
│   │   ├── pagination.py           # 分页
│   │   ├── cache.py                # 缓存工具
│   │   ├── event_bus.py            # 事件总线
│   │   └── logging.py              # 日志配置
│   │
│   ├── db/                         # 数据库工具
│   │   ├── __init__.py
│   │   ├── session.py              # 异步 Session 管理
│   │   ├── migrations/             # Alembic 迁移
│   │   │   ├── env.py
│   │   │   ├── alembic.ini
│   │   │   └── versions/
│   │   └── seed.py                 # 种子数据
│   │
│   └── tasks/                      # Celery 定时/异步任务
│       ├── __init__.py
│       ├── celery_app.py           # Celery 配置
│       ├── scanner_task.py         # 扫描任务
│       ├── backup_task.py          # 备份任务
│       ├── health_check_task.py    # 健康检查任务
│       ├── model_sync_task.py      # 模型配置同步通知
│       └── memory_maintenance.py   # 记忆维护
│
├── tests/                          # 测试
│   ├── conftest.py                 # 测试 fixtures
│   ├── test_api/                   # API 测试
│   ├── test_services/              # 服务测试
│   └── test_engine/                # 引擎测试
│
├── alembic.ini
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## 2. 前端项目结构

```
frontend/
├── src/
│   ├── main.tsx                    # 入口
│   ├── App.tsx                     # 根组件 + 路由
│   │
│   ├── router/                     # 路由配置
│   │   ├── index.tsx               # 路由表
│   │   ├── AuthGuard.tsx           # 鉴权守卫
│   │   └── RoleGuard.tsx           # 角色守卫
│   │
│   ├── layouts/                    # 布局组件
│   │   ├── AppLayout.tsx
│   │   ├── WorkspaceLayout.tsx
│   │   ├── AdminLayout.tsx
│   │   ├── Sidebar.tsx
│   │   └── HeaderBar.tsx
│   │
│   ├── pages/                      # 页面组件
│   │   ├── login/
│   │   ├── workspace/
│   │   ├── agents/
│   │   │   ├── list/
│   │   │   ├── create/
│   │   │   ├── detail/
│   │   │   ├── edit/
│   │   │   └── settings/
│   │   ├── model-templates/
│   │   │   ├── list/
│   │   │   ├── create/
│   │   │   └── detail/
│   │   ├── skills/
│   │   │   ├── list/
│   │   │   ├── detail/
│   │   │   └── batch/
│   │   ├── mcps/
│   │   │   ├── list/
│   │   │   ├── detail/
│   │   │   └── batch/
│   │   ├── chat/
│   │   ├── sessions/
│   │   ├── token/
│   │   ├── knowledge/
│   │   ├── memories/
│   │   ├── monitor/
│   │   ├── backup/
│   │   ├── audit/
│   │   ├── collaboration/
│   │   ├── market/
│   │   ├── scanner/
│   │   └── settings/
│   │
│   ├── components/                 # 组件
│   │   ├── common/                 # 通用组件
│   │   │   ├── PageContainer/
│   │   │   ├── DataTable/
│   │   │   ├── FormDrawer/
│   │   │   ├── EmptyState/
│   │   │   ├── Loading/
│   │   │   ├── ModelSelector/
│   │   │   ├── AgentSelector/
│   │   │   └── StatusBadge/
│   │   └── business/               # 业务组件
│   │       ├── AgentCard/
│   │       ├── AgentForm/
│   │       ├── ModelBindingSelect/
│   │       ├── ChatInput/
│   │       ├── ChatMessage/
│   │       ├── SessionTree/
│   │       ├── SkillCard/
│   │       ├── McpCard/
│   │       ├── TemplateForm/
│   │       ├── TemplateTestBtn/
│   │       ├── VersionTimeline/
│   │       ├── BoundAgentList/
│   │       ├── TokenChart/
│   │       ├── HealthRadar/
│   │       └── AuditTable/
│   │
│   ├── stores/                     # 状态管理
│   │   ├── authStore.ts
│   │   ├── workspaceStore.ts
│   │   ├── agentStore.ts
│   │   ├── modelTemplateStore.ts
│   │   ├── skillStore.ts
│   │   ├── mcpStore.ts
│   │   ├── sessionStore.ts
│   │   ├── chatStore.ts
│   │   ├── tokenStore.ts
│   │   ├── monitorStore.ts
│   │   └── uiStore.ts
│   │
│   ├── services/                   # API 调用层
│   │   ├── api.ts                  # Axios 实例/拦截器
│   │   ├── authApi.ts
│   │   ├── agentApi.ts
│   │   ├── modelTemplateApi.ts
│   │   ├── skillApi.ts
│   │   ├── mcpApi.ts
│   │   ├── sessionApi.ts
│   │   ├── chatApi.ts              # WebSocket 对话
│   │   ├── tokenApi.ts
│   │   ├── monitorApi.ts
│   │   ├── backupApi.ts
│   │   ├── auditApi.ts
│   │   ├── collaborationApi.ts
│   │   └── marketApi.ts
│   │
│   ├── hooks/                      # 自定义 Hooks
│   │   ├── useAuth.ts
│   │   ├── usePagination.ts
│   │   ├── useWebSocket.ts
│   │   └── useModelTemplate.ts
│   │
│   ├── utils/                      # 工具函数
│   │   ├── format.ts               # 日期/数字格式化
│   │   ├── validators.ts           # 表单校验
│   │   └── constants.ts            # 常量定义
│   │
│   └── styles/                     # 样式
│       ├── global.css
│       ├── variables.css
│       └── theme.ts
│
├── public/
├── vite.config.ts
├── tsconfig.json
├── package.json
├── Dockerfile
└── .env.example
```

---

## 3. 模块依赖关系

```
api/ (路由层) → schemas/ (请求校验) → services/ (业务逻辑) → models/ (ORM)
                                                          → engine/ (核心引擎)
                                                          → core/ (基础设施)
                                                          → tasks/ (后台任务)

依赖方向：api → services → models + engine + core + tasks
无循环依赖，Service 层可调用其他 Service（通过 ServiceFactory）
```

---

## 4. 命名规范

| 层级 | 命名规范 | 示例 |
|------|---------|------|
| 路由文件 | 复数 snake_case | agents.py, model_templates.py |
| ORM 模型 | 单数 PascalCase | class Agent(Base) |
| Schema | 单数 PascalCase + Req/Resp | AgentCreateReq, AgentResp |
| Service | 单数 snake_case + service | agent_service.py |
| API 函数 | 动词+资源 | create_agent, list_agents |
| 前端页面 | 驼峰文件夹 | agentCreate/ |
| 前端组件 | PascalCase | AgentCard.tsx |
| 前端 Store | 驼峰 | agentStore.ts |
| 前端服务 | 驼峰 | agentApi.ts |

---

> **文件版本：** v1.0 | **更新日期：** 2026-07-26
