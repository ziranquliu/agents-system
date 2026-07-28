# 前端页面结构与路由设计

> 配套文档：智能体管理系统构建计划书 v1.7 — 第9章
> 技术栈：React 18 + TypeScript + Ant Design Pro + Zustand

---

## 1. 页面树总览

```
/                                   → 登录页
/dashboard                          → 工作台总览
├── /workspace                      → 工作空间选择
└── /workspace/:id                  → 进入工作空间
    ├── /agents                     → 智能体管理
    │   ├── /agents/list            → 智能体列表
    │   ├── /agents/create          → 创建智能体
    │   ├── /agents/:id             → 智能体详情
    │   ├── /agents/:id/edit        → 编辑配置
    │   ├── /agents/:id/sessions    → 对话记录
    │   └── /agents/:id/settings    → 高级设置
    ├── /chat                       → 对话界面
    │   └── /chat/:session_id       → 具体会话
    ├── /skills                     → Skill 管理
    │   ├── /skills/list            → 技能列表
    │   ├── /skills/:id             → 技能详情
    │   └── /skills/batch           → 批量安装
    ├── /mcps                       → MCP 管理
    │   ├── /mcps/list              → MCP 列表
    │   ├── /mcps/:id               → MCP 详情
    │   └── /mcps/batch             → 批量注册
    ├── /model-templates            → 模型配置模板
    │   ├── /model-templates/list   → 模板列表
    │   ├── /model-templates/create → 创建模板
    │   └── /model-templates/:id    → 模板详情
    ├── /sessions                   → 会话管理
    │   ├── /sessions/list          → 会话列表
    │   └── /sessions/:id           → 会话详情
    ├── /token                      → Token 管理
    │   ├── /token/dashboard        → Token 看板
    │   └── /token/budget           → 预算设置
    ├── /knowledge                  → 知识库
    │   ├── /knowledge/list         → 知识库列表
    │   └── /knowledge/:id          → 知识库详情
    ├── /memories                   → Agent 记忆
    │   └── /memories/:agent_id     → 记忆管理
    ├── /monitor                    → 监控运维
    │   ├── /monitor/dashboard      → 监控看板
    │   ├── /monitor/health         → 健康检查
    │   └── /monitor/ops            → 自动化运维
    ├── /backup                     → 备份恢复
    │   ├── /backup/list            → 备份列表
    │   └── /backup/create          → 创建备份
    ├── /audit                      → 操作审计
    │   ├── /audit/logs             → 审计日志
    │   └── /audit/reports          → 审计报表
    ├── /collaboration              → 多 Agent 协作
    │   ├── /collaboration/tasks    → 协作任务
    │   └── /collaboration/create   → 创建任务
    ├── /market                     → 在线市场
    │   ├── /market/agents          → Agent 市场
    │   ├── /market/skills          → Skill 市场
    │   ├── /market/mcps            → MCP 市场
    │   └── /market/models          → 模型市场
    ├── /scanner                    → 扫描更新
    │   ├── /scanner/results        → 扫描结果
    │   └── /scanner/updates        → 更新中心
    ├── /workspace-settings         → 空间设置
    └── /workspace-settings/members → 成员管理

/admin                              → 管理后台
├── /admin/users                    → 用户管理
├── /admin/system                   → 系统设置
└── /admin/logs                     → 系统日志
```

---

## 2. 路由配置

```typescript
// src/router/index.tsx
const routes: RouteConfig[] = [
  // 公开路由
  { path: '/login', component: LoginPage, auth: false },
  { path: '/register', component: RegisterPage, auth: false },

  // 认证路由 - 工作台
  {
    path: '/dashboard',
    component: DashboardLayout,
    auth: true,
    children: [
      { index: true, component: WorkspaceSelector },
      {
        path: ':workspaceId',
        component: WorkspaceLayout,
        children: [
          // 首页
          { path: 'overview', component: WorkspaceOverview },

          // Agent 管理
          {
            path: 'agents',
            component: AgentLayout,
            children: [
              { path: 'list', component: AgentList },
              { path: 'create', component: AgentCreate },
              { path: ':agentId', component: AgentDetail },
              { path: ':agentId/edit', component: AgentEdit },
              { path: ':agentId/sessions', component: AgentSessions },
              { path: ':agentId/settings', component: AgentSettings },
            ]
          },

          // 对话
          {
            path: 'chat',
            children: [
              { path: ':sessionId', component: ChatSession },
            ]
          },

          // 模型配置模板
          {
            path: 'model-templates',
            children: [
              { path: 'list', component: ModelTemplateList },
              { path: 'create', component: ModelTemplateCreate },
              { path: ':templateId', component: ModelTemplateDetail },
            ]
          },

          // Skill 管理
          {
            path: 'skills',
            children: [
              { path: 'list', component: SkillList },
              { path: ':skillId', component: SkillDetail },
              { path: 'batch', component: SkillBatchInstall },
            ]
          },

          // MCP 管理
          {
            path: 'mcps',
            children: [
              { path: 'list', component: McpList },
              { path: ':mcpId', component: McpDetail },
              { path: 'batch', component: McpBatchRegister },
            ]
          },

          // 会话管理
          {
            path: 'sessions',
            children: [
              { path: 'list', component: SessionList },
              { path: ':sessionId', component: SessionDetail },
            ]
          },

          // Token
          {
            path: 'token',
            children: [
              { path: 'dashboard', component: TokenDashboard },
              { path: 'budget', component: TokenBudget },
            ]
          },

          // 知识库
          {
            path: 'knowledge',
            children: [
              { path: 'list', component: KnowledgeList },
              { path: ':kbId', component: KnowledgeDetail },
            ]
          },

          // Agent 记忆
          {
            path: 'memories',
            children: [
              { path: ':agentId', component: AgentMemories },
            ]
          },

          // 监控
          {
            path: 'monitor',
            children: [
              { path: 'dashboard', component: MonitorDashboard },
              { path: 'health', component: HealthCheck },
              { path: 'ops', component: OpsAutomation },
            ]
          },

          // 备份
          {
            path: 'backup',
            children: [
              { path: 'list', component: BackupList },
              { path: 'create', component: BackupCreate },
            ]
          },

          // 审计
          {
            path: 'audit',
            children: [
              { path: 'logs', component: AuditLogs },
              { path: 'reports', component: AuditReports },
            ]
          },

          // 协作
          {
            path: 'collaboration',
            children: [
              { path: 'tasks', component: CollabTasks },
              { path: 'create', component: CollabCreate },
            ]
          },

          // 市场
          {
            path: 'market',
            children: [
              { path: 'agents', component: MarketAgents },
              { path: 'skills', component: MarketSkills },
              { path: 'mcps', component: MarketMcps },
              { path: 'models', component: MarketModels },
            ]
          },

          // 扫描更新
          {
            path: 'scanner',
            children: [
              { path: 'results', component: ScannerResults },
              { path: 'updates', component: UpdateCenter },
            ]
          },

          // 设置
          {
            path: 'settings',
            component: WorkspaceSettings,
            children: [
              { path: 'members', component: MemberManagement },
            ]
          },
        ]
      }
    ]
  },

  // 管理后台
  {
    path: '/admin',
    component: AdminLayout,
    auth: true,
    role: 'admin',
    children: [
      { path: 'users', component: AdminUsers },
      { path: 'system', component: AdminSystem },
      { path: 'logs', component: AdminLogs },
    ]
  },

  // 404
  { path: '*', component: NotFound },
];
```

---

## 3. 组件拆分方案

### 3.1 通用组件（src/components/common/）

| 组件 | 说明 |
|------|------|
| PageContainer | 页面容器（面包屑+标题+操作栏） |
| DataTable | 通用数据表格（筛选+排序+分页） |
| FormDrawer | 表单抽屉 |
| ConfirmModal | 确认弹窗 |
| EmptyState | 空状态 |
| ErrorBoundary | 错误边界 |
| Loading | 加载中 |
| ModelSelector | 模型选择器（从模板中选） |
| AgentSelector | Agent 选择器（多选） |
| SkillSelector | Skill 选择器 |
| StatusBadge | 状态标签 |
| SearchInput | 搜索输入框 |

### 3.2 业务组件（src/components/business/）

| 组件 | 所属页面 | 说明 |
|------|---------|------|
| AgentCard | AgentList | Agent 卡片 |
| AgentForm | AgentCreate/Edit | Agent 创建/编辑表单 |
| ModelBindingSelect | AgentForm | 模型配置模板绑定选择 |
| ChatInput | ChatSession | 消息输入框 |
| ChatMessage | ChatSession | 消息气泡 |
| SessionTree | SessionList | 会话列表树 |
| SkillCard | SkillList | Skill 卡片 |
| McpCard | McpList | MCP 卡片 |
| TemplateForm | ModelTemplateCreate | 模板编辑表单 |
| TemplateTestBtn | TemplateDetail | 连接测试按钮 |
| VersionTimeline | TemplateDetail | 版本时间线 |
| BoundAgentList | TemplateDetail | 已绑定 Agent 列表 |
| TokenChart | TokenDashboard | Token 趋势图 |
| HealthRadar | MonitorDashboard | 健康雷达图 |
| AuditTable | AuditLogs | 审计日志表格 |

### 3.3 布局组件（src/components/layout/）

| 组件 | 说明 |
|------|------|
| AppLayout | 应用主布局（侧边栏+顶栏+内容区） |
| WorkspaceLayout | 工作空间布局（空间切换+二级菜单） |
| AdminLayout | 管理后台布局 |
| Sidebar | 侧边导航 |
| HeaderBar | 顶栏（搜索+通知+用户菜单） |

---

## 4. 状态管理（Zustand Store）

```typescript
// src/stores/
├── authStore.ts          // 认证状态
├── workspaceStore.ts     // 当前工作空间
├── agentStore.ts         // Agent 列表/当前 Agent
├── modelTemplateStore.ts // 模型配置模板
├── skillStore.ts         // Skill 列表
├── mcpStore.ts           // MCP 列表
├── sessionStore.ts       // 当前会话/消息
├── chatStore.ts          // 对话实时状态
├── tokenStore.ts         // Token 统计
├── monitorStore.ts       // 监控数据
└── uiStore.ts            // UI 状态（侧边栏折叠/主题等）
```

---

## 5. 页面与 API 映射

| 页面 | 对应 API |
|------|----------|
| AgentList | GET /workspaces/{ws_id}/agents |
| AgentCreate | POST /workspaces/{ws_id}/agents |
| AgentDetail | GET /agents/{id} |
| ModelTemplateList | GET /workspaces/{ws_id}/model-templates |
| ModelTemplateCreate | POST /workspaces/{ws_id}/model-templates |
| ModelTemplateDetail | GET /model-templates/{id} + /bound-agents |
| SkillList | GET /workspaces/{ws_id}/skills |
| SkillBatchInstall | POST /skills/{id}/install-to-agents |
| McpList | GET /workspaces/{ws_id}/mcps |
| TokenDashboard | GET /workspaces/{ws_id}/token-usage/* |
| MonitorDashboard | GET /workspaces/{ws_id}/dashboard |
| AuditLogs | GET /workspaces/{ws_id}/audit-logs |
| CollabTasks | GET /workspaces/{ws_id}/collaboration/tasks |
| ChatSession | WS /ws/v1/chat/{session_id} |
| MarketAgents | GET /market/agents |

---

> **页面总数：** ~40 个页面 | **路由层级：** 3 级 | **组件数：** ~30 个业务组件
> **文件版本：** v1.0 | **更新日期：** 2026-07-26
