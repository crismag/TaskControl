# TaskControl developer tasks.
# `make check` is the gate: it must pass before any change is proposed.

PYTHON ?= python3.12
VENV   := .venv
BIN    := $(VENV)/bin

.DEFAULT_GOAL := help
.PHONY: help install format lint typecheck test test-unit test-integration check clean run-api run-cli

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

$(BIN)/python:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip

install: $(BIN)/python ## Create the virtualenv and install the project with dev extras
	$(BIN)/python -m pip install -e ".[dev]"

format: ## Apply formatting and import ordering
	$(BIN)/ruff format src tests
	$(BIN)/ruff check --fix src tests

lint: ## Check formatting and lint rules without modifying files
	$(BIN)/ruff format --check src tests
	$(BIN)/ruff check src tests

typecheck: ## Run mypy in strict mode
	$(BIN)/mypy

test: ## Run the full test suite with coverage
	$(BIN)/pytest --cov --cov-report=term-missing

test-unit: ## Run unit tests only
	$(BIN)/pytest tests/unit -m "not integration"

test-integration: ## Run integration tests only
	$(BIN)/pytest tests/integration -m integration

check: lint typecheck test ## Everything CI runs. The gate.

run-api: ## Start the API with autoreload
	$(BIN)/uvicorn taskcontrol.apps.api.main:create_app --factory --reload

run-cli: ## Show CLI help
	$(BIN)/taskctl --help

clean: ## Remove caches, build output, and the virtualenv
	rm -rf $(VENV) build dist .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name '*.egg-info' -prune -exec rm -rf {} +
