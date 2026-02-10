.PHONY: install dev run migrate lint format test clean

install:
	uv sync

dev:
	uv run uvicorn app.main:app --reload --port 8000

run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

migrate:
	uv run alembic upgrade head

migration:
	uv run alembic revision --autogenerate -m "$(msg)"

lint:
	uv run ruff check .

format:
	uv run ruff format .

test:
	uv run pytest

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	rm -rf .venv dist *.egg-info
