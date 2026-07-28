# API 接口规范

> 配套文档：智能体管理系统构建计划书 v1.7 — 第9章
> 基础路径：`/api/v1`
> 认证方式：Bearer JWT Token
> 响应格式：`{"code": 0, "data": {...}, "message": "success"}`

---

## 1. 通用约定

### 1.1 响应格式

```json
// 成功
{ "code": 0, "data": { ... }, "message": "success" }
// 列表
{ "code": 0, "data": { "items": [...], "total": 100, "page": 1, "page_size": 20 }, "message": "success" }
// 错误
{ "code": 40001, "data": null, "message": "参数校验失败" }
```

### 1.2 OpenAPI / Swagger 自动文档

基于 FastAPI 的特性，自动生成两套在线 API 文档：

| 文档 | 路径 | 用途 |
|------|------|------|
| **Swagger UI** | `/docs` | 交互式 API 测试（前后端联调） |
| **ReDoc** | `/redoc` | 静态 API 文档浏览（对外发布） |

**自动生成机制：**
- 所有 Pydantic Schema 自动转为 OpenAPI 3.1 规范的 JSON
- 接口注释、参数说明、示例、错误码自动汇入
- 启动应用后访问 `/openapi.json` 可获取完整规范

**配置建议：**
```python
app = FastAPI(
    title="智能体管理系统 API",
    version="1.8.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    description="..."
)
```

### 1.3 HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 409 | 冲突（如重名） |
| 422 | 参数校验失败 |
| 500 | 服务端错误 |

### 1.3 分页参数

所有列表接口统一接受：`?page=1&page_size=20&sort_by=created_at&sort_order=desc`

### 1.4 统一异常处理

全局异常处理器拦截所有未捕获异常，统一返回标准格式：

| 异常类型 | 处理策略 | HTTP 状态码 | 错误码示例 |
|---------|---------|------------|-----------|
| `RequestValidationError` | Pydantic 参数校验失败 | 422 | 20-00-01 |
| `HTTPException` | 业务异常（指定 code+message） | 自定义 | 自定义 |
| `PermissionError` | RBAC 权限校验失败 | 403 | 30-00-02 |
| `TokenExpiredError` | JWT 过期 | 401 | 30-00-03 |
| `IntegrityError` | DB 唯一约束冲突 | 409 | 20-00-03 |
| `TimeoutError` | 上游模型调用超时 | 504 | 20-15-04 |
| `Exception`（兜底） | 未预期错误，记录堆栈 | 500 | 10-00-01 |

**实现示例：**

```python
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"code": 200001, "data": None,
                 "message": "参数校验失败",
                 "detail": exc.errors()}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception(f"未处理异常: {exc}", extra={"path": request.url.path})
    return JSONResponse(
        status_code=500,
        content={"code": 100001, "data": None, "message": "内部服务器错误"}
    )
```

### 1.5 API 限流策略

采用 Redis + 令牌桶算法，按用户/工作空间/IP 三级限流：

| 级别 | 维度 | 限流规则 | 适用场景 |
|------|------|---------|---------|
| **L1 用户级** | user_id | 60 次/分钟 | 普通接口 |
| **L2 接口级** | user_id + API path | 写操作 10次/分钟，读操作 60次/分钟 | 创建/删除类敏感操作 |
| **L3 工作空间级** | workspace_id | 1000 次/分钟 | 防止单空间拖垮系统 |
| **L4 IP 级** | client_ip | 100 次/分钟 | 未登录接口（登录/注册） |
| **对话接口** | agent_id | 10 次/分钟 | 防止模型过载 |
| **大模型调用** | agent_id + model | 与上游 Provider 限流联动 | 模型成本控制 |

**响应头：**
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1785039300
Retry-After: 30  # 触发限流时返回
```

**实现：** FastAPI 中间件 + Redis 原子操作（INCR + EXPIRE）实现令牌桶。

---

## 2. 认证模块

### POST /auth/login

登录获取 Token。

```json
// Request
{ "username": "admin", "password": "***" }
// Response
{ "token": "eyJhbGci...", "expires_in": 86400, "user": { "id": "uuid", "username": "admin", "role": "admin" } }
```

### POST /auth/logout

注销 Token。

### GET /auth/me

获取当前用户信息。

### PUT /auth/password

修改密码。

```json
{ "old_password": "***", "new_password": "***" }
```

---

## 3. 工作空间

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /workspaces | 列出工作空间 |
| POST | /workspaces | 创建工作空间 |
| GET | /workspaces/{id} | 获取详情 |
| PUT | /workspaces/{id} | 更新 |
| DELETE | /workspaces/{id} | 删除 |
| GET | /workspaces/{id}/stats | 获取统计信息 |

### POST /workspaces

```json
{ "name": "我的空间", "description": "..." }
```

---

## 4. 智能体管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /workspaces/{ws_id}/agents | 列出 Agent |
| POST | /workspaces/{ws_id}/agents | 创建 Agent |
| GET | /agents/{id} | 获取 Agent 详情 |
| PUT | /agents/{id} | 更新 Agent |
| DELETE | /agents/{id} | 删除 Agent |
| PATCH | /agents/{id}/status | 切换状态 |
| POST | /agents/{id}/duplicate | 复制 Agent |

### POST /workspaces/{ws_id}/agents

```json
{
  "name": "客服助手",
  "system_prompt": "你是一个友好的客服助手...",
  "description": "用于处理用户咨询",
  "temperature": 0.7,
  "max_tokens": 2048,
  "model_template_id": "uuid",     // 模型配置模板（可选）
  "model_overrides": {              // 参数覆盖（可选）
    "temperature": 0.3
  },
  "skill_ids": ["uuid1", "uuid2"], // 绑定 Skill
  "mcp_ids": ["uuid1"]             // 绑定 MCP
}

// Response 201
{
  "id": "uuid",
  "name": "客服助手",
  "status": "inactive",
  "model_binding": {
    "template_id": "uuid",
    "template_name": "GPT-4o 模板",
    "override_params": { "temperature": 0.3 }
  },
  "skills": [{ "id": "uuid", "name": "联网搜索" }],
  "mcps": [{ "id": "uuid", "name": "文件读取" }]
}
```

### GET /agents/{id} — 返回详情

```json
{
  "id": "uuid",
  "name": "客服助手",
  "status": "active",
  "system_prompt": "...",
  "description": "...",
  "config": { "temperature": 0.7, "max_tokens": 2048 },
  "model_binding": { "template_id": "uuid", "template_name": "GPT-4o", "provider": "openai" },
  "skills": [{ "id": "uuid", "name": "联网搜索", "version": "1.2.0" }],
  "mcps": [{ "id": "uuid", "name": "文件读取" }],
  "stats": { "session_count": 128, "token_usage_7d": 50000 },
  "created_at": "2026-07-26T00:00:00Z"
}
```

---

## 5. 模型配置模板

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /workspaces/{ws_id}/model-templates | 列出模板 |
| POST | /workspaces/{ws_id}/model-templates | 创建模板 |
| GET | /model-templates/{id} | 获取模板 |
| PUT | /model-templates/{id} | 更新模板 |
| DELETE | /model-templates/{id} | 删除模板 |
| GET | /model-templates/{id}/versions | 版本列表 |
| POST | /model-templates/{id}/test | 测试连接 |
| POST | /model-templates/{id}/rollback | 回滚到指定版本 |
| GET | /model-templates/{id}/bound-agents | 查看绑定的 Agent |
| POST | /model-templates/{id}/sync | 手动同步到绑定 Agent |

### POST /workspaces/{ws_id}/model-templates

```json
{
  "name": "GPT-4o 对话模板",
  "provider": "openai",
  "model_name": "gpt-4o",
  "api_base_url": "https://api.openai.com/v1",
  "api_key": "sk-...",
  "category": "对话模型",
  "default_params": { "temperature": 0.7, "max_tokens": 4096, "top_p": 0.9 }
}

// Response 201
{
  "id": "uuid",
  "name": "GPT-4o 对话模板",
  "provider": "openai",
  "model_name": "gpt-4o",
  "category": "对话模型",
  "status": "draft",
  "version": 1,
  "test_status": "untested"
}
```

### PUT /model-templates/{id}

```json
// 更新后自动创建新版本，触发同步通知
{
  "model_name": "gpt-4o-mini",
  "default_params": { "temperature": 0.5 }
}
// Response — 返回新版本信息
{
  "id": "uuid",
  "version": 2,
  "changelog": "切换模型为 gpt-4o-mini，降低 temperature",
  "bound_agents_count": 3,
  "sync_status": "pending"
}
```

### POST /model-templates/{id}/test

```json
// Response
{ "status": "passed", "latency_ms": 320, "model_info": { "name": "gpt-4o", "context_length": 128000 } }
```

---

## 6. Skill 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /workspaces/{ws_id}/skills | 列出 Skill |
| POST | /workspaces/{ws_id}/skills | 安装/创建 Skill |
| GET | /skills/{id} | 获取 Skill 详情 |
| PUT | /skills/{id} | 更新 |
| DELETE | /skills/{id} | 卸载 |
| POST | /skills/{id}/install-to-agents | 批量安装到多个 Agent |
| POST | /skills/{id}/sync-to-agents | 同步到指定 Agent |

### POST /skills/{id}/install-to-agents

```json
{ "agent_ids": ["uuid1", "uuid2", "uuid3"], "params": { "agent1_uuid": { "key": "val" } } }
```

---

## 7. MCP 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /workspaces/{ws_id}/mcps | 列出 MCP |
| POST | /workspaces/{ws_id}/mcps | 注册 MCP |
| GET | /mcps/{id} | 获取详情 |
| PUT | /mcps/{id} | 更新 |
| DELETE | /mcps/{id} | 删除 |
| POST | /mcps/{id}/register-to-agents | 批量注册到 Agent |
| POST | /mcps/{id}/sync-to-agents | 同步到 Agent |

---

## 8. 会话管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /agents/{agent_id}/sessions | 会话列表 |
| POST | /agents/{agent_id}/sessions | 创建会话 |
| GET | /sessions/{id} | 获取会话详情 |
| DELETE | /sessions/{id} | 删除会话 |
| GET | /sessions/{id}/messages | 获取消息历史 |
| POST | /sessions/{id}/messages | 发送消息（流式） |
| POST | /sessions/{id}/export | 导出会话 |
| POST | /sessions/batch-export | 批量导出 |

### POST /sessions/{id}/messages

```json
// Request
{ "content": "你好，帮我查一下天气", "role": "user" }

// Response (SSE 流式)
// data: {"type": "token", "content": "好的"}
// data: {"type": "token", "content": "，正在查询..."}
// data: {"type": "done", "message_id": "uuid", "token_count": 128}
```

### POST /sessions/{id}/export

```json
{ "format": "markdown", "include_meta": true }
// Response: 文件下载
```

---

## 9. Token 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /workspaces/{ws_id}/token-usage | Token 消耗统计 |
| GET | /workspaces/{ws_id}/token-usage/trend | 趋势图数据 |
| GET | /workspaces/{ws_id}/token-usage/by-agent | 按 Agent 汇总 |
| GET | /workspaces/{ws_id}/token-usage/by-model | 按模型汇总 |
| PUT | /workspaces/{ws_id}/token-budget | 设置预算 |
| GET | /workspaces/{ws_id}/token-budget | 获取预算 |

---

## 10. 知识库

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /workspaces/{ws_id}/knowledge-bases | 列表 |
| POST | /workspaces/{ws_id}/knowledge-bases | 创建 |
| GET | /knowledge-bases/{id} | 详情 |
| POST | /knowledge-bases/{id}/documents | 上传文档 |
| DELETE | /knowledge-bases/{id}/documents/{doc_id} | 删除文档 |
| POST | /knowledge-bases/{id}/search | 搜索知识 |

---

## 11. Agent 记忆

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /agents/{id}/memories | 记忆列表 |
| POST | /agents/{id}/memories | 手动添加记忆 |
| DELETE | /agents/{id}/memories/{mem_id} | 删除记忆 |
| POST | /agents/{id}/memories/search | 搜索记忆 |
| POST | /agents/{id}/memories/forget | 触发遗忘 |

---

## 12. 监控与运维

### 12.1 监控看板

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /workspaces/{ws_id}/dashboard | 总览大盘数据 |
| GET | /workspaces/{ws_id}/dashboard/realtime | 实时指标 |
| GET | /workspaces/{ws_id}/dashboard/comparison | 对比视图 |

### 12.2 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /agents/{id}/health | Agent 健康状态 |
| POST | /agents/{id}/health/check | 触发检查 |
| GET | /workspaces/{ws_id}/health/summary | 健康汇总 |

### 12.3 自动化运维

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /workspaces/{ws_id}/ops/auto-scale | 触发自动扩缩容 |
| POST | /workspaces/{ws_id}/ops/self-heal/{agent_id} | 触发自愈 |

---

## 13. 备份恢复

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /workspaces/{ws_id}/backups | 创建备份 |
| GET | /workspaces/{ws_id}/backups | 备份列表 |
| POST | /workspaces/{ws_id}/backups/{id}/restore | 恢复 |
| DELETE | /workspaces/{ws_id}/backups/{id} | 删除备份 |

---

## 14. 操作审计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /workspaces/{ws_id}/audit-logs | 审计日志查询 |
| GET | /workspaces/{ws_id}/audit-logs/stats | 审计统计 |
| POST | /workspaces/{ws_id}/audit-logs/export | 导出审计报告 |

支持查询参数：`?action=create&resource_type=agent&user_id=uuid&from=2026-07-01&to=2026-07-26`

---

## 15. 多 Agent 协作

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /workspaces/{ws_id}/collaboration/tasks | 创建协作任务 |
| GET | /workspaces/{ws_id}/collaboration/tasks | 任务列表 |
| GET | /collaboration/tasks/{id} | 任务详情 |
| POST | /collaboration/tasks/{id}/cancel | 取消任务 |

### POST /workspaces/{ws_id}/collaboration/tasks

```json
{
  "mode": "supervisor",         // supervisor/team/pipeline/debate/competition
  "goal": "分析这份文档并生成摘要",
  "agents": ["uuid1", "uuid2"],
  "config": {
    "supervisor_id": "uuid1",
    "max_rounds": 3,
    "timeout_seconds": 300
  }
}
```

---

## 16. 扫描器与更新

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /workspaces/{ws_id}/scanner/scan | 触发扫描 |
| GET | /workspaces/{ws_id}/scanner/results | 扫描结果 |
| GET | /workspaces/{ws_id}/updates | 可用更新列表 |
| POST | /workspaces/{ws_id}/updates/{id}/apply | 应用更新 |
| POST | /workspaces/{ws_id}/updates/batch-apply | 批量更新 |

---

## 17. 市场

### 17.1 Agent 市场

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /market/agents | 浏览 Agent 模板 |
| GET | /market/agents/{id} | 模板详情 |
| POST | /market/agents/{id}/install | 安装模板 |
| POST | /market/agents | 上传模板 |

### 17.2 Skill 市场

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /market/skills | 浏览 Skill |
| POST | /market/skills/{id}/install | 安装 Skill |
| POST | /market/skills | 上传 |

### 17.3 MCP 市场

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /market/mcps | 浏览 MCP 服务 |
| POST | /market/mcps/{id}/connect | 一键接入 |

### 17.4 模型市场

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /market/models | 浏览模型 |
| GET | /market/models/{id} | 模型详情 |
| POST | /market/models/{id}/connect | 快速接入（创建模板） |

---

## 18. WebSocket 接口

### WS /ws/v1/chat/{session_id}

实时对话流式接口。

```json
// Client → Server
{ "type": "message", "content": "你好" }
{ "type": "cancel" }

// Server → Client (SSE over WS)
{ "type": "token", "content": "你" }
{ "type": "token", "content": "好" }
{ "type": "tool_call", "tool": "search", "args": {"q": "天气"} }
{ "type": "done", "message_id": "uuid" }
```

### WS /ws/v1/dashboard/{workspace_id}

实时监控看板推送。

```json
{ "type": "metric", "name": "active_agents", "value": 12, "timestamp": "..." }
{ "type": "metric", "name": "qps", "value": 3.5 }
{ "type": "alert", "level": "warning", "message": "Agent 客服助手 健康分低于60" }
```

---

## 19. 接口分组总览

| 模块 | 前缀 | 接口数 |
|------|------|--------|
| 认证 | /auth | 4 |
| 工作空间 | /workspaces | 6 |
| 智能体 | /agents | 8 |
| 模型模板 | /model-templates | 10 |
| Skill | /skills | 7 |
| MCP | /mcps | 7 |
| 会话 | /sessions | 8 |
| Token | /token-usage | 6 |
| 知识库 | /knowledge-bases | 6 |
| 记忆 | /agent-memories | 5 |
| 监控 | /dashboard, /health, /ops | 8 |
| 备份 | /backups | 4 |
| 审计 | /audit-logs | 3 |
| 协作 | /collaboration | 4 |
| 扫描更新 | /scanner, /updates | 5 |
| 市场 | /market | 10 |
| WebSocket | /ws | 2 |
| **合计** | | **~103 个接口** |

---

> **文件版本：** v1.0 | **配套计划书：** v1.7 | **更新日期：** 2026-07-26
