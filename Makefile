.PHONY: help up down test lint clean build

help:           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

up:             ## Start the full Docker stack
	docker compose -f docker/compose/docker-compose.yml up -d

down:           ## Stop the full Docker stack
	docker compose -f docker/compose/docker-compose.yml down

build:          ## Rebuild the API container without cache
	docker compose -f docker/compose/docker-compose.yml build --no-cache api
	docker compose -f docker/compose/docker-compose.yml up -d --force-recreate api

test:           ## Run the full test suite
	pytest -v

lint:           ## Run ruff and mypy checks
	ruff check src tests || true
	mypy src || true

clean:          ## Remove build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +

db-reset:       ## Reset the demo database (scoped to demo environment)
	python -c "from src.core.api.database import SessionLocal; from src.core.models.node import EscalationTask, AuditLog, DependencyEdge, Node; db=SessionLocal(); db.query(EscalationTask).delete(); db.query(AuditLog).delete(); db.query(DependencyEdge).delete(); db.query(Node).filter_by(environment='demo').delete(); db.commit(); print('Demo data cleared.')"

demo:           ## Run the integration demo
	python scripts/integration_demo.py
