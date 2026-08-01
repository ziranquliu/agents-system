# 数据库迁移指南

> 文档版本: v1.0  
> 最后更新: 2026-08-01  
> 维护者: 后端开发团队

---

## 一、迁移文件结构

```
backend/alembic/
├── versions/
│   ├── 03a8f0110b12_initial_schema_v2.py    # 初始schema（基础表）
│   ├── 2a8f0110b13_optimize_indexes_v2.py   # 索引优化
│   └── 03a8f0110b13_add_missing_tables.py   # 新增缺失表 ← 本次整改
├── env.py                                    # 迁移环境配置
└── script.py.mako                           # 迁移脚本模板
```

---

## 二、迁移执行步骤

### 2.1 前置检查

```bash
# 1. 确保PostgreSQL服务运行中
docker ps | grep postgres

# 2. 检查当前迁移状态
cd backend
alembic current

# 3. 查看待执行的迁移
alembic check
```

### 2.2 执行迁移

```bash
# 方式一：执行所有待处理迁移
alembic upgrade head

# 方式二：升级到指定版本
alembic upgrade 03a8f0110b13

# 方式三：预览SQL（不实际执行）
alembic upgrade head --sql
```

### 2.3 验证结果

```bash
# 连接数据库
make psql

# 查看所有表
\dt

# 查看特定表结构
\d model_template_versions
\d agent_memories
\d token_usages

# 退出
\q
```

---

## 三、本次新增表清单

| 表名 | 说明 | 关键字段 |
|------|------|---------|
| `model_template_versions` | 模板版本历史 | template_id, version, config_snapshot |
| `model_template_bindings` | 模板-Agent绑定 | template_id, agent_id, sync_mode |
| `token_usages` | Token消耗记录 | user_id, agent_id, input_tokens |
| `token_budgets` | Token预算 | user_id, monthly_budget |
| `agent_memories` | Agent记忆 | agent_id, memory_type, content |
| `audit_logs` | 审计日志 | action, resource_type, detail |
| `backup_records` | 备份记录 | backup_type, status, file_path |
| `health_check_runs` | 健康检查 | agent_id, check_level, score |
| `collaboration_tasks` | 协作任务 | mode, goal, status |
| `notification_configs` | 通知配置 | notify_method, webhook_url |

---

## 四、回滚操作

⚠️ **警告**: 回滚操作会删除数据，请谨慎执行！

```bash
# 回滚一个版本
alembic downgrade -1

# 回滚到指定版本
alembic downgrade 03a8f0110b12

# 回滚到初始状态
alembic downgrade base
```

---

## 五、常见问题

### Q1: 迁移失败怎么办？

```bash
# 1. 查看详细错误
alembic upgrade head -v

# 2. 检查约束冲突
# 可能是字段类型不匹配或约束冲突

# 3. 手动修复后重新执行
alembic upgrade head
```

### Q2: 如何添加新字段？

```bash
# 1. 修改ORM模型
# backend/app/models/xxx.py

# 2. 生成新迁移
alembic revision --autogenerate -m "add_xxx_field"

# 3. 审查生成的SQL
# 确认无误后执行
alembic upgrade head
```

### Q3: 分区表如何处理？

```sql
-- audit_logs 是分区表，按月分区
CREATE TABLE audit_logs_y2026m08 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
```

---

## 六、最佳实践

1. **迁移前备份**
   ```bash
   pg_dump agent_system > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **小步提交**
   - 每次迁移只做一件事
   - 清晰的commit message

3. **测试环境先行**
   - 先在dev环境验证
   - 确认无误后再升级生产

4. **保留降级能力**
   - 编写downgrade()函数
   - 测试回滚流程
