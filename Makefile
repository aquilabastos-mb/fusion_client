# Fusion Client - Makefile for testing and development

.PHONY: help test test-unit test-integration test-examples test-fast test-slow test-all
.PHONY: test-coverage test-coverage-html lint format check install install-dev clean
.PHONY: mock-server run-mock-server stop-mock-server docs build release

# Default target
help: ## Show this help message
	@echo "Fusion Client - Development Commands"
	@echo "===================================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Installation
install: ## Install the package
	pip install -e .

install-dev: ## Install package with development dependencies
	pip install -e ".[dev,langchain,crewai,observability]"

# Testing
test: ## Run all tests
	pytest

test-unit: ## Run unit tests only
	pytest tests/unit/ -m "unit" -v

test-integration: ## Run integration tests (requires API keys)
	pytest tests/integration/ -m "integration" -v --tb=short

test-examples: ## Run documentation example tests
	pytest tests/test_examples.py -v

test-fast: ## Run fast tests (unit + smoke)
	pytest tests/unit/ tests/test_examples.py -m "not slow" -x -v

test-slow: ## Run slow tests (integration + performance)
	pytest tests/integration/ -m "slow" -v --tb=short

test-all: ## Run all tests including slow ones
	pytest tests/ --tb=short

test-api: ## Run tests against real API (requires FUSION_API_KEY)
	pytest tests/integration/ -m "api" -v --tb=short

test-langchain: ## Run LangChain integration tests
	pytest tests/integration/test_langchain_integration.py -v

test-crewai: ## Run CrewAI integration tests
	pytest tests/integration/test_crewai_integration.py -v

test-performance: ## Run performance tests
	pytest tests/integration/ -m "performance" -v

# Coverage
test-coverage: ## Run tests with coverage
	pytest --cov=fusion_client --cov-report=term-missing

test-coverage-html: ## Generate HTML coverage report
	pytest --cov=fusion_client --cov-report=html
	@echo "Coverage report generated in htmlcov/index.html"

# Code Quality
lint: ## Run linting checks
	ruff check fusion_client/ tests/
	mypy fusion_client/

format: ## Format code
	black fusion_client/ tests/
	ruff format fusion_client/ tests/

check: ## Run all code quality checks
	@echo "Running linting..."
	@make lint
	@echo "Running formatting check..."
	@black --check fusion_client/ tests/
	@echo "Running tests..."
	@make test-fast
	@echo "All checks passed!"

# Mock Server
mock-server: ## Start mock server for testing
	python -m tests.testing.mock_server

run-mock-server: ## Run mock server in background
	python -c "from tests.testing.mock_server import MockFusionServer; import asyncio; server = MockFusionServer(); server.start_background(); print(f'Mock server running at {server.base_url}'); input('Press Enter to stop...'); server.stop_background()"

# Documentation
docs: ## Build documentation
	@echo "Building documentation..."
	mkdocs build

docs-serve: ## Serve documentation locally
	mkdocs serve

# Build and Release
build: ## Build package
	python -m build

clean: ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

release: clean build ## Build and upload to PyPI
	twine upload dist/*

# Development helpers
dev-setup: install-dev ## Setup development environment
	pre-commit install
	@echo "Development environment setup complete!"

test-matrix: ## Run tests across Python versions (using tox)
	tox

# Specific test scenarios
test-with-mock-server: ## Run integration tests with mock server
	@echo "Starting mock server..."
	@python -c "from tests.testing.mock_server import MockFusionServer; server = MockFusionServer(); server.start_background(); print('Mock server started'); import time; time.sleep(1)" &
	@sleep 2
	@echo "Running tests against mock server..."
	@FUSION_API_KEY=test-key FUSION_BASE_URL=http://localhost:8888 pytest tests/integration/ -v
	@echo "Tests completed"

benchmark: ## Run performance benchmarks
	pytest tests/integration/ -m "performance" --benchmark-only -v

stress-test: ## Run stress tests
	pytest tests/integration/ -m "performance" -k "stress" -v

# Environment checks
check-env: ## Check environment setup
	@echo "Checking Python version..."
	@python --version
	@echo "Checking dependencies..."
	@pip list | grep -E "(pytest|httpx|pydantic|respx)"
	@echo "Checking environment variables..."
	@if [ -z "$$FUSION_API_KEY" ]; then echo "⚠️  FUSION_API_KEY not set"; else echo "✅ FUSION_API_KEY is set"; fi
	@if [ -z "$$FUSION_BASE_URL" ]; then echo "ℹ️  FUSION_BASE_URL not set (will use default)"; else echo "✅ FUSION_BASE_URL is set"; fi

# CI/CD helpers
ci-install: ## Install dependencies for CI
	pip install -e ".[dev]"

ci-test: ## Run tests suitable for CI
	pytest tests/unit/ tests/test_examples.py --cov=fusion_client --cov-report=xml -v

ci-lint: ## Run linting for CI
	ruff check fusion_client/ tests/ --output-format=github
	mypy fusion_client/ --junit-xml=mypy-results.xml

ci-security: ## Run security checks
	pip-audit
	bandit -r fusion_client/ -f json -o bandit-report.json

# Docker helpers (if using Docker)
docker-build: ## Build Docker image for testing
	docker build -t fusion-client-test .

docker-test: ## Run tests in Docker
	docker run --rm -v $(PWD):/app fusion-client-test make test

# Database/State management for tests
reset-test-data: ## Reset test database/state
	@echo "Resetting test data..."
	@python -c "from tests.testing.mock_server import MockFusionServer; server = MockFusionServer(); server.reset_state(); print('Test data reset')"

# Advanced testing scenarios
test-error-scenarios: ## Test error handling scenarios
	pytest tests/unit/test_client.py::TestFusionClientErrorHandling -v

test-rate-limiting: ## Test rate limiting behavior
	pytest tests/unit/test_utils.py::TestRateLimiter -v

test-caching: ## Test caching functionality
	pytest tests/unit/test_utils.py::TestFusionCache -v

test-streaming: ## Test streaming functionality
	pytest tests/unit/test_utils.py::TestStreamingParser -v

# Documentation testing
test-docs: ## Test documentation examples
	pytest tests/test_examples.py -v

validate-examples: ## Validate all code examples in docs
	@echo "Validating documentation examples..."
	@python -c "import ast; import glob; [ast.parse(open(f).read()) for f in glob.glob('docs/examples/*.py')]"
	@echo "All examples are valid Python code!"

# Performance profiling
profile: ## Run performance profiling
	python -m cProfile -o profile.prof -m pytest tests/integration/ -m "performance" -v
	@echo "Profile saved to profile.prof"

# Maintenance
update-deps: ## Update dependencies
	pip install --upgrade pip
	pip install --upgrade -e ".[dev,langchain,crewai,observability]"

check-deps: ## Check for dependency security issues
	pip-audit

# Default values for environment variables
export PYTHONPATH := $(shell pwd)
export FUSION_TIMEOUT := 30
export FUSION_MAX_RETRIES := 3 