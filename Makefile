.PHONY: help setup run stop test clean lint typecheck format check

# Default target
help:
	@echo "CPU Monitoring TUI - Available Commands:"
	@echo "  make setup      - Install dependencies and set up virtual environment"
	@echo "  make run        - Start the monitoring application"
	@echo "  make stop       - Stop the monitoring application"
	@echo "  make test       - Run test suite with coverage"
	@echo "  make lint       - Run code linter (ruff)"
	@echo "  make typecheck  - Run type checker (pyright)"
	@echo "  make format     - Format code with ruff"
	@echo "  make check      - Run linter, type checker, and tests"
	@echo "  make clean      - Remove generated files and caches"

# Python and virtual environment settings
PYTHON := python3
VENV := .venv
VENV_BIN := $(VENV)/bin
PYTHON_VENV := $(VENV_BIN)/python
PIP := $(VENV_BIN)/pip

# Check if virtual environment exists
VENV_EXISTS := $(shell [ -d $(VENV) ] && echo 1 || echo 0)

# Setup: Create virtual environment and install dependencies
setup:
ifeq ($(VENV_EXISTS), 0)
	@echo "Creating virtual environment..."
	$(PYTHON) -m venv $(VENV)
endif
	@echo "Installing dependencies..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@echo ""
	@echo "Setup complete! Activate the virtual environment with:"
	@echo "  source $(VENV_BIN)/activate"
	@echo ""
	@echo "Or run directly with: make run"

# Run the monitoring application
run:
ifeq ($(VENV_EXISTS), 0)
	@echo "Virtual environment not found. Running setup first..."
	@$(MAKE) setup
endif
	@echo "Starting CPU monitoring application..."
	@$(PYTHON_VENV) -m src.main

# Stop the application (graceful shutdown via Ctrl+C)
stop:
	@echo "To stop the application, press Ctrl+C in the terminal where it's running"
	@pkill -f "python.*src.main" || true

# Run tests with coverage
test:
ifeq ($(VENV_EXISTS), 0)
	@echo "Virtual environment not found. Running setup first..."
	@$(MAKE) setup
endif
	@echo "Running test suite..."
	$(VENV_BIN)/pytest -v --tb=short --color=yes --timeout=10

# Run linter
lint:
ifeq ($(VENV_EXISTS), 0)
	@echo "Virtual environment not found. Running setup first..."
	@$(MAKE) setup
endif
	@echo "Running ruff linter..."
	$(VENV_BIN)/ruff check src tests

# Run type checker
typecheck:
ifeq ($(VENV_EXISTS), 0)
	@echo "Virtual environment not found. Running setup first..."
	@$(MAKE) setup
endif
	@echo "Running pyright type checker..."
	$(VENV_BIN)/pyright src tests

# Format code with ruff
format:
ifeq ($(VENV_EXISTS), 0)
	@echo "Virtual environment not found. Running setup first..."
	@$(MAKE) setup
endif
	@echo "Formatting code with ruff..."
	$(VENV_BIN)/ruff check --fix src tests
	$(VENV_BIN)/ruff format src tests

# Check: Run linter, type checker, and tests
check: lint typecheck test
	@echo "All checks passed!"

# Clean generated files
clean:
	@echo "Cleaning generated files..."
	rm -rf $(VENV)
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf .pyright
	rm -rf src/__pycache__
	rm -rf tests/__pycache__
	rm -rf src/*.pyc
	rm -rf tests/*.pyc
	rm -f cpu_monitor.log
	@echo "Clean complete!"
