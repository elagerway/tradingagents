.PHONY: db-up db-down db-reset db-test db-status api-install api-dev api-test api-lint help

help:
	@echo "Snapsonic dev targets:"
	@echo "  make db-up       - start local Supabase (Docker)"
	@echo "  make db-down     - stop local Supabase"
	@echo "  make db-reset    - reset DB and re-run all migrations + seed"
	@echo "  make db-test     - run all pgTAP tests under supabase/tests/database/"
	@echo "  make db-status   - show local Supabase status + URLs"
	@echo "  make api-install - install Python deps for apps/api"
	@echo "  make api-dev     - run FastAPI dev server with reload"
	@echo "  make api-test    - run pytest in apps/api"
	@echo "  make api-lint    - lint apps/api with ruff"

db-up:
	supabase start

db-down:
	supabase stop

db-reset:
	supabase db reset

db-test:
	supabase test db

db-status:
	supabase status

# === API service (apps/api) ===
.PHONY: api-install api-dev api-test api-lint

api-install:
	cd apps/api && uv sync

api-dev:
	cd apps/api && uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

api-test:
	cd apps/api && uv run pytest -v

api-lint:
	cd apps/api && uv run ruff check . && uv run ruff format --check .
