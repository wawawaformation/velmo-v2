.PHONY: install up down migrate seed seed-kb chat api frontend-install frontend eval ci test fmt lint typecheck

install:
	uv sync --extra llm --extra vector --extra embeddings --extra api

up:
	docker compose up -d

down:
	docker compose down

migrate:
	uv run alembic upgrade head

seed:
	uv run python scripts/seed.py

seed-kb:
	CHROMA_HOST=localhost CHROMA_PORT=8001 uv run python scripts/seed_kb.py

chat:
	uv run python -m velmo.cli

api:
	uv run uvicorn velmo.api:app --reload

frontend-install:
	cd frontend && npm install

# Nécessite l'API lancée en parallèle (make api) — le dev server Vite
# relaie /api/... vers http://localhost:8000 (vite.config.js).
frontend:
	cd frontend && npm run dev

eval:
	uv run python -m velmo.mlops.score

ci: test

test:
	uv run pytest tests/ -v

fmt:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff check .

typecheck:
	uv run mypy src
