.PHONY: help up down build logs ps migrate seed fmt lint test clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

up: ## Start dev stack (Postgres, Redis, MinIO, API, dashboard, wigolo, worker)
	docker compose -f docker-compose.dev.yml up -d --build

down: ## Stop dev stack
	docker compose -f docker-compose.dev.yml down

logs: ## Tail logs
	docker compose -f docker-compose.dev.yml logs -f --tail=200

ps: ## Show running containers
	docker compose -f docker-compose.dev.yml ps

migrate: ## Run Alembic migrations
	docker compose -f docker-compose.dev.yml exec api python -m vvf_database.migrate upgrade head

seed: ## Seed default admin user
	docker compose -f docker-compose.dev.yml exec api python -m vvf_database.seed

fmt: ## Format Python (ruff) and TypeScript (prettier)
	ruff format packages apps integrations tests
	@cd apps/dashboard && npx prettier --write .

lint: ## Lint
	ruff check packages apps integrations tests
	@cd apps/dashboard && npx next lint || true

test: ## Run Python tests
	pytest tests

clean: ## Remove build artifacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
	find . -type d -name "*.egg-info" -prune -exec rm -rf {} +
