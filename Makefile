# Bonded Exhibition Chatbot - convenience targets
# Run "make help" to see what's available.

PYTHON      ?= python3
PORT        ?= 8080
HOST        ?= 127.0.0.1
COMPOSE     ?= docker compose
COMPOSE_DEV ?= $(COMPOSE) -f docker-compose.dev.yml

.DEFAULT_GOAL := help
.PHONY: help install run dev test docker-build docker-up docker-up-dev docker-down docker-logs lint clean

help: ## Show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9_.-]+:.*?## / {printf "  %-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Create venv (if needed) and install Python deps
	@test -d venv || $(PYTHON) -m venv venv
	@. venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

run: install ## Run the chatbot locally (HOST/PORT overridable)
	@. venv/bin/activate && $(PYTHON) web_server.py --host $(HOST) --port $(PORT)

dev: ## Run with FLASK_ENV=development and auto-reload
	@. venv/bin/activate && FLASK_ENV=development CHATBOT_DEBUG=true $(PYTHON) web_server.py --host $(HOST) --port $(PORT)

test: install ## Run pytest
	@. venv/bin/activate && $(PYTHON) -m pytest tests/ -v

docker-build: ## Build the production Docker image
	$(COMPOSE) build

docker-up: ## Start full stack (chatbot + redis) detached
	@test -f .env || cp .env.example .env
	$(COMPOSE) up -d
	@echo "Open http://localhost:$(PORT)"

docker-up-dev: ## Start minimal stack (chatbot only) detached
	@test -f .env || cp .env.example .env
	$(COMPOSE_DEV) up -d --build
	@echo "Open http://localhost:$(PORT)"

docker-down: ## Stop and remove containers
	-$(COMPOSE) down
	-$(COMPOSE_DEV) down

docker-logs: ## Tail container logs
	$(COMPOSE) logs -f --tail=100 chatbot

lint: ## Run ruff if installed
	@command -v ruff >/dev/null 2>&1 && ruff check src tests || echo "ruff not installed; skipping"

clean: ## Remove venv and __pycache__
	rm -rf venv .pytest_cache **/__pycache__
