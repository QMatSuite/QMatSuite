# Makefile for QMatSuite

.PHONY: test quick-test extended-test install clean

# Quick tests (run in CI)
quick-test:
	pytest tests/ -m quick -v

# Extended tests (developer only)
extended-test:
	pytest extended-tests/ -m extended -v

# Run all quick tests with coverage
test-coverage:
	pytest tests/ -m quick --cov=src/qmatsuite --cov-report=html --cov-report=term

# Install dependencies
install:
	pip install -r requirements.txt
	pip install pytest pytest-cov pytest-xdist

# Clean test artifacts
clean:
	find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov/ coverage.xml
	rm -rf tests/__pycache__ extended-tests/__pycache__

