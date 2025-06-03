.PHONY: fmt lint lint-check

# Python code formatting and linting
fmt:
	@echo "Formatting Python code..."
	cd docker/api && ruff format src/

lint:
	@echo "Linting and fixing Python code..."
	cd docker/api && ruff check --fix src/

lint-check:
	@echo "Checking Python code (no fixes)..."
	cd docker/api && ruff check src/
