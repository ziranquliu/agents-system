# 权限模型设计（RBAC）

> 配套文档：智能体管理系统构建计划书 v1.7 — 第9章
> 模型：基于角色的访问控制（RBAC） + 工作空间数据隔离

---

## 1. 角色定义

| 角色 | 层级 | 说明 |
|------|------|------|
| **super_admin** | 系统级 | 系统管理员，拥有全部权限 |
| **workspace_admin** | 空间级 | 工作空间管理员，管理空间内的所有资源 |
| **workspace_editor** | 空间级 | 工作空间编辑者，可创建/修改资源 |
| **workspace_viewer** | 空间级 | 工作空间只读者，仅可查看 |
| **agent_user** | 资源级 | Agent 使用者，仅可使用被分配的 Agent 对话 |

---

## 2. 权限矩阵

### 2.1 系统级权限（super_admin）

| 权限 | 说明 |
|------|------|
| system.manage | 系统配置管理 |
| workspace.* | 管理所有工作空间 |
| user.* | 用户 CRUD |
| audit.view_all | 查看全平台审计日志 |
| admin.* | 管理后台所有功能 |

### 2.2 工作空间级权限

| 权限 | admin | editor | viewer |
|------|-------|--------|--------|
| workspace.view | ✅ | ✅ | ✅ |
| workspace.update | ✅ | ✅ | ❌ |
| workspace.delete | ✅ | ❌ | ❌ |
| workspace.members | ✅ | ❌ | ❌ |

### 2.3 智能体权限

| 权限 | admin | editor | viewer |
|------|-------|--------|--------|
| agent.create | ✅ | ✅ | ❌ |
| agent.list | ✅ | ✅ | ✅ |
| agent.view | ✅ | ✅ | ✅ |
| agent.update | ✅ | ✅ | ❌ |
| agent.delete | ✅ | ✅ | ❌ |
| agent.duplicate | ✅ | ✅ | ❌ |
| agent.change_status | ✅ | ✅ | ❌ |

### 2.4 模型配置模板

| 权限 | admin | editor | viewer |
|------|-------|--------|--------|
| model_template.create | ✅ | ✅ | ❌ |
| model_template.list | ✅ | ✅ | ✅ |
| model_template.view | ✅ | ✅ | ✅ |
| model_template.update | ✅ | ✅ | ❌ |
| model_template.delete | ✅ | ✅ | ❌ |
| model_template.test | ✅ | ✅ | ❌ |
| model_template.sync | ✅ | ✅ | ❌ |
| model_template.rollback | ✅ | ✅ | ❌ |

### 2.5 Skill / MCP

| 权限 | admin | editor | viewer |
|------|-------|--------|--------|
| skill.install | ✅ | ✅ | ❌ |
| skill.uninstall | ✅ | ✅ | ❌ |
| skill.bind_to_agent | ✅ | ✅ | ❌ |
| skill.sync | ✅ | ✅ | ❌ |
| mcp.register | ✅ | ✅ | ❌ |
| mcp.unregister | ✅ | ✅ | ❌ |
| mcp.bind_to_agent | ✅ | ✅ | ❌ |

### 2.6 会话与对话

| 权限 | admin | editor | viewer | agent_user |
|------|-------|--------|--------|------------|
| session.list | ✅ | ✅ | ✅ | ✅（自己的） |
| session.view | ✅ | ✅ | ✅ | ✅（自己的） |
| session.delete | ✅ | ✅ | ❌ | ❌ |
| session.export | ✅ | ✅ | ✅ | ✅ |
| session.chat | ✅ | ✅ | ❌ | ✅（被授权） |

### 2.7 监控运维

| 权限 | admin | editor | viewer |
|------|-------|--------|--------|
| dashboard.view | ✅ | ✅ | ✅ |
| health.view | ✅ | ✅ | ✅ |
| health.trigger_check | ✅ | ✅ | ❌ |
| ops.auto_scale | ✅ | ✅ | ❌ |
| ops.self_heal | ✅ | ✅ | ❌ |
| backup.create | ✅ | ✅ | ❌ |
| backup.restore | ✅ | ✅ | ❌ |

### 2.8 审计

| 权限 | admin | editor | viewer |
|------|-------|--------|--------|
| audit.logs | ✅ | ✅ | ✅ |
| audit.export | ✅ | ✅ | ✅ |
| audit.view_detail | ✅ | ❌ | ❌ |

---

## 3. 数据隔离策略

```
super_admin → 看到所有工作空间的数据
workspace_admin → 只看到自己工作空间的数据
workspace_editor → 只看到自己工作空间的数据
workspace_viewer → 只看到自己工作空间的数据（只读）
agent_user → 只看到被授权使用的 Agent 的会话数据
```

所有 API 查询强制加入 `workspace_id` 过滤：

```python
# 伪代码
async def list_agents(workspace_id: UUID, current_user: User):
    if current_user.role == 'super_admin':
        # 可查看所有空间
        pass
    else:
        # 只能查看自己空间的
        query = query.where(Agent.workspace_id == workspace_id)
```

---

## 4. 数据库设计

### roles（角色表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| name | VARCHAR(64) | UNIQUE，角色名称 |
| description | TEXT | |
| is_system | BOOLEAN | 系统内置角色 |

### permissions（权限表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| code | VARCHAR(128) | UNIQUE，权限编码如 `agent.create` |
| name | VARCHAR(128) | 权限名称 |
| module | VARCHAR(64) | 所属模块 |

### role_permissions（角色权限关联）

| 字段 | 类型 | 说明 |
|------|------|------|
| role_id | UUID | FK→roles.id |
| permission_id | UUID | FK→permissions.id |
| PK(role_id, permission_id) | | |

### user_workspace_roles（用户-工作空间-角色）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| user_id | UUID | FK→users.id |
| workspace_id | UUID | FK→workspaces.id |
| role_id | UUID | FK→roles.id |
| UNIQUE(user_id, workspace_id) | | |

---

## 5. API 鉴权中间件

```python
# 伪代码：权限校验装饰器
@router.get("/agents")
@require_permission("agent.list")
async def list_agents():
    ...

# 伪代码：中间件流程
1. 提取 JWT Token → 解析 user_id + role
2. 如果是 super_admin → 放行全部
3. 提取 workspace_id（URL 路径参数）
4. 查询 user_workspace_roles 获取角色
5. 查询 role_permissions 获取权限
6. 校验当前接口所需的 permission
7. 通过 → 继续；不通过 → 403
```

---

> **文件版本：** v1.0 | **更新日期：** 2026-07-26
