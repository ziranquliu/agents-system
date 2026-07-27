.PHONY: help infra-up infra-down backend-dev backend-install frontend-dev frontend-install lint test clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

infra-up: ## Start infrastructure services (PostgreSQL, Redis, Qdrant, MinIO)
	docker compose -f docker/docker-compose.dev.yml up -d

infra-down: ## Stop infrastructure services
	docker compose -f docker/docker-compose.dev.yml down

backend-install: ## Install backend dependencies
	cd backend && python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt

backend-dev: ## Start backend dev server
	cd backend && .venv\Scripts\activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

backend-test: ## Run backend tests
	cd backend && .venv\Scripts\activate && pytest tests/ -v

frontend-install: ## Install frontend dependencies
	cd frontend && pnpm install

frontend-dev: ## Start frontend dev server
	cd frontend && pnpm dev

frontend-build: ## Build frontend for production
	cd frontend && pnpm build

lint: ## Run all linters
	cd backend && .venv\Scripts\activate && ruff check .
	cd frontend && pnpm lint

test: backend-test frontend-build ## Run all tests

clean: ## Clean temporary files
	rm -rf backend/.venv
	rm -rf frontend/node_modules
	rm -rf frontend/dist
	rm -rf **/__pycache__
	rm -rf **/.pytest_cache
