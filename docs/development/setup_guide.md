# 环境搭建指南

> 文档版本: v1.0  
> 最后更新: 2026-08-01

---

## 一、前置要求

### 1.1 系统要求

| 组件 | 最低版本 | 推荐版本 |
|------|---------|---------|
| Python | 3.11+ | 3.11.x |
| Node.js | 20+ | 20.x LTS |
| Docker | 24+ | 24.x |
| Docker Compose | 2.20+ | 2.24.x |

### 1.2 硬件要求

- CPU: 4核+
- 内存: 8GB+
- 磁盘: 20GB可用空间

---

## 二、快速启动

### 2.1 克隆项目

```bash
git clone <repository-url>
cd agents-system
```

### 2.2 配置环境变量

```bash
# 复制模板
cp backend/.env.example backend/.env

# 编辑配置文件
code backend/.env  # 或使用任意编辑器
```

**关键配置项**:

```ini
# 数据库
DATABASE_URL=postgresql+asyncpg://agent:agent_pass@localhost:5432/agent_system

# Redis
REDIS_URL=redis://localhost:6379/0

# Qdrant (向量数据库)
QDRANT_URL=http://localhost:6333

# JWT
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# 加密密钥 (用于API Key加密存储)
ENCRYPTION_SECRET_KEY=your-encryption-key-min-32-chars

# CSRF
CSRF_SECRET_KEY=your-csrf-secret-key
```

### 2.3 启动基础设施

```bash
# 启动所有服务
make infra-up

# 查看状态
make infra-logs

# 单个服务
docker compose -f docker/docker-compose.dev.yml up -d postgres redis qdrant
```

### 2.4 安装依赖

```bash
# 后端
make backend-install

# 前端
make frontend-install
```

### 2.5 执行数据库迁移

```bash
make migrate
```

### 2.6 启动开发服务器

```bash
# 终端1: 后端
make backend-dev

# 终端2: 前端
make frontend-dev
```

### 2.7 访问应用

- 前端: http://localhost:5173
- API文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

---

## 三、Docker服务详情

### 3.1 PostgreSQL

```yaml
# docker/docker-compose.dev.yml
agent-postgres:
  image: postgres:17
  environment:
    POSTGRES_USER: agent
    POSTGRES_PASSWORD: agent_pass
    POSTGRES_DB: agent_system
  ports:
    - "5432:5432"
  volumes:
    - ./data/postgres:/var/lib/postgresql/data
```

### 3.2 Redis

```yaml
agent-redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
  volumes:
    - ./data/redis:/data
```

### 3.3 Qdrant

```yaml
agent-qdrant:
  image: qdrant/qdrant:latest
  ports:
    - "6333:6333"
    - "6334:6334"
  volumes:
    - ./data/qdrant:/qdrant/storage
```

---

## 四、常用命令

```bash
# 查看所有命令
make help

# 停止服务
make infra-down

# 重启服务
make infra-restart

# 进入PostgreSQL
make psql

# 进入Redis
make redis-cli

# 清理临时文件
make clean
```

---

## 五、故障排查

### 5.1 端口冲突

```bash
# 查看占用端口的进程
netstat -ano | findstr :5432
netstat -ano | findstr :6379
netstat -ano | findstr :6333

# 修改docker-compose.yml中的端口映射
ports:
  - "5433:5432"  # 改为5433
```

### 5.2 数据库连接失败

```bash
# 检查PostgreSQL是否运行
docker ps | grep postgres

# 查看日志
docker logs agent-postgres

# 重置数据（注意：会清空所有数据）
rm -rf data/postgres
make infra-up
make migrate
```

### 5.3 后端启动失败

```bash
# 检查依赖
pip install -r requirements.txt

# 查看详细错误
python -m uvicorn app.main:app --reload --log-level debug
```

### 5.4 前端启动失败

```bash
# 清理缓存重新安装
cd frontend
rm -rf node_modules package-lock.json
npm install

# 开发模式启动
npm run dev
```

---

## 六、IDE配置

### 6.1 VS Code

推荐插件:
- Python (ms-python.python)
- Pylance
- Black Formatter
- ESLint
- Prettier
- Docker

### 6.2 代码格式化

```ini
# .prettierrc
{
  "semi": false,
  "trailingComma": "es5",
  "singleQuote": true,
  "tabWidth": 2
}
```

```ini
# .black
[tool.black]
line-length = 88
target-version = ['py311']
```

---

## 七、开发工作流

```mermaid
graph LR
    A[clone项目] --> B[配置.env]
    B --> C[启动Docker]
    C --> D[执行迁移]
    D --> E[启动后端]
    E --> F[启动前端]
    F --> G[开始开发]
```
