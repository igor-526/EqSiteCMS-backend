.PHONY: test lint format

test:
	uv run pytest tests/unit

lint:
	uv run mypy src tests
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run flake8 src tests

format:
	uv run ruff check --fix src tests
	uv run ruff format src tests
