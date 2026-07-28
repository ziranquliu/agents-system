# 业务数据流图

> 配套文档：智能体管理系统构建计划书 v1.7 — 第9章
> 涵盖核心业务流程的数据流与事件流

---

## 1. 核心链路一：创建 Agent → 对话

```mermaid
sequenceDiagram
    participant User as 用户
    participant FE as 前端
    participant API as API 层
    participant SVC as AgentService
    participant DB as PostgreSQL
    participant Engine as Agent 引擎
    participant LLM as 大模型

    User->>FE: 创建 Agent
    FE->>API: POST /agents { name, prompt, model_template_id }
    API->>SVC: create_agent()
    SVC->>DB: INSERT agents
    SVC->>DB: INSERT agent_model_bindings (绑定模板)
    SVC->>DB: INSERT agent_configs (初始配置)
    SVC-->>API: Agent 创建成功
    API-->>FE: 201 { agent_id }
    FE-->>User: 创建成功

    User->>FE: 发送对话消息
    FE->>API: POST /sessions { agent_id } (创建会话)
    API->>API: 鉴权 + 工作空间隔离
    API-->>FE: 会话 ID

    FE->>API: WS /chat/{session_id}
    activate API
    API->>SVC: get_agent_config(agent_id)
    SVC-->>API: 配置 + 模型绑定信息
    API->>Engine: chat(agent_config, message)
    Engine->>DB: 查询模型模板配置
    Engine->>LLM: 调用模型（带系统提示词）
    LLM-->>Engine: 流式响应
    Engine-->>API: Token 流
    API-->>FE: SSE Token 流
    deactivate API
    FE-->>User: 逐字显示回复
```

---

## 2. 核心链路二：模型配置模板 → 一键绑定 → 自动同步

```mermaid
sequenceDiagram
    participant Admin as 管理员
    participant FE as 前端
    participant API as API 层
    participant TemplateSvc as ModelTemplateService
    participant DB as PostgreSQL
    participant EventBus as 事件总线
    participant SyncSvc as SyncService
    participant Agents as Agent 运行时

    Admin->>FE: 创建模型配置模板
    FE->>API: POST /model-templates { provider, model, api_key, params }
    API->>TemplateSvc: create_template()
    TemplateSvc->>DB: INSERT model_config_templates
    TemplateSvc->>DB: INSERT model_config_versions (v1)
    API-->>FE: 模板创建成功（draft 状态）

    Admin->>FE: 测试连接
    FE->>API: POST /model-templates/{id}/test
    API->>TemplateSvc: test_connection()
    TemplateSvc->>LLM: 调用模型（简单 prompt）
    LLM-->>TemplateSvc: 成功响应
    TemplateSvc->>DB: UPDATE status = published
    API-->>FE: { status: "passed" }

    Admin->>FE: 创建 Agent 并绑定模板
    FE->>API: POST /agents { model_template_id, ... }
    API->>TemplateSvc: bind_agent(template_id, agent_id)
    TemplateSvc->>DB: INSERT agent_model_bindings (绑定状态=synced)
    API-->>FE: Agent 创建成功

    Admin->>FE: 修改模板（切换模型）
    FE->>API: PUT /model-templates/{id} { model_name: "gpt-4o-mini" }
    API->>TemplateSvc: update_template()
    TemplateSvc->>DB: INSERT model_config_versions (v2)
    TemplateSvc->>DB: UPDATE agent_model_bindings (绑定状态=outdated)
    TemplateSvc->>EventBus: publish("model_template.changed", { template_id, version: 2 })
    API-->>FE: { version: 2, bound_agents_count: 3 }

    EventBus-->>SyncSvc: 异步消费变更事件
    SyncSvc->>DB: 查询所有绑定的 Agent
    SyncSvc->>Agents: 通知配置已变更（同步模式=auto）
    SyncSvc->>DB: UPDATE agent_model_bindings (绑定状态=synced)
    Agents->>LLM: 后续对话自动使用新模型
```

---

## 3. 核心链路三：Skill 批量安装 → 跨 Agent 同步

```mermaid
sequenceDiagram
    participant User as 用户
    participant FE as 前端
    participant API as API 层
    participant SkillSvc as SkillService
    participant DB as PostgreSQL
    participant AgentEngine as Agent 引擎

    User->>FE: 选择多个 Agent + 多个 Skill
    FE->>API: POST /skills/{id}/install-to-agents
    API->>SkillSvc: batch_install(skill_id, [agent_ids], params)
    
    par 并行安装到每个 Agent
        SkillSvc->>DB: INSERT agent_skills (agent_1, skill_x)
        SkillSvc->>DB: INSERT agent_skills (agent_2, skill_x)
        SkillSvc->>DB: INSERT agent_skills (agent_3, skill_x)
    end
    
    SkillSvc->>AgentEngine: 通知 Agent 技能列表已更新
    API-->>FE: { success_count: 3, failed_count: 0 }
    FE-->>User: 批量安装成功

    User->>FE: 修改 Skill 版本
    FE->>API: PUT /skills/{id} { version: "2.0.0" }
    API->>SkillSvc: update_skill()
    SkillSvc->>DB: UPDATE skills SET version = "2.0.0"
    SkillSvc->>AgentEngine: 通知所有绑定的 Agent 技能已更新
    API-->>FE: 更新成功
```

---

## 4. 核心链路四：多 Agent 协作

```mermaid
sequenceDiagram
    participant User as 用户
    participant API as API 层
    participant Collab as 协作引擎
    participant AgentA as 主管 Agent
    participant AgentB as 工作 Agent 1
    participant AgentC as 工作 Agent 2
    participant Aggregator as 结果聚合器

    User->>API: POST /collaboration/tasks { mode: "supervisor", ... }
    API->>Collab: create_collab_task()
    Collab->>Collab: 拆解任务为子任务
    Collab->>AgentA: 分配监督角色
    AgentA->>Collab: 分解子任务列表

    par 并行执行
        Collab->>AgentB: 子任务 1
        Collab->>AgentC: 子任务 2
        AgentB-->>Collab: 结果 1
        AgentC-->>Collab: 结果 2
    end

    Collab->>Aggregator: 聚合结果
    Aggregator->>AgentA: 提交聚合结果
    AgentA-->>Collab: 最终输出
    Collab-->>API: 协作完成
    API-->>User: 返回最终结果
```

---

## 5. 数据流总图

```mermaid
flowchart LR
    subgraph INPUT["输入层"]
        USER[用户操作]
        SCAN[定时扫描器]
        EVENT[外部事件]
    end

    subgraph API["API/WS 网关"]
        REST[REST API]
        WS[WebSocket]
    end

    subgraph CORE["核心业务层"]
        AGENT[Agent 服务]
        MODEL[模型模板服务]
        SKILL[Skill 服务]
        MCP[MCP 服务]
        CHAT[对话引擎]
        COLLAB[协作引擎]
        SESSION[会话管理]
        TOKEN[Token 管理]
        MEMORY[记忆管理]
    end

    subgraph DATA["数据层"]
        PG[(PostgreSQL)]
        REDIS[(Redis)]
        QD[(Qdrant)]
        MINIO[(MinIO)]
    end

    subgraph OBS["可观测性"]
        PROM[Prometheus]
        GRAF[Grafana]
        LOKI[Loki]
        AUDIT[审计日志]
    end

    subgraph OUTPUT["输出层"]
        DASH[监控看板]
        EXPORT[导出/报告]
        ALERT[告警通知]
    end

    INPUT --> API
    API --> CORE
    CORE --> DATA
    CORE -.->|"指标"| OBS
    OBS --> OUTPUT
    EVENT -.->|"触发"| CORE
```

---

## 6. 事件总线事件列表

| 事件名称 | 发布时机 | 消费者 |
|---------|---------|--------|
| agent.created | Agent 创建后 | 审计服务、扫描器 |
| agent.deleted | Agent 删除后 | 会话服务、记忆服务 |
| agent.status_changed | Agent 状态变更 | 监控服务、看板 |
| model_template.created | 模板创建后 | 审计服务 |
| model_template.updated | 模板更新后 | 同步服务、绑定 Agent |
| model_template.synced | 同步完成后 | 审计服务 |
| skill.installed | Skill 安装后 | Agent 引擎 |
| skill.updated | Skill 更新后 | 绑定 Agent |
| skill.uninstalled | Skill 卸载后 | Agent 引擎 |
| mcp.registered | MCP 注册后 | Agent 引擎 |
| session.created | 会话创建 | Token 服务 |
| message.sent | 消息发送 | Token 服务、记忆服务 |
| backup.completed | 备份完成 | 监控服务 |
| health.alert | 健康检查异常 | 告警服务、看板 |
| scanner.found_changes | 扫描到变更 | 更新中心 |

---

> **文件版本：** v1.0 | **更新日期：** 2026-07-26
