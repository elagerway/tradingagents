.PHONY: db-up db-down db-reset db-test db-status help

help:
	@echo "Snapsonic dev targets:"
	@echo "  make db-up      - start local Supabase (Docker)"
	@echo "  make db-down    - stop local Supabase"
	@echo "  make db-reset   - reset DB and re-run all migrations + seed"
	@echo "  make db-test    - run all pgTAP tests under supabase/tests/database/"
	@echo "  make db-status  - show local Supabase status + URLs"

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
