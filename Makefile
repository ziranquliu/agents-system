.PHONY: help infra-up infra-down infra-logs backend-dev backend-install backend-test \
        frontend-dev frontend-install frontend-build migrate lint test clean psql redis-cli shell

help: ## 显示帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ============================================================
# 基础设施 (Docker Compose)
# ============================================================

infra-up: ## 启动基础设施 (PostgreSQL + Redis + Qdrant)
	docker compose -f docker/docker-compose.dev.yml up -d

infra-down: ## 停止基础设施
	docker compose -f docker/docker-compose.dev.yml down

infra-logs: ## 查看基础设施日志
	docker compose -f docker/docker-compose.dev.yml logs -f

psql: ## 进入 PostgreSQL 命令行
	docker compose -f docker/docker-compose.dev.yml exec agent-postgres psql -U agent -d agent_system

redis-cli: ## 进入 Redis 命令行
	docker compose -f docker/docker-compose.dev.yml exec agent-redis redis-cli

# ============================================================
# 后端
# ============================================================

backend-install: ## 安装后端依赖
	pip install -r backend/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

backend-dev: ## 启动后端开发服务器 (热重载)
	cd backend && python run_server.py

backend-test: ## 运行后端测试
	cd backend && python -m pytest tests/ -v --tb=short

backend-shell: ## 进入后端 Python 交互环境
	cd backend && python -c "import asyncio; from app.db.session import get_db; print('可用: get_db, 在 ipython 中运行')"

# ============================================================
# 前端
# ============================================================

frontend-install: ## 安装前端依赖
	cd frontend && npm install

frontend-dev: ## 启动前端开发服务器
	cd frontend && npm run dev

frontend-build: ## 构建前端生产版本
	cd frontend && npm run build

# ============================================================
# 数据库迁移
# ============================================================

migrate: ## 执行数据库迁移
	cd backend && alembic upgrade head

migration-new: ## 生成新的数据库迁移 (用法: make migration-new msg="描述")
	cd backend && alembic revision --autogenerate -m "$(msg)"

migration-history: ## 查看迁移历史
	cd backend && alembic history

migration-downgrade: ## 回滚一级迁移
	cd backend && alembic downgrade -1

seed: ## 填充种子数据
	cd backend && python scripts/seed_data.py

# ============================================================
# 质量保障
# ============================================================

lint: ## 运行 Python 代码检查
	cd backend && ruff check app/ tests/ scripts/

test: backend-test ## 运行全部测试

# ============================================================
# 工具
# ============================================================

clean: ## 清理临时文件
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache/ .coverage htmlcov/

.DEFAULT_GOAL := help
