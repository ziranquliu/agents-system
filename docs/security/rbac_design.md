# RBAC权限模型设计

> 文档版本: v1.0  
> 最后更新: 2026-08-01

---

## 一、角色定义

### 1.1 系统内置角色

| 角色 | 标识符 | 权限范围 | 说明 |
|------|--------|---------|------|
| **超级管理员** | `admin` | 全局 | 所有资源的全权访问 |
| **工作空间管理员** | `workspace_admin` | 所属工作空间 | 管理空间内所有资源 |
| **编辑器** | `editor` | 所属工作空间 | 创建/编辑资源，不能删除 |
| **查看者** | `viewer` | 所属工作空间 | 只读访问 |
| **API用户** | `api_user` | 有限API | 仅API调用权限 |

### 1.2 角色层级

```
admin (全局)
    │
    ├── workspace_admin
    │       │
    │       ├── editor
    │       │       │
    │       │       ├── viewer
    │       │
    │       └── api_user
    │
    └── guest (受限)
```

---

## 二、权限矩阵

### 2.1 Agent管理权限

| 操作 | admin | workspace_admin | editor | viewer | api_user |
|------|-------|-----------------|--------|--------|----------|
| 列表Agent | ✅ | ✅ | ✅ | ✅ | ✅ |
| 查看详情 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 创建Agent | ✅ | ✅ | ✅ | ❌ | ❌ |
| 更新Agent | ✅ | ✅ | ✅ | ❌ | ❌ |
| 删除Agent | ✅ | ✅ | ❌ | ❌ | ❌ |
| 复制Agent | ✅ | ✅ | ✅ | ❌ | ❌ |
| 启用/停用 | ✅ | ✅ | ✅ | ❌ | ❌ |

### 2.2 模型模板权限

| 操作 | admin | workspace_admin | editor | viewer | api_user |
|------|-------|-----------------|--------|--------|----------|
| 列表模板 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 查看详情 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 创建模板 | ✅ | ✅ | ✅ | ❌ | ❌ |
| 更新模板 | ✅ | ✅ | ✅ | ❌ | ❌ |
| 删除模板 | ✅ | ✅ | ❌ | ❌ | ❌ |
| 测试连接 | ✅ | ✅ | ✅ | ❌ | ❌ |
| 版本回滚 | ✅ | ✅ | ✅ | ❌ | ❌ |

### 2.3 工作空间权限

| 操作 | admin | workspace_admin | editor | viewer | api_user |
|------|-------|-----------------|--------|--------|----------|
| 创建工作空间 | ✅ | ❌ | ❌ | ❌ | ❌ |
| 邀请成员 | ✅ | ✅ | ❌ | ❌ | ❌ |
| 移除成员 | ✅ | ✅ | ❌ | ❌ | ❌ |
| 修改设置 | ✅ | ✅ | ❌ | ❌ | ❌ |
| 删除空间 | ✅ | ✅ | ❌ | ❌ | ❌ |

---

## 三、工作空间隔离

### 3.1 数据隔离策略

```python
# 所有涉及工作空间的查询必须携带workspace_id过滤
query = select(Agent).where(
    Agent.workspace_id == current_workspace_id
)
```

### 3.2 跨工作空间访问控制

| 场景 | 处理逻辑 |
|------|---------|
| 普通用户访问其他空间资源 | 返回403 Forbidden |
| admin访问所有空间 | 允许（全局视角） |
| workspace_admin仅访问自己空间 | 限制scope |

---

## 四、实现方式

### 4.1 装饰器用法

```python
from app.core.rbac import PermissionLevels

@router.get("/agents")
@PermissionLevels.reader()
async def list_agents(...):
    """需要viewer及以上角色"""
    ...

@router.post("/agents")
@PermissionLevels.editor()
async def create_agent(...):
    """需要editor及以上角色"""
    ...

@router.delete("/agents/{id}")
@PermissionLevels.owner()
async def delete_agent(...):
    """需要owner或admin角色"""
    ...
```

### 4.2 依赖注入用法

```python
from app.core.rbac import require_workspace_permission

@router.post("/agents")
async def create_agent(
    data: AgentCreate,
    user: User = Depends(require_workspace_permission(["editor", "admin"])),
    db: AsyncSession = Depends(get_db)
):
    ...
```

---

## 五、安全最佳实践

### 5.1 Token安全

```python
# JWT claims中必须包含
{
    "sub": user_id,
    "role": user_role,
    "workspace_id": workspace_id,  # 当前工作空间
    "exp": expiration_time
}
```

### 5.2 权限缓存

对于高频权限检查，建议缓存结果：

```python
from core.cache import cache

@cache(ttl=300)  # 5分钟缓存
async def check_permission(user_id: str, resource: str, action: str):
    # 实际权限检查逻辑
    ...
```

---

## 六、审计追踪

所有权限相关操作记录到audit_logs表：

```python
# 记录权限变更
await audit_service.log(
    action="permission_change",
    resource_type="role",
    resource_id=user_id,
    detail={"from_role": "editor", "to_role": "admin"},
    user_id=current_user.id
)
```
