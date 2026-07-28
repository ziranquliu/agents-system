# 项目初始化清单

> 配套文档：智能体管理系统构建计划书 v1.8 — 第9章
> 用途：项目仓库初始化时按此清单逐项创建

---

## 1. 仓库初始化

```bash
# 创建项目根目录
mkdir agent-management-system && cd agent-management-system

# 初始化 Git
git init
git checkout -b main
git checkout -b develop

# 创建基础目录结构（参考 design/project_structure.md）
mkdir -p backend/app/{api/v1,api/ws,models,schemas,services,engine,core,db/migrations,db/migrations/versions,tasks}
mkdir -p backend/tests/{test_api,test_services,test_engine,test_core}
mkdir -p frontend/src/{router,layouts,pages,components/{common,business},stores,services,hooks,utils,styles}
mkdir -p docs/design
mkdir -p scripts
mkdir -p .github/workflows
```

---

## 2. 必备文件清单

### 2.1 根目录

| 文件 | 模板 | 说明 |
|------|------|------|
| `README.md` | 见下文模板 | 项目入口文档 |
| `LICENSE` | MIT | 开源协议 |
| `.gitignore` | GitHub Python+Node 模板 | Git 忽略配置 |
| `.editorconfig` | 标准 | 编辑器统一配置 |
| `docker-compose.dev.yml` | design/dev_setup.md | 开发依赖服务 |
| `docker-compose.prod.yml` | 生产编排 | 生产部署 |
| `Makefile` | 见下文 | 常用命令快捷方式 |

### 2.2 后端 backend/

| 文件 | 说明 |
|------|------|
| `pyproject.toml` | Python 项目配置（依赖、工具配置） |
| `requirements.txt` | 生产依赖锁定 |
| `requirements-dev.txt` | 开发依赖（pytest/ruff/mypy等） |
| `.env.example` | 环境变量模板 |
| `alembic.ini` | 数据库迁移配置 |
| `Dockerfile` | 后端镜像构建 |
| `.pre-commit-config.yaml` | 提交前检查钩子 |
| `app/main.py` | FastAPI 入口 |
| `app/config.py` | Pydantic Settings 配置 |
| `app/database.py` | 异步数据库连接 |
| `app/dependencies.py` | 通用依赖注入 |
| `app/core/security.py` | JWT/密码/API Key 加密 |
| `app/core/exceptions.py` | 自定义异常类 |
| `app/core/response.py` | 统一响应格式 |
| `app/core/rate_limit.py` | API 限流中间件 |
| `app/core/logging.py` | 日志配置 |

### 2.3 前端 frontend/

| 文件 | 说明 |
|------|------|
| `package.json` | 依赖与脚本 |
| `pnpm-lock.yaml` | 依赖锁定 |
| `vite.config.ts` | Vite 配置 |
| `tsconfig.json` | TypeScript 配置 |
| `.env.example` | 环境变量模板 |
| `Dockerfile` | 前端镜像构建 |
| `eslint.config.js` | ESLint 配置 |
| `.prettierrc` | Prettier 配置 |
| `src/main.tsx` | React 入口 |
| `src/App.tsx` | 根组件+路由 |
| `src/services/api.ts` | Axios 实例+拦截器 |

---

## 3. README.md 模板

```markdown
# 智能体管理系统

> 本地部署的多智能体管理平台，支持 Agent 管理、Skill/MCP 管理、模型配置模板化、
> 多 Agent 协作、监控运维等完整能力。

## 技术栈

- 后端：FastAPI 0.115+ / Python 3.11+
- 前端：React 18 / TypeScript / Ant Design Pro / Vite
- 数据库：PostgreSQL 16 / Redis 7 / Qdrant / MinIO
- 任务队列：Celery
- 监控：Prometheus / Grafana / Loki

## 快速开始

### 1. 环境要求
- Python ≥ 3.11
- Node.js ≥ 20 LTS
- Docker ≥ 24
- pnpm ≥ 9

### 2. 启动依赖服务
​```bash
docker compose -f docker-compose.dev.yml up -d
​```

### 3. 启动后端
​```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env  # 编辑配置
alembic upgrade head
uvicorn app.main:app --reload --port 8000
​```

### 4. 启动前端
​```bash
cd frontend
pnpm install
cp .env.example .env.local
pnpm dev  # 访问 http://localhost:5173
​```

## 项目文档

- 产品需求与设计：`docs/plan/智能体管理系统构建计划书.md`
- 架构图看板：`docs/plan/architecture/架构图看板.html`
- 数据库设计：`docs/plan/design/database_design.md`
- API 规范：`docs/plan/design/api_spec.md`
- 前端结构：`docs/plan/design/frontend_structure.md`
- 开发环境搭建：`docs/plan/design/dev_setup.md`

## 开发命令

​```bash
make help           # 查看所有命令
make install        # 安装依赖
make dev            # 启动开发环境
make test           # 运行测试
make lint           # 代码检查
make migrate        # 数据库迁移
make docker-up      # 启动依赖服务
​```

## 项目结构

详见 `docs/plan/design/project_structure.md`
```

---

## 4. Makefile 模板

```makefile
.PHONY: help install dev test lint format migrate docker-up docker-down

help:
	@echo "可用命令:"
	@echo "  make install      - 安装前后端依赖"
	@echo "  make dev           - 启动开发环境（后端+前端）"
	@echo "  make test          - 运行测试"
	@echo "  make lint          - 代码检查"
	@echo "  make format        - 格式化代码"
	@echo "  make migrate       - 生成并执行数据库迁移"
	@echo "  make docker-up     - 启动依赖服务（PostgreSQL/Redis/Qdrant/MinIO）"
	@echo "  make docker-down   - 停止依赖服务"

install:
	cd backend && pip install -r requirements-dev.txt
	cd frontend && pnpm install

dev:
	cd backend && uvicorn app.main:app --reload --port 8000 &
	cd frontend && pnpm dev

test:
	cd backend && pytest -v --cov=app
	cd frontend && pnpm test

lint:
	cd backend && ruff check . && mypy app/
	cd frontend && pnpm lint

format:
	cd backend && ruff format .
	cd frontend && pnpm format

migrate:
	cd backend && alembic revision --autogenerate -m "$(msg)"
	cd backend && alembic upgrade head

docker-up:
	docker compose -f docker-compose.dev.yml up -d

docker-down:
	docker compose -f docker-compose.dev.yml down
```

---

## 5. .gitignore 模板

```gitignore
# Python
__pycache__/
*.py[cod]
.venv/
*.egg-info/
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
.coverage

# Node
node_modules/
dist/
.vite/

# 环境配置
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# 日志
*.log
logs/

# 数据库
*.sqlite3
*.db

# 构建产物
build/
*.tar.gz
*.whl
```

---

## 6. 启动检查清单

在开始编码前，逐项确认：

- [ ] Git 仓库已初始化，develop 分支已创建
- [ ] README.md 已创建并填写
- [ ] docker-compose.dev.yml 可正常启动依赖服务
- [ ] 后端 `uvicorn app.main:app` 可正常启动
- [ ] 后端 `/docs` Swagger UI 可访问
- [ ] 后端 `/health` 健康检查端点可访问
- [ ] 前端 `pnpm dev` 可启动并访问
- [ ] 前端可调用后端 API（CORS 配置正确）
- [ ] Alembic 迁移可正常执行
- [ ] pytest 可运行测试用例
- [ ] Ruff / ESLint 代码检查可运行
- [ ] pre-commit 钩子已安装
- [ ] CI/CD 流水线已配置（GitHub Actions）
- [ ] 团队成员都通过 `design/dev_setup.md` 可成功搭建环境

---

## 7. 依赖版本锁定建议

### 后端（pyproject.toml 关键依赖）

```toml
[project]
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy[asyncio]>=2.0.30",
    "asyncpg>=0.29.0",
    "alembic>=1.13.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.3.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "redis>=5.0.0",
    "celery>=5.4.0",
    "httpx>=0.27.0",
    "qdrant-client>=1.10.0",
    "minio>=7.2.0",
    "python-multipart>=0.0.9",
    "orjson>=3.10.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
    "httpx>=0.27.0",
    "ruff>=0.5.0",
    "mypy>=1.10.0",
    "pre-commit>=3.7.0",
]
```

### 前端（package.json 关键依赖）

```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.24.0",
    "antd": "^5.20.0",
    "@ant-design/pro-components": "^2.7.0",
    "axios": "^1.7.0",
    "zustand": "^4.5.0",
    "dayjs": "^1.11.0",
    "echarts": "^5.5.0",
    "echarts-for-react": "^3.0.2"
  },
  "devDependencies": {
    "vite": "^5.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.5.0",
    "vitest": "^2.0.0",
    "@testing-library/react": "^16.0.0",
    "eslint": "^9.0.0",
    "prettier": "^3.3.0",
    "msw": "^2.3.0"
  }
}
```

---

## 8. CI/CD 流水线配置（GitHub Actions）

### 8.1 测试流水线 `.github/workflows/test.yml`

```yaml
name: Test
on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: test_agent_mgmt
          POSTGRES_PASSWORD: test
        ports: ['5432:5432']
      redis:
        image: redis:7-alpine
        ports: ['6379:6379']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r backend/requirements-dev.txt
      - run: cd backend && alembic upgrade head
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:test@localhost:5432/test_agent_mgmt
      - run: cd backend && pytest -v --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v4

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - uses: pnpm/action-setup@v4
        with: { version: 9 }
      - run: cd frontend && pnpm install --frozen-lockfile
      - run: cd frontend && pnpm lint
      - run: cd frontend && pnpm test -- --coverage
      - run: cd frontend && pnpm build
```

### 8.2 部署流水线 `.github/workflows/deploy.yml`

```yaml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build & Push Images
        run: |
          docker build -t agent-mgmt-backend:latest ./backend
          docker build -t agent-mgmt-frontend:latest ./frontend
          # Push to registry...
      - name: Deploy to Server
        run: |
          ssh ${{ secrets.DEPLOY_HOST }} "cd /opt/agent-mgmt && docker compose pull && docker compose up -d"
```

---

> **文件版本：** v1.0 | **更新日期：** 2026-07-26
