# 项目启动调试报告

## 执行摘要

✅ **调试环境已准备完成**

- 调试时间: 2026-08-01 23:45
- 调试状态: 准备就绪
- 下一步: 启动服务器

---

## 检查结果

### 依赖检查
```
[OK] FastAPI
[OK] SQLAlchemy
[OK] Uvicorn
[OK] Pydantic
[OK] Redis
[OK] Qdrant
[OK] Cryptography
[OK] PyJWT
```

### 语法检查
```
[OK] 所有文件语法正确
[OK] 无导入错误
[OK] 无重复导入
```

---

## 启动命令

### 方式 1: 使用调试脚本 (推荐)
```bash
cd backend
python debug_server.py
```

### 方式 2: 手动启动
```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --log-level debug
```

---

## 访问地址

| 服务 | 地址 |
|------|------|
| API 文档 | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| 健康检查 | http://localhost:8000/health |
| API 根路径 | http://localhost:8000/api/v1 |

---

## 测试端点

### 1. 健康检查
```bash
curl http://localhost:8000/health
```

### 2. 认证接口
```bash
# 注册
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "password": "test123"}'

# 登录
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "password": "test123"}'
```

### 3. Agent 管理
```bash
# 获取 Agent 列表
curl http://localhost:8000/api/v1/agents

# 创建 Agent
curl -X POST http://localhost:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"name": "Test Agent", "description": "Test"}'
```

### 4. 模型配置
```bash
# 获取模型列表
curl http://localhost:8000/api/v1/models
```

---

## 数据库检查

### 检查数据库连接
```bash
cd backend
python -c "from app.db.session import async_session_factory; print('DB OK')"
```

### 检查表结构
```bash
cd backend
python -c "
from app.db.session import async_session_factory
from sqlalchemy import text

async def check():
    async with async_session_factory() as session:
        result = await session.execute(text('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = \'public\''))
        print(f'Tables: {result.scalar()}')

import asyncio
asyncio.run(check())
"
```

---

## 日志位置

- 应用日志: `backend/logs/app.log`
- 错误日志: `backend/logs/error.log`
- 访问日志: `backend/logs/access.log`

---

## 故障排查

### 问题 1: 端口被占用
```bash
# Windows
netstat -ano | findstr :8000
taskkill /F /PID <PID>

# 或修改端口
python -m uvicorn app.main:app --port 8001
```

### 问题 2: 数据库连接失败
```bash
# 检查 PostgreSQL 是否运行
# 检查 .env 配置
# 运行迁移
alembic upgrade head
```

### 问题 3: Redis 连接失败
```bash
# 检查 Redis 是否运行
# 检查 .env 配置
redis-cli ping
```

---

## 下一步行动

1. ✅ 运行 `python debug_server.py`
2. ⏳ 访问 http://localhost:8000/docs
3. ⏳ 测试关键 API 端点
4. ⏳ 检查数据库连接
5. ⏳ 检查 Redis 连接
6. ⏳ 运行测试套件

---

**报告生成时间**: 2026-08-01 23:45
**执行者**: AgnesCode
**状态**: ✅ 调试环境已准备，等待启动
