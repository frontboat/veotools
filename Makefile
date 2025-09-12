.PHONY: install install-dev test test-unit test-integration test-coverage clean build

# Install the package in development mode
install:
	pip install -e .

# Install with development dependencies
install-dev:
	pip install -e ".[dev,mcp]"

# Run all tests
test:
	pytest

# Run only unit tests
test-unit:
	pytest -m unit

# Run integration tests
test-integration:
	pytest -m integration

# Run tests with coverage
test-coverage:
	pytest --cov=veotools --cov-report=html --cov-report=term

# Run tests in parallel
test-parallel:
	pytest -n auto

# Run tests with verbose output
test-verbose:
	pytest -v

# Clean up build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Build the package
build: clean
	python -m build

# Format code (requires black)
format:
	black src/ tests/

# Lint code (requires ruff)
lint:
	ruff check src/ tests/

# Type check (requires mypy)
typecheck:
	mypy src/veotools

# Documentation commands
docs-install:
	pip install -e ".[docs]"

docs-serve:
	mkdocs serve

docs-build:
	mkdocs build

docs-deploy:
	mkdocs gh-deploy

# Generate API documentation with pdoc (simple alternative)
docs-api:
	pdoc --html --output-dir docs-api src/veotools --force

docs-api-serve:
	pdoc --http localhost:8080 src/veotools

# Generate LLM-friendly documentation
llm-docs:
	python scripts/generate_llm_docs.py --format md --output llm.txt

llm-docs-xml:
	python scripts/generate_llm_docs.py --format xml --output llm.xml

llm-docs-json:
	python scripts/generate_llm_docs.py --format json --output llm.json