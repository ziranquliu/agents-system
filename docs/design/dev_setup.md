# 开发环境搭建指南

> 配套文档：智能体管理系统构建计划书 v1.7 — 第9章

---

## 1. 技术栈版本要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | ≥3.11 | 后端开发语言 |
| Node.js | ≥20 LTS | 前端运行时 |
| pnpm | ≥9 | 前端包管理 |
| PostgreSQL | ≥16 | 主数据库 |
| Redis | ≥7 | 缓存/消息队列 |
| Qdrant | ≥1.10 | 向量数据库 |
| MinIO | LATEST | 对象存储 |
| Docker | ≥24 | 容器化 |
| Docker Compose | ≥2.24 | 编排 |

---

## 2. 本地开发环境搭建

### 2.1 克隆仓库

```bash
git clone https://github.com/xxx/agent-management-system.git
cd agent-management-system
```

### 2.2 启动依赖服务

```bash
# 使用 Docker Compose 启动 PostgreSQL + Redis + Qdrant + MinIO
docker compose -f docker-compose.dev.yml up -d

# 验证服务状态
docker compose ps
```

### 2.3 后端环境配置

```bash
cd backend

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 安装依赖
pip install -r requirements-dev.txt

# 复制环境变量
cp .env.example .env
# 编辑 .env 填写本地配置（数据库连接/API Key等）

# 初始化数据库
alembic upgrade head

# 填充种子数据
python -m scripts.seed

# 启动开发服务器（热重载）
uvicorn app.main:app --reload --port 8000
```

### 2.4 前端环境配置

```bash
cd frontend

# 安装依赖
pnpm install

# 复制环境变量
cp .env.example .env.local

# 启动开发服务器
pnpm dev
# 访问 http://localhost:5173
```

---

## 3. 环境变量说明

### 3.1 后端 .env

```env
# 应用
APP_NAME=Agent Management System
APP_VERSION=1.7.0
DEBUG=true
SECRET_KEY=your-secret-key-here

# 数据库
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/agent_mgmt
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Redis
REDIS_URL=redis://localhost:6379/0

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=agent-files

# JWT
JWT_SECRET_KEY=your-jwt-secret
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# CORS
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# 日志
LOG_LEVEL=DEBUG
LOG_FILE=logs/app.log
```

### 3.2 前端 .env.local

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws/v1
VITE_APP_TITLE=智能体管理系统
```

---

## 4. Docker Compose 开发环境

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: agent_mgmt
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin

volumes:
  pgdata:
  qdrant_data:
  minio_data:
```

---

## 5. 代码规范

### 5.1 后端

| 工具 | 用途 | 命令 |
|------|------|------|
| Ruff | 代码检查+格式化 | `ruff check . && ruff format .` |
| mypy | 类型检查 | `mypy app/` |
| pytest | 测试 | `pytest -v` |
| pre-commit | 提交前检查 | `pre-commit run --all-files` |

```bash
# 安装 pre-commit
pip install pre-commit
pre-commit install

# 配置在 .pre-commit-config.yaml 中
```

### 5.2 前端

| 工具 | 用途 | 命令 |
|------|------|------|
| ESLint | 代码检查 | `pnpm lint` |
| Prettier | 格式化 | `pnpm format` |
| Vitest | 测试 | `pnpm test` |
| TypeScript | 类型检查 | `pnpm typecheck` |

---

## 6. Git 分支策略

```
main          → 生产分支（保护）
├── develop   → 开发主分支
│   ├── feat/xxx    → 功能分支
│   ├── fix/xxx     → 修复分支
│   └── refactor/xxx → 重构分支
├── release/* → 发布候选分支
└── hotfix/*  → 紧急修复分支

命名规范：
- feat/model-template-sync
- fix/agent-create-validation
- refactor/chat-engine
```

---

## 7. 常用命令速查

```bash
# 后端
uvicorn app.main:app --reload           # 启动 dev
alembic revision --autogenerate -m "msg" # 生成迁移
alembic upgrade head                     # 执行迁移
pytest -v --cov=app                      # 测试+覆盖率
ruff check . --fix                       # 自动修复

# 前端
pnpm dev                                 # 启动 dev
pnpm build                               # 构建
pnpm test -- --coverage                  # 测试+覆盖率
pnpm lint --fix                          # 自动修复

# Docker
docker compose -f docker-compose.dev.yml up -d  # 启动依赖
docker compose -f docker-compose.dev.yml down    # 停止
docker compose logs -f                           # 查看日志
```

---

> **文件版本：** v1.0 | **更新日期：** 2026-07-26
