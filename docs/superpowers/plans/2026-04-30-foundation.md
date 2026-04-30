# Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the monorepo skeleton, a local Supabase instance with the v1 schema (profiles, api_keys, runs), RLS policies, pgsodium-backed BYO key vault, all SQL covered by pgTAP tests, and a CI workflow that runs those tests on every PR. Conclude by provisioning a Supabase Cloud project and pushing the schema to it so Plans 2–4 have a real database to point at.

**Architecture:** Three new top-level directories — `apps/api/` (FastAPI service, populated in Plan 2), `apps/web/` (Next.js app, populated in Plan 3), `supabase/` (database). The upstream `tradingagents/` Python package is *never* modified. Tests are written before migrations (TDD). RLS is verified by Postgres-impersonating two distinct test users.

**Tech Stack:** PostgreSQL 15 (Supabase), pgsodium 3.x, Supabase CLI, pgTAP, [`basejump-supabase_test_helpers`](https://github.com/usebasejump/supabase-test-helpers) for impersonation, GitHub Actions, GNU Make.

**Reference spec:** [`docs/superpowers/specs/2026-04-30-tradingagents-app-design.md`](../specs/2026-04-30-tradingagents-app-design.md)

---

## Working assumptions

- Engineer is running macOS or Linux. Windows users adapt paths.
- Engineer has `git`, `make`, Docker, and the [Supabase CLI](https://supabase.com/docs/guides/cli) installed (`brew install supabase/tap/supabase`). If not, `task 1` covers the install.
- All work happens on branch `feature/foundation` (already created by writing-plans).
- After every commit, push only at the end of the plan — we'll open a PR once all tests are green.

---

## File map (everything this plan creates or modifies)

```
.gitignore                                                       # modify
Makefile                                                         # create
README.md                                                        # modify (add monorepo banner)

apps/
├── api/.gitkeep                                                  # create (Plan 2 fills this)
├── web/.gitkeep                                                  # create (Plan 3 fills this)
└── README.md                                                     # create

supabase/
├── config.toml                                                   # create (via supabase init)
├── seed.sql                                                      # create
├── migrations/
│   ├── 20260430120000_init_schema.sql                            # create
│   ├── 20260430120100_profiles_rls.sql                           # create
│   ├── 20260430120200_pgsodium_setup.sql                         # create
│   ├── 20260430120300_api_keys_rls.sql                           # create
│   ├── 20260430120400_vault_rpcs.sql                             # create
│   ├── 20260430120500_runs_rls.sql                               # create
│   └── 20260430120600_create_run_rpc.sql                         # create
└── tests/
    └── database/
        ├── 00_smoke.sql                                          # create
        ├── 10_profiles_schema.sql                                # create
        ├── 11_profiles_rls.sql                                   # create
        ├── 20_api_keys_schema.sql                                # create
        ├── 21_api_keys_rls.sql                                   # create
        ├── 22_vault_save_key.sql                                 # create
        ├── 23_vault_load_keys.sql                                # create
        ├── 30_runs_schema.sql                                    # create
        ├── 31_runs_rls.sql                                       # create
        └── 32_create_run_rpc.sql                                 # create

.github/
└── workflows/
    └── foundation-ci.yml                                          # create

docs/
└── superpowers/
    └── plans/
        └── 2026-04-30-foundation.md                              # this file
```

---

## Phase 1 — Repo scaffolding

### Task 1: Verify Supabase CLI is installed

**Files:** none (preflight)

- [ ] **Step 1: Run version check**

```bash
supabase --version
```

Expected output: a version like `2.x.y` or higher.

- [ ] **Step 2: If missing, install**

On macOS:
```bash
brew install supabase/tap/supabase
```

On Linux:
```bash
curl -fsSL https://supabase.com/install.sh | bash
```

Re-run `supabase --version` to confirm.

- [ ] **Step 3: Verify Docker is running**

```bash
docker info | head -3
```

Expected: no error. Supabase local runs Postgres in Docker.

No commit — this is a workstation-setup task.

---

### Task 2: Add monorepo entries to `.gitignore`

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Read existing `.gitignore`**

```bash
cat .gitignore | head -20
```

This shows the upstream's existing ignore rules.

- [ ] **Step 2: Append our additions**

Append this block to the *end* of `.gitignore`:

```gitignore

# === Snapsonic monorepo additions ===
# Supabase
supabase/.temp/
supabase/.branches/

# Apps (Plan 2, Plan 3)
apps/api/.venv/
apps/api/.pytest_cache/
apps/api/__pycache__/
apps/api/**/__pycache__/
apps/web/.next/
apps/web/node_modules/
apps/web/.vercel/

# Local env files (env.example committed)
.env.local
apps/api/.env
apps/web/.env*.local
```

- [ ] **Step 3: Verify nothing currently tracked is now ignored**

```bash
git check-ignore -v $(git ls-files) 2>/dev/null
```

Expected: empty output (nothing tracked is ignored).

- [ ] **Step 4: Commit**

```bash
git add .gitignore
git commit -m "chore: add monorepo .gitignore entries"
```

---

### Task 3: Create `apps/` skeleton with placeholder READMEs

**Files:**
- Create: `apps/README.md`
- Create: `apps/api/.gitkeep`
- Create: `apps/web/.gitkeep`

- [ ] **Step 1: Create the directory skeleton**

```bash
mkdir -p apps/api apps/web
touch apps/api/.gitkeep apps/web/.gitkeep
```

- [ ] **Step 2: Write `apps/README.md`**

Create `apps/README.md`:

```markdown
# Snapsonic application code

This directory holds the application that wraps the upstream `tradingagents`
Python package. The upstream package (in the repo root at `tradingagents/`) is
never modified — we depend on it as a Python library.

## Subdirectories

- `api/` — FastAPI service deployed to Render. Hosts the LangGraph engine and
  exposes `POST /runs/{id}/start` and `GET /runs/{id}/stream`. Populated in
  Plan 2.

- `web/` — Next.js (App Router) application deployed to Vercel. Auth, run
  history, settings, live agent timeline. Populated in Plan 3.

See [`docs/superpowers/specs/2026-04-30-tradingagents-app-design.md`](../docs/superpowers/specs/2026-04-30-tradingagents-app-design.md)
for the design.
```

- [ ] **Step 3: Commit**

```bash
git add apps/
git commit -m "chore: scaffold apps/ monorepo directories"
```

---

### Task 4: Add a top-of-README pointer to the new layout

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read the current top of `README.md`**

```bash
head -30 README.md
```

- [ ] **Step 2: Insert a Snapsonic banner just under the title**

Use the Edit tool to insert these lines *immediately after* line 1 of `README.md` (the existing `<p align="center">` block) — keep it minimal and non-disruptive. Insert this block before the existing `<div align="center" style="line-height: 1;">`:

```markdown

---

> **🔧 Snapsonic note:** This clone wraps the upstream TradingAgents engine in a
> hosted application. See [`apps/README.md`](apps/README.md) for our Next.js +
> FastAPI overlay and [`docs/superpowers/specs/`](docs/superpowers/specs/) for
> design docs. The upstream `tradingagents/` package is unmodified.

---

```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add Snapsonic monorepo banner to README"
```

---

## Phase 2 — Supabase local init

### Task 5: Run `supabase init`

**Files:**
- Create: `supabase/config.toml`, `supabase/seed.sql`, `supabase/.gitignore`, `supabase/migrations/`

- [ ] **Step 1: Initialize**

From repo root:

```bash
supabase init
```

The CLI prompts about VS Code settings and Deno — answer **N** to both unless you use them. It writes `supabase/config.toml`, `supabase/seed.sql`, and an empty `supabase/migrations/` directory.

- [ ] **Step 2: Verify the generated layout**

```bash
ls supabase/
```

Expected output:
```
config.toml
seed.sql
```

(`migrations/` may or may not exist yet — we'll create it explicitly.)

```bash
mkdir -p supabase/migrations supabase/tests/database
```

- [ ] **Step 3: Commit**

```bash
git add supabase/
git commit -m "chore: supabase init"
```

---

### Task 6: Configure `supabase/config.toml`

**Files:**
- Modify: `supabase/config.toml`

- [ ] **Step 1: Read the generated config**

```bash
cat supabase/config.toml
```

The default is functional. We need to confirm two things:

1. `[auth]` has `enable_signup = true` *for local dev* (we'll rely on allowlisting at the DB level, not at Supabase Auth level — this lets us seed test users in `seed.sql` without manual approval).
2. `[auth.email]` has `enable_signup = true` and `enable_confirmations = false` for local dev.

- [ ] **Step 2: Update config**

Use the Edit tool to ensure these settings exist (most are defaults but make them explicit):

In the `[auth]` section, set:
```toml
enable_signup = true
```

In the `[auth.email]` section, set:
```toml
enable_signup = true
enable_confirmations = false
```

In the `[db]` section, add:
```toml
[db.seed]
enabled = true
sql_paths = ["./seed.sql"]
```

(If the seed section already exists with the default value, skip.)

- [ ] **Step 3: Start Supabase to verify config is valid**

```bash
supabase start
```

Expected: a list of URLs (API URL, DB URL, Studio URL, anon key, service_role key). Takes 1–2 minutes on first run (downloads Docker images).

- [ ] **Step 4: Stop Supabase to keep your machine quiet**

```bash
supabase stop
```

- [ ] **Step 5: Commit**

```bash
git add supabase/config.toml
git commit -m "chore: configure supabase auth + seed for local dev"
```

---

## Phase 3 — Test infrastructure

### Task 7: Add a sentinel pgTAP test that proves the test runner works

**Files:**
- Create: `supabase/tests/database/00_smoke.sql`

- [ ] **Step 1: Write the smoke test**

Create `supabase/tests/database/00_smoke.sql`:

```sql
-- 00_smoke.sql
-- Sanity check that pgTAP runs at all. Should always pass.

begin;
select plan(1);

select pass('pgTAP test runner is alive');

select * from finish();
rollback;
```

- [ ] **Step 2: Run the test**

```bash
supabase start
supabase test db
```

Expected output: green output ending in something like `# All tests successful.` and a summary `1..1`.

- [ ] **Step 3: Commit**

```bash
git add supabase/tests/database/00_smoke.sql
git commit -m "test: add pgTAP smoke test"
```

---

### Task 8: Add `Makefile` with dev shortcuts

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Write the Makefile**

Create `Makefile` at repo root:

```makefile
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
```

- [ ] **Step 2: Verify the Make targets work**

```bash
make help
```

Expected: the help text above prints.

```bash
make db-test
```

Expected: the smoke test from Task 7 passes (Supabase must be running — `make db-up` first if not).

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "chore: add Makefile with db-* dev shortcuts"
```

---

### Task 9: Install Basejump test helpers (inline SQL)

**Files:**
- Create: `supabase/migrations/20260430115000_install_test_helpers.sql`

The test helpers expose `tests.create_supabase_user(identifier)`, `tests.authenticate_as(identifier)`, `tests.clear_authentication()`, `tests.get_supabase_uid(identifier)` — these let pgTAP tests act as different authenticated users.

> **Note:** the original plan called this "install via `create extension`". That doesn't work — the `basejump-supabase_test_helpers` extension is **not bundled** in Supabase's local Postgres image (verified empirically: `pg_available_extensions` returns nothing for it). Embedding the canonical SQL inline gives identical runtime semantics and avoids depending on the image shipping an extension binary. We also need to load `pgtap` ourselves at the top of the migration because the helpers' `rls_enabled()` SQL functions reference pgTAP's `is(...)` and SQL function bodies are validated at CREATE time.

- [ ] **Step 1: Fetch the canonical helpers SQL**

```bash
curl -sL https://raw.githubusercontent.com/usebasejump/supabase-test-helpers/main/supabase_test_helpers--0.0.6.sql -o /tmp/basejump-helpers.sql
# Strip the first two lines (the `\echo … \quit` directive intended only for
# `CREATE EXTENSION` consumers).
tail -n +3 /tmp/basejump-helpers.sql > /tmp/basejump-helpers-clean.sql
wc -l /tmp/basejump-helpers-clean.sql   # should be ~382
```

- [ ] **Step 2: Write the migration**

Create `supabase/migrations/20260430115000_install_test_helpers.sql` with this header, then append the cleaned SQL from Step 1:

```sql
-- ============================================================================
-- Install Basejump's Supabase test helpers (inline)
-- ============================================================================
--
-- Provides the `tests` schema used by pgTAP files to impersonate users:
--   - tests.create_supabase_user(identifier, email?, phone?, metadata?)
--   - tests.get_supabase_uid(identifier)
--   - tests.authenticate_as(identifier)
--   - tests.authenticate_as_service_role()
--   - tests.clear_authentication()
--   - tests.rls_enabled(schema [, table])
--   - tests.freeze_time / unfreeze_time
--
-- Source: https://github.com/usebasejump/supabase-test-helpers
-- Version: 0.0.6 (file: supabase_test_helpers--0.0.6.sql)
--
-- Why inline instead of `create extension`:
-- The `basejump-supabase_test_helpers` extension is NOT bundled in Supabase's
-- local Postgres docker image. Embedding the canonical SQL inline avoids
-- depending on the image shipping an extension binary.
--
-- These helpers are present in production too because Supabase Cloud doesn't
-- differentiate dev/prod migration paths. They're harmless: they live under a
-- `tests` / `test_overrides` schema, only callable explicitly, and add no
-- policies.
-- ============================================================================

-- Load pgTAP into the `extensions` schema so that the rls_enabled() helpers
-- below (which call pgTAP's is(...)) parse-resolve at CREATE time. pgTAP is
-- normally loaded only by `supabase test db`; we need it earlier here.
CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;

-- (then the contents of /tmp/basejump-helpers-clean.sql)
```

To produce the file mechanically:

```bash
cat > supabase/migrations/20260430115000_install_test_helpers.sql <<'HEADER'
-- ============================================================================
-- Install Basejump's Supabase test helpers (inline)
-- ============================================================================
--
-- Provides the `tests` schema used by pgTAP files to impersonate users:
--   - tests.create_supabase_user(identifier, email?, phone?, metadata?)
--   - tests.get_supabase_uid(identifier)
--   - tests.authenticate_as(identifier)
--   - tests.authenticate_as_service_role()
--   - tests.clear_authentication()
--   - tests.rls_enabled(schema [, table])
--   - tests.freeze_time / unfreeze_time
--
-- Source: https://github.com/usebasejump/supabase-test-helpers
-- Version: 0.0.6 (file: supabase_test_helpers--0.0.6.sql)
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;

HEADER
cat /tmp/basejump-helpers-clean.sql >> supabase/migrations/20260430115000_install_test_helpers.sql
```

- [ ] **Step 3: Reset and verify it installs cleanly**

```bash
make db-up         # start the stack if not running
make db-reset
```

Expected: migration applies without error. The `tests` schema now exists.

```bash
docker exec -i supabase_db_tradingAgents psql -U postgres -d postgres -t -A <<< "select tests.create_supabase_user('alice') as user_id;"
```

Expected: a UUID-shaped value is returned (e.g. `e04147b8-84f3-4928-a86c-f1838f43290e`).

> Note: `supabase db psql` doesn't accept `-c <sql>` in CLI 2.95+. Use the docker exec form above (the container name follows the pattern `supabase_db_<repo-folder-name>`).

- [ ] **Step 4: Stop the stack**

```bash
make db-down
```

Expected: containers stop; `docker ps` shows no `supabase_*` containers.

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/20260430115000_install_test_helpers.sql
git commit -m "feat(db): inline Basejump test helpers + pgTAP for impersonation"
```

---

## Phase 4 — `profiles` table

### Task 10: TDD — write failing test for `profiles` schema

**Files:**
- Create: `supabase/tests/database/10_profiles_schema.sql`

- [ ] **Step 1: Write the failing test**

Create `supabase/tests/database/10_profiles_schema.sql`:

```sql
-- 10_profiles_schema.sql
-- Asserts the profiles table has the expected shape.

begin;
select plan(7);

select has_table('public', 'profiles', 'profiles table exists');

select has_column('public', 'profiles', 'id', 'has id column');
select col_type_is('public', 'profiles', 'id', 'uuid', 'id is uuid');
select col_is_pk('public', 'profiles', 'id', 'id is primary key');

select has_column('public', 'profiles', 'email', 'has email column');
select has_column('public', 'profiles', 'allowed_at', 'has allowed_at column');
select col_type_is(
  'public', 'profiles', 'allowed_at',
  'timestamp with time zone',
  'allowed_at is timestamptz'
);

select * from finish();
rollback;
```

- [ ] **Step 2: Run the test — expect failure**

```bash
make db-test
```

Expected: this test file fails with messages like `relation "public.profiles" does not exist` and `not ok 1 - profiles table exists`.

- [ ] **Step 3: Commit the failing test**

```bash
git add supabase/tests/database/10_profiles_schema.sql
git commit -m "test(db): add profiles schema test (RED)"
```

---

### Task 11: Create `profiles` table + auto-insert trigger

**Files:**
- Create: `supabase/migrations/20260430120000_init_schema.sql`

- [ ] **Step 1: Write the migration**

Create `supabase/migrations/20260430120000_init_schema.sql`:

```sql
-- 20260430120000_init_schema.sql
-- Creates the profiles table and a trigger that auto-creates a profile
-- whenever a new auth.users row appears.

create table public.profiles (
  id           uuid primary key references auth.users(id) on delete cascade,
  email        text not null,
  display_name text,
  allowed_at   timestamptz,
  created_at   timestamptz not null default now()
);

comment on column public.profiles.allowed_at is
  'Null = waitlisted. Non-null = beta member; set by an admin when granting access.';

-- Trigger: when a new auth.users row is inserted, create a corresponding profile.
create function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email)
  values (new.id, new.email);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row
  execute function public.handle_new_user();
```

- [ ] **Step 2: Apply migration and run the test — expect pass**

```bash
make db-reset
make db-test
```

Expected: the smoke test (Task 7) and the profiles schema test (Task 10) both pass. Output ends with `# All tests successful.`

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/20260430120000_init_schema.sql
git commit -m "feat(db): create profiles table + auth trigger (GREEN)"
```

---

### Task 12: TDD — write failing RLS test for `profiles`

**Files:**
- Create: `supabase/tests/database/11_profiles_rls.sql`

- [ ] **Step 1: Write the failing test**

Create `supabase/tests/database/11_profiles_rls.sql`:

```sql
-- 11_profiles_rls.sql
-- Asserts that a user can read only their own profile.

begin;
select plan(3);

-- Create two users via the test helpers.
select tests.create_supabase_user('alice');
select tests.create_supabase_user('bob');

-- Authenticate as alice and confirm she sees only her row.
select tests.authenticate_as('alice');

select results_eq(
  $$ select count(*)::int from public.profiles where id = tests.get_supabase_uid('alice') $$,
  $$ values (1) $$,
  'alice can see her own profile'
);

select results_eq(
  $$ select count(*)::int from public.profiles where id = tests.get_supabase_uid('bob') $$,
  $$ values (0) $$,
  'alice cannot see bob''s profile'
);

select results_eq(
  $$ select count(*)::int from public.profiles $$,
  $$ values (1) $$,
  'alice''s unfiltered query returns only her own row'
);

select * from finish();
rollback;
```

- [ ] **Step 2: Run — expect failure**

```bash
make db-test
```

Expected: the new test fails because RLS is not yet enabled — `alice`'s queries return *all* profiles (count = 2 instead of 1, and she sees bob's profile).

- [ ] **Step 3: Commit the failing test**

```bash
git add supabase/tests/database/11_profiles_rls.sql
git commit -m "test(db): add profiles RLS test (RED)"
```

---

### Task 13: Enable RLS + add `select` policy on `profiles`

**Files:**
- Create: `supabase/migrations/20260430120100_profiles_rls.sql`

- [ ] **Step 1: Write the migration**

Create `supabase/migrations/20260430120100_profiles_rls.sql`:

```sql
-- 20260430120100_profiles_rls.sql
-- Enables RLS on profiles and adds a self-only select policy.

alter table public.profiles enable row level security;

create policy "users can select own profile"
  on public.profiles
  for select
  to authenticated
  using (id = auth.uid());

-- No insert/update/delete policies for `authenticated`. Profile rows are
-- created by the on_auth_user_created trigger; updates (e.g. setting
-- display_name) will be added in a future plan as a separate Server Action.
```

- [ ] **Step 2: Apply and re-run tests — expect pass**

```bash
make db-reset
make db-test
```

Expected: all four files green (00_smoke, 10_profiles_schema, 11_profiles_rls). Smoke `# All tests successful.`.

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/20260430120100_profiles_rls.sql
git commit -m "feat(db): enable RLS on profiles (GREEN)"
```

---

## Phase 5 — pgsodium + `api_keys` table

### Task 14: Enable pgsodium + create master key

**Files:**
- Create: `supabase/migrations/20260430120200_pgsodium_setup.sql`

- [ ] **Step 1: Write the migration**

Create `supabase/migrations/20260430120200_pgsodium_setup.sql`:

```sql
-- 20260430120200_pgsodium_setup.sql
-- Enables pgsodium and creates a deterministic AEAD key for BYO API key
-- encryption. The key UUID is referenced by encrypt/decrypt RPCs (see later
-- migrations).

create extension if not exists pgsodium;

-- Create the master key once. Idempotent: re-running this migration won't
-- create duplicates because we look it up by name.
do $$
declare
  key_id uuid;
begin
  select id into key_id from pgsodium.key where name = 'tradingagents_byo_keys';

  if key_id is null then
    perform pgsodium.create_key(
      key_type := 'aead-det',
      name := 'tradingagents_byo_keys'
    );
  end if;
end;
$$;

-- Helper: returns the UUID of our master key. Used by RPCs in later migrations.
create function public._byo_master_key_id()
returns uuid
language sql
stable
security definer
set search_path = pgsodium, public
as $$
  select id from pgsodium.key where name = 'tradingagents_byo_keys'
$$;

-- Lock down: only superuser/service_role and our SECURITY DEFINER RPCs may call this.
revoke all on function public._byo_master_key_id() from public, anon, authenticated;
```

- [ ] **Step 2: Apply migration**

```bash
make db-reset
```

Expected: no errors. The `pgsodium` extension is now enabled and the master key exists.

- [ ] **Step 3: Manually verify the key exists**

```bash
supabase db psql -c "select id, name, key_type from pgsodium.key where name = 'tradingagents_byo_keys';"
```

Expected: one row, `key_type = aead-det`.

- [ ] **Step 4: Commit**

```bash
git add supabase/migrations/20260430120200_pgsodium_setup.sql
git commit -m "feat(db): enable pgsodium + create BYO master key"
```

---

### Task 15: TDD — failing test for `api_keys` schema

**Files:**
- Create: `supabase/tests/database/20_api_keys_schema.sql`

- [ ] **Step 1: Write the failing test**

Create `supabase/tests/database/20_api_keys_schema.sql`:

```sql
-- 20_api_keys_schema.sql
-- Asserts the api_keys table has the expected shape.

begin;
select plan(8);

select has_table('public', 'api_keys', 'api_keys table exists');
select has_column('public', 'api_keys', 'user_id', 'has user_id');
select has_column('public', 'api_keys', 'provider', 'has provider');
select has_column('public', 'api_keys', 'key_encrypted', 'has key_encrypted');
select col_type_is(
  'public', 'api_keys', 'key_encrypted', 'bytea',
  'key_encrypted is bytea'
);
select has_column('public', 'api_keys', 'last_used_at', 'has last_used_at');
select has_column('public', 'api_keys', 'created_at', 'has created_at');

-- Composite primary key (user_id, provider)
select col_is_pk(
  'public', 'api_keys', array['user_id', 'provider'],
  '(user_id, provider) is composite PK'
);

select * from finish();
rollback;
```

- [ ] **Step 2: Run — expect failure**

```bash
make db-test
```

Expected: schema assertions fail (table does not exist).

- [ ] **Step 3: Commit the failing test**

```bash
git add supabase/tests/database/20_api_keys_schema.sql
git commit -m "test(db): add api_keys schema test (RED)"
```

---

### Task 16: Create `api_keys` table + RLS

**Files:**
- Create: `supabase/migrations/20260430120300_api_keys_rls.sql`

- [ ] **Step 1: Write the migration**

Create `supabase/migrations/20260430120300_api_keys_rls.sql`:

```sql
-- 20260430120300_api_keys_rls.sql
-- Creates the api_keys table holding pgsodium-encrypted BYO LLM keys.
-- key_encrypted is opaque ciphertext; encrypt/decrypt happens only through
-- the SECURITY DEFINER RPCs in 20260430120400_vault_rpcs.sql.

create table public.api_keys (
  user_id        uuid not null references auth.users(id) on delete cascade,
  provider       text not null check (provider in (
    'openai','anthropic','google','xai','deepseek',
    'dashscope','zhipu','openrouter','alpha_vantage'
  )),
  key_encrypted  bytea not null,
  last_used_at   timestamptz,
  created_at     timestamptz not null default now(),
  primary key (user_id, provider)
);

alter table public.api_keys enable row level security;

-- Authenticated users can SEE their own rows (to display masked last-4 in
-- /settings UI), but never the plaintext (which is encrypted in
-- key_encrypted).
create policy "users can select own api_keys"
  on public.api_keys
  for select
  to authenticated
  using (user_id = auth.uid());

-- Authenticated users can DELETE their own rows (UI: "remove key").
create policy "users can delete own api_keys"
  on public.api_keys
  for delete
  to authenticated
  using (user_id = auth.uid());

-- INSERT and UPDATE are denied for `authenticated` — they happen exclusively
-- through vault_save_key() (next migration), which is SECURITY DEFINER and
-- handles encryption.
```

- [ ] **Step 2: Apply and run schema test — expect pass**

```bash
make db-reset
make db-test
```

Expected: 20_api_keys_schema.sql is now green.

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/20260430120300_api_keys_rls.sql
git commit -m "feat(db): create api_keys table + select/delete RLS (GREEN)"
```

---

### Task 17: TDD — failing RLS test for `api_keys`

**Files:**
- Create: `supabase/tests/database/21_api_keys_rls.sql`

- [ ] **Step 1: Write the failing test**

Create `supabase/tests/database/21_api_keys_rls.sql`:

```sql
-- 21_api_keys_rls.sql
-- Asserts that:
--  (a) a user can select their own api_keys row,
--  (b) a user CANNOT select another user's api_keys row,
--  (c) authenticated users CANNOT insert directly (must use vault_save_key).

begin;
select plan(3);

select tests.create_supabase_user('alice');
select tests.create_supabase_user('bob');

-- Service role inserts a fake api_key row for each (we test plumbing here;
-- real flow uses vault_save_key, tested in 22_vault_save_key.sql).
set role service_role;
insert into public.api_keys (user_id, provider, key_encrypted)
values
  (tests.get_supabase_uid('alice'), 'openai', '\x01'::bytea),
  (tests.get_supabase_uid('bob'),   'openai', '\x02'::bytea);
reset role;

-- Authenticate as alice.
select tests.authenticate_as('alice');

select results_eq(
  $$ select count(*)::int from public.api_keys where user_id = tests.get_supabase_uid('alice') $$,
  $$ values (1) $$,
  'alice sees her own api_key row'
);

select results_eq(
  $$ select count(*)::int from public.api_keys where user_id = tests.get_supabase_uid('bob') $$,
  $$ values (0) $$,
  'alice cannot see bob''s api_keys'
);

select throws_ok(
  $$ insert into public.api_keys (user_id, provider, key_encrypted)
       values (tests.get_supabase_uid('alice'), 'anthropic', '\x03'::bytea) $$,
  '42501',
  null,
  'authenticated user cannot directly insert into api_keys'
);

select * from finish();
rollback;
```

- [ ] **Step 2: Run — expect pass**

```bash
make db-test
```

Expected: the test passes immediately because the RLS policies from Task 16 already enforce these behaviors. (We're verifying that what we wrote *actually* works — this is RED-then-already-GREEN, which is fine; the test value is in catching future regressions.)

If the test fails, the cause is almost certainly that Task 16's RLS policies were forgotten — go fix them.

- [ ] **Step 3: Commit**

```bash
git add supabase/tests/database/21_api_keys_rls.sql
git commit -m "test(db): assert api_keys RLS isolates users"
```

---

## Phase 6 — Vault RPCs

### Task 18: TDD — failing test for `vault_save_key`

**Files:**
- Create: `supabase/tests/database/22_vault_save_key.sql`

- [ ] **Step 1: Write the failing test**

Create `supabase/tests/database/22_vault_save_key.sql`:

```sql
-- 22_vault_save_key.sql
-- Asserts vault_save_key(provider, plaintext) encrypts plaintext and
-- upserts into api_keys for the authenticated user.

begin;
select plan(4);

select tests.create_supabase_user('alice');
select tests.authenticate_as('alice');

-- The function must exist.
select has_function(
  'public', 'vault_save_key', array['text', 'text'],
  'vault_save_key(text, text) exists'
);

-- Calling it inserts a row with non-empty ciphertext that does NOT contain
-- the plaintext bytes.
select lives_ok(
  $$ select public.vault_save_key('openai', 'sk-test-alice-secret') $$,
  'vault_save_key call succeeds'
);

select results_eq(
  $$ select count(*)::int from public.api_keys
       where user_id = tests.get_supabase_uid('alice')
         and provider = 'openai'
         and length(key_encrypted) > 0
         and position('sk-test-alice-secret'::bytea in key_encrypted) = 0 $$,
  $$ values (1) $$,
  'plaintext is not present in stored ciphertext'
);

-- Calling again with same provider upserts (replaces) the row.
select lives_ok(
  $$ select public.vault_save_key('openai', 'sk-test-alice-NEW') $$,
  'second call upserts'
);

select * from finish();
rollback;
```

- [ ] **Step 2: Run — expect failure**

```bash
make db-test
```

Expected: `has_function` fails (function does not exist).

- [ ] **Step 3: Commit**

```bash
git add supabase/tests/database/22_vault_save_key.sql
git commit -m "test(db): add vault_save_key test (RED)"
```

---

### Task 19: Implement `vault_save_key` RPC

**Files:**
- Create: `supabase/migrations/20260430120400_vault_rpcs.sql` (will hold both vault RPCs)

- [ ] **Step 1: Write the migration**

Create `supabase/migrations/20260430120400_vault_rpcs.sql`:

```sql
-- 20260430120400_vault_rpcs.sql
-- BYO API key vault RPCs:
--   - vault_save_key(provider, plaintext): encrypt + upsert
--   - vault_load_keys(uid, providers[]): decrypt subset (service_role only)

-- ----- vault_save_key ---------------------------------------------------

create function public.vault_save_key(
  p_provider  text,
  p_plaintext text
)
returns void
language plpgsql
security definer
set search_path = public, pgsodium
as $$
declare
  v_user_id uuid := auth.uid();
  v_key_id  uuid := public._byo_master_key_id();
  v_cipher  bytea;
begin
  if v_user_id is null then
    raise exception 'not authenticated' using errcode = '28000';
  end if;

  -- AEAD with user_id as additional authenticated data:
  -- prevents an attacker who copies a row to a different user from
  -- decrypting it.
  v_cipher := pgsodium.crypto_aead_det_encrypt(
    convert_to(p_plaintext, 'utf8'),
    convert_to(v_user_id::text, 'utf8'),
    v_key_id
  );

  insert into public.api_keys (user_id, provider, key_encrypted)
  values (v_user_id, p_provider, v_cipher)
  on conflict (user_id, provider) do update
    set key_encrypted = excluded.key_encrypted,
        created_at    = now(),
        last_used_at  = null;
end;
$$;

-- Only authenticated users can call it. Service role doesn't need it
-- (Plan 2 will use vault_load_keys, not vault_save_key).
revoke all on function public.vault_save_key(text, text) from public, anon;
grant execute on function public.vault_save_key(text, text) to authenticated;
```

(Task 20 will add `vault_load_keys` to the *same* migration file — append, don't create a new one.)

- [ ] **Step 2: Apply and run tests — expect pass**

```bash
make db-reset
make db-test
```

Expected: 22_vault_save_key.sql is now green.

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/20260430120400_vault_rpcs.sql
git commit -m "feat(db): add vault_save_key RPC (GREEN)"
```

---

### Task 20: TDD — failing test for `vault_load_keys`

**Files:**
- Create: `supabase/tests/database/23_vault_load_keys.sql`

- [ ] **Step 1: Write the failing test**

Create `supabase/tests/database/23_vault_load_keys.sql`:

```sql
-- 23_vault_load_keys.sql
-- Asserts vault_load_keys(user_id, providers[]) returns the original
-- plaintext for the requested providers, bumps last_used_at, and is
-- callable only by service_role.

begin;
select plan(5);

select tests.create_supabase_user('alice');
select tests.authenticate_as('alice');

-- Save two keys as alice.
perform public.vault_save_key('openai',    'sk-alice-openai');
perform public.vault_save_key('anthropic', 'sk-alice-anthropic');

-- Reset to no role; impersonate the service role for vault_load_keys.
select tests.clear_authentication();
set role service_role;

-- Function exists.
select has_function(
  'public', 'vault_load_keys', array['uuid', 'text[]'],
  'vault_load_keys(uuid, text[]) exists'
);

-- Returns the requested providers only, with correct plaintext.
select results_eq(
  $$ select provider, plaintext from public.vault_load_keys(
       (select id from auth.users where email like 'alice%'),
       array['openai']::text[]
     ) order by provider $$,
  $$ values ('openai'::text, 'sk-alice-openai'::text) $$,
  'returns only requested providers with correct plaintext'
);

select results_eq(
  $$ select count(*)::int from public.vault_load_keys(
       (select id from auth.users where email like 'alice%'),
       array['openai','anthropic']::text[]
     ) $$,
  $$ values (2) $$,
  'returns multiple providers when requested'
);

-- last_used_at gets bumped after a load.
select isnt(
  (select last_used_at from public.api_keys
     where provider = 'openai'
       and user_id = (select id from auth.users where email like 'alice%')),
  null::timestamptz,
  'last_used_at is updated by vault_load_keys'
);

-- Authenticated role cannot call vault_load_keys.
reset role;
select tests.authenticate_as('alice');
select throws_ok(
  $$ select * from public.vault_load_keys(auth.uid(), array['openai']::text[]) $$,
  '42501',
  null,
  'authenticated user cannot call vault_load_keys'
);

select * from finish();
rollback;
```

- [ ] **Step 2: Run — expect failure**

```bash
make db-test
```

Expected: `has_function` fails.

- [ ] **Step 3: Commit**

```bash
git add supabase/tests/database/23_vault_load_keys.sql
git commit -m "test(db): add vault_load_keys test (RED)"
```

---

### Task 21: Implement `vault_load_keys` RPC

**Files:**
- Modify: `supabase/migrations/20260430120400_vault_rpcs.sql` (append)

- [ ] **Step 1: Append `vault_load_keys` to the existing migration**

Add this to the *bottom* of `supabase/migrations/20260430120400_vault_rpcs.sql`:

```sql
-- ----- vault_load_keys --------------------------------------------------

create type public.vault_load_keys_row as (
  provider  text,
  plaintext text
);

create function public.vault_load_keys(
  p_user_id   uuid,
  p_providers text[]
)
returns setof public.vault_load_keys_row
language plpgsql
security definer
set search_path = public, pgsodium
as $$
declare
  v_key_id uuid := public._byo_master_key_id();
  r        public.api_keys%rowtype;
begin
  for r in
    select * from public.api_keys
    where user_id = p_user_id
      and provider = any(p_providers)
  loop
    -- Bump last_used_at while we have the row.
    update public.api_keys
       set last_used_at = now()
     where user_id = r.user_id
       and provider = r.provider;

    return next (
      r.provider,
      convert_from(
        pgsodium.crypto_aead_det_decrypt(
          r.key_encrypted,
          convert_to(r.user_id::text, 'utf8'),
          v_key_id
        ),
        'utf8'
      )
    )::public.vault_load_keys_row;
  end loop;
end;
$$;

-- Service role only. Authenticated/anon must never call this.
revoke all on function public.vault_load_keys(uuid, text[]) from public, anon, authenticated;
grant execute on function public.vault_load_keys(uuid, text[]) to service_role;
```

- [ ] **Step 2: Apply and run tests — expect pass**

```bash
make db-reset
make db-test
```

Expected: 23_vault_load_keys.sql passes.

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/20260430120400_vault_rpcs.sql
git commit -m "feat(db): add vault_load_keys RPC (GREEN)"
```

---

## Phase 7 — `runs` table + `create_run` RPC

### Task 22: TDD — failing test for `runs` schema

**Files:**
- Create: `supabase/tests/database/30_runs_schema.sql`

- [ ] **Step 1: Write the failing test**

Create `supabase/tests/database/30_runs_schema.sql`:

```sql
-- 30_runs_schema.sql
-- Asserts the runs table has the expected shape.

begin;
select plan(10);

select has_table('public', 'runs', 'runs table exists');
select has_column('public', 'runs', 'id', 'has id');
select col_type_is('public', 'runs', 'id', 'uuid', 'id is uuid');
select col_is_pk('public', 'runs', 'id', 'id is PK');

select has_column('public', 'runs', 'user_id', 'has user_id');
select has_column('public', 'runs', 'ticker', 'has ticker');
select has_column('public', 'runs', 'trade_date', 'has trade_date');
select has_column('public', 'runs', 'status', 'has status');
select col_type_is('public', 'runs', 'config', 'jsonb', 'config is jsonb');
select col_type_is('public', 'runs', 'events', 'jsonb', 'events is jsonb');

select * from finish();
rollback;
```

- [ ] **Step 2: Run — expect failure**

```bash
make db-test
```

Expected: schema assertions fail.

- [ ] **Step 3: Commit**

```bash
git add supabase/tests/database/30_runs_schema.sql
git commit -m "test(db): add runs schema test (RED)"
```

---

### Task 23: Create `runs` table + RLS (insert denied for `authenticated`)

**Files:**
- Create: `supabase/migrations/20260430120500_runs_rls.sql`

- [ ] **Step 1: Write the migration**

Create `supabase/migrations/20260430120500_runs_rls.sql`:

```sql
-- 20260430120500_runs_rls.sql
-- Creates the runs table and enables select-only RLS for users.
-- Inserts go through create_run() (next migration), which is SECURITY DEFINER.
-- Updates go through service_role from the FastAPI worker (Plan 2).

create table public.runs (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users(id) on delete cascade,
  ticker          text not null,
  trade_date      date not null,
  status          text not null default 'pending'
                    check (status in ('pending','running','completed','failed')),
  config          jsonb not null,
  events          jsonb not null default '[]'::jsonb,
  final_decision  jsonb,
  error           text,
  created_at      timestamptz not null default now(),
  started_at      timestamptz,
  completed_at    timestamptz
);

create index runs_user_id_created_at_idx
  on public.runs (user_id, created_at desc);

alter table public.runs enable row level security;

-- Users can read their own runs.
create policy "users can select own runs"
  on public.runs
  for select
  to authenticated
  using (user_id = auth.uid());

-- INSERT, UPDATE, DELETE all denied for `authenticated`. Inserts go through
-- create_run() (SECURITY DEFINER); updates happen on the FastAPI side via
-- service_role.
```

- [ ] **Step 2: Apply and run schema test — expect pass**

```bash
make db-reset
make db-test
```

Expected: 30_runs_schema.sql passes.

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/20260430120500_runs_rls.sql
git commit -m "feat(db): create runs table + select RLS (GREEN)"
```

---

### Task 24: TDD — failing RLS + behavior test for `runs`

**Files:**
- Create: `supabase/tests/database/31_runs_rls.sql`

- [ ] **Step 1: Write the failing test**

Create `supabase/tests/database/31_runs_rls.sql`:

```sql
-- 31_runs_rls.sql
-- Asserts:
--   (a) authenticated user cannot directly insert/update/delete a runs row
--   (b) a user can read their own runs but not others'
--   (c) service_role can update any row

begin;
select plan(5);

select tests.create_supabase_user('alice');
select tests.create_supabase_user('bob');

-- Service role inserts test rows.
set role service_role;
insert into public.runs (id, user_id, ticker, trade_date, config)
values
  ('00000000-0000-0000-0000-000000000aaa',
   tests.get_supabase_uid('alice'), 'NVDA', '2026-01-15', '{}'::jsonb),
  ('00000000-0000-0000-0000-000000000bbb',
   tests.get_supabase_uid('bob'),   'AAPL', '2026-01-15', '{}'::jsonb);
reset role;

-- Authenticate as alice.
select tests.authenticate_as('alice');

select results_eq(
  $$ select count(*)::int from public.runs $$,
  $$ values (1) $$,
  'alice sees only her own runs'
);

select throws_ok(
  $$ insert into public.runs (user_id, ticker, trade_date, config)
       values (tests.get_supabase_uid('alice'), 'TSLA', '2026-01-15', '{}'::jsonb) $$,
  '42501',
  null,
  'authenticated user cannot directly insert into runs'
);

select throws_ok(
  $$ update public.runs set ticker = 'PWND'
       where id = '00000000-0000-0000-0000-000000000aaa' $$,
  null, null,
  'authenticated user cannot update own runs row directly'
);

-- Service role can update.
select tests.clear_authentication();
set role service_role;

select lives_ok(
  $$ update public.runs set status = 'running', started_at = now()
       where id = '00000000-0000-0000-0000-000000000aaa' $$,
  'service_role can update runs'
);

select results_eq(
  $$ select status::text from public.runs where id = '00000000-0000-0000-0000-000000000aaa' $$,
  $$ values ('running'::text) $$,
  'service_role update took effect'
);

select * from finish();
rollback;
```

- [ ] **Step 2: Run — expect pass**

```bash
make db-test
```

Expected: all five assertions pass thanks to RLS from Task 23. If anything fails, fix the policies in `20260430120500_runs_rls.sql` before continuing.

- [ ] **Step 3: Commit**

```bash
git add supabase/tests/database/31_runs_rls.sql
git commit -m "test(db): assert runs RLS isolates users + locks writes"
```

---

### Task 25: TDD — failing test for `create_run` RPC

**Files:**
- Create: `supabase/tests/database/32_create_run_rpc.sql`

- [ ] **Step 1: Write the failing test**

Create `supabase/tests/database/32_create_run_rpc.sql`:

```sql
-- 32_create_run_rpc.sql
-- Asserts create_run(input jsonb) inserts a runs row owned by the
-- authenticated user, and rejects waitlisted users.

begin;
select plan(5);

select tests.create_supabase_user('alice');
select tests.create_supabase_user('waitlisted');

-- Mark alice as allowed; waitlisted stays null.
set role service_role;
update public.profiles set allowed_at = now()
  where id = tests.get_supabase_uid('alice');
reset role;

-- Function exists.
select has_function(
  'public', 'create_run', array['jsonb'],
  'create_run(jsonb) exists'
);

-- Allowed user can create a run.
select tests.authenticate_as('alice');

select isa_ok(
  (select public.create_run(
    jsonb_build_object(
      'ticker', 'NVDA',
      'trade_date', '2026-01-15',
      'config', jsonb_build_object('llm_provider', 'openai')
    )
  )),
  'uuid',
  'create_run returns a uuid'
);

select results_eq(
  $$ select count(*)::int from public.runs
       where user_id = tests.get_supabase_uid('alice')
         and ticker = 'NVDA' $$,
  $$ values (1) $$,
  'create_run inserted the row'
);

-- Waitlisted user is rejected.
select tests.clear_authentication();
select tests.authenticate_as('waitlisted');

select throws_ok(
  $$ select public.create_run(
       jsonb_build_object(
         'ticker', 'AAPL',
         'trade_date', '2026-01-15',
         'config', '{}'::jsonb
       )
     ) $$,
  null, null,
  'waitlisted user cannot create_run'
);

select results_eq(
  $$ select count(*)::int from public.runs
       where user_id = tests.get_supabase_uid('waitlisted') $$,
  $$ values (0) $$,
  'no row inserted for waitlisted user'
);

select * from finish();
rollback;
```

- [ ] **Step 2: Run — expect failure**

```bash
make db-test
```

Expected: `has_function` fails.

- [ ] **Step 3: Commit**

```bash
git add supabase/tests/database/32_create_run_rpc.sql
git commit -m "test(db): add create_run RPC test (RED)"
```

---

### Task 26: Implement `create_run` RPC

**Files:**
- Create: `supabase/migrations/20260430120600_create_run_rpc.sql`

- [ ] **Step 1: Write the migration**

Create `supabase/migrations/20260430120600_create_run_rpc.sql`:

```sql
-- 20260430120600_create_run_rpc.sql
-- create_run(input jsonb) — SECURITY DEFINER insert into runs.
--
-- input shape: {
--   "ticker":     text,
--   "trade_date": date (ISO),
--   "config":     jsonb
-- }
--
-- Validates:
--   - caller is authenticated
--   - caller has profiles.allowed_at set (not waitlisted)
--   - required keys are present and well-typed

create function public.create_run(input jsonb)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_user_id   uuid := auth.uid();
  v_allowed   timestamptz;
  v_ticker    text;
  v_trade_date date;
  v_config    jsonb;
  v_run_id    uuid;
begin
  if v_user_id is null then
    raise exception 'not authenticated' using errcode = '28000';
  end if;

  select allowed_at into v_allowed
    from public.profiles
   where id = v_user_id;

  if v_allowed is null then
    raise exception 'beta access pending' using errcode = '42501';
  end if;

  v_ticker     := input->>'ticker';
  v_trade_date := (input->>'trade_date')::date;
  v_config     := input->'config';

  if v_ticker is null or length(v_ticker) = 0 then
    raise exception 'ticker is required' using errcode = '22023';
  end if;
  if v_trade_date is null then
    raise exception 'trade_date is required' using errcode = '22023';
  end if;
  if v_config is null then
    raise exception 'config is required' using errcode = '22023';
  end if;

  insert into public.runs (user_id, ticker, trade_date, config)
  values (v_user_id, v_ticker, v_trade_date, v_config)
  returning id into v_run_id;

  return v_run_id;
end;
$$;

revoke all on function public.create_run(jsonb) from public, anon;
grant execute on function public.create_run(jsonb) to authenticated;
```

- [ ] **Step 2: Apply and run tests — expect pass**

```bash
make db-reset
make db-test
```

Expected: all 10 test files green.

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/20260430120600_create_run_rpc.sql
git commit -m "feat(db): add create_run RPC with allowlist check (GREEN)"
```

---

## Phase 8 — Seed data & cold-start verification

### Task 27: Add `seed.sql` with one allowlisted dev user

**Files:**
- Modify: `supabase/seed.sql`

- [ ] **Step 1: Write the seed**

Open `supabase/seed.sql` (created by `supabase init`) and replace its contents with:

```sql
-- supabase/seed.sql
-- Local-dev seed: one allowlisted user so /login works on a fresh DB.
-- Runs after migrations on `supabase db reset`.

-- Create a dev user. Email is fixed; password is irrelevant for magic-link.
do $$
declare
  v_user_id uuid;
begin
  -- If the user already exists (re-run), skip.
  select id into v_user_id from auth.users where email = 'dev@snapsonic.local';
  if v_user_id is not null then
    return;
  end if;

  -- supabase_test_helpers will create the user + a matching profiles row
  -- via the on_auth_user_created trigger.
  v_user_id := tests.create_supabase_user('dev@snapsonic.local');

  -- Mark allowed.
  update public.profiles
     set allowed_at = now(), display_name = 'Dev'
   where id = v_user_id;
end;
$$;
```

- [ ] **Step 2: Reset and verify the seed runs**

```bash
make db-reset
```

Expected: no errors. Then:

```bash
supabase db psql -c "select email, allowed_at from public.profiles join auth.users using (id);"
```

Expected: one row with `email = dev@snapsonic.local` and a non-null `allowed_at`.

- [ ] **Step 3: Commit**

```bash
git add supabase/seed.sql
git commit -m "chore(db): seed allowlisted dev user for local"
```

---

### Task 28: Cold-start smoke

**Files:** none (verification only)

- [ ] **Step 1: Stop everything**

```bash
make db-down
```

- [ ] **Step 2: Cold start, reset, test**

```bash
make db-up
make db-reset
make db-test
```

Expected: all 10 pgTAP files pass, ending with `# All tests successful.` and a summary like `1..N` where N is the total assertions across all files.

- [ ] **Step 3: Confirm seed user is present after cold start**

```bash
supabase db psql -c "select email, allowed_at from public.profiles join auth.users using (id);"
```

Expected: `dev@snapsonic.local` row.

No commit — verification only.

---

## Phase 9 — CI

### Task 29: Add GitHub Actions workflow that runs `supabase test db`

**Files:**
- Create: `.github/workflows/foundation-ci.yml`

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/foundation-ci.yml`:

```yaml
name: Foundation CI

on:
  pull_request:
    paths:
      - 'supabase/**'
      - '.github/workflows/foundation-ci.yml'
  push:
    branches:
      - main
    paths:
      - 'supabase/**'

jobs:
  pgTAP:
    name: pgTAP database tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Supabase CLI
        uses: supabase/setup-cli@v1
        with:
          version: latest

      - name: Start local Supabase
        run: supabase start

      - name: Reset DB (apply migrations + seed)
        run: supabase db reset

      - name: Run pgTAP tests
        run: supabase test db

      - name: Stop local Supabase
        if: always()
        run: supabase stop --no-backup
```

- [ ] **Step 2: Lint the YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/foundation-ci.yml'))"
```

Expected: no output (success). If you don't have Python's `yaml`, use `yamllint` or just visually inspect.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/foundation-ci.yml
git commit -m "ci: run pgTAP tests on every PR touching supabase/"
```

---

### Task 30: Open a draft PR to trigger CI

**Files:** none (PR action)

- [ ] **Step 1: Reconfigure remotes**

The freshly-cloned `origin` points at TauricResearch's upstream. We push to the user's repo at `https://github.com/elagerway/tradingagents` instead. Rename and re-add:

```bash
git remote rename origin upstream
git remote add origin https://github.com/elagerway/tradingagents.git
git remote -v
```

Expected output:
```
origin    https://github.com/elagerway/tradingagents.git (fetch)
origin    https://github.com/elagerway/tradingagents.git (push)
upstream  https://github.com/TauricResearch/TradingAgents.git (fetch)
upstream  https://github.com/TauricResearch/TradingAgents.git (push)
```

This setup keeps `git fetch upstream` available for pulling in upstream engine releases later.

- [ ] **Step 2: Push the branch**

```bash
git push -u origin feature/foundation
```

If `origin` doesn't have a `main` branch yet, push that first:

```bash
git checkout main
git push -u origin main
git checkout feature/foundation
git push -u origin feature/foundation
```

- [ ] **Step 3: Open a draft PR**

```bash
gh pr create --draft --title "Plan 1: Foundation — schema, RLS, vault" \
  --body "$(cat <<'EOF'
## Summary

- Monorepo skeleton: `apps/api/`, `apps/web/`, `supabase/`
- Supabase schema: profiles, api_keys, runs (all RLS-protected)
- pgsodium-backed BYO key vault (`vault_save_key`, `vault_load_keys`)
- `create_run()` SECURITY DEFINER RPC with allowlist check
- 10 pgTAP test files covering schema + RLS + RPC behavior
- GitHub Actions workflow runs all tests on every PR

## Plan

[`docs/superpowers/plans/2026-04-30-foundation.md`](docs/superpowers/plans/2026-04-30-foundation.md)

## Test plan

- [x] All migrations apply cleanly (`make db-reset`)
- [x] All pgTAP tests pass locally (`make db-test`)
- [ ] CI green
- [ ] Manually verified seed user exists after `supabase db reset`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: Watch CI**

```bash
gh pr checks --watch
```

Expected: all checks green.

If CI fails, read the logs (`gh run view --log-failed`) and fix locally before pushing again. **Do not merge until CI is green.**

No additional commit unless fixes are needed.

---

## Phase 10 — Provision Supabase Cloud

### Task 31: Create a Supabase Cloud project

**Files:** none (manual external step)

- [ ] **Step 1: Create the project**

In the Supabase dashboard (https://app.supabase.com):

1. Click **New project**.
2. Organization: choose or create the Snapsonic org.
3. Name: `tradingagents-beta` (or your preferred name).
4. Region: pick closest to your users (e.g. `us-east-1`).
5. Database password: generate a strong one and store it in your password manager.
6. Plan: Free tier is fine for the closed beta.

Wait ~2 minutes for the project to provision.

- [ ] **Step 2: Capture the project ref + keys**

From the dashboard's **Project Settings → API** page, capture:
- Project URL: `https://<ref>.supabase.co`
- `anon` public key
- `service_role` key (secret — store in 1Password or similar)
- Project ref (the `<ref>` portion of the URL)

These will populate Plans 2 and 3's environment variables. **Do not commit any of them.**

- [ ] **Step 3: Create `.env.example` documenting the names**

Create `apps/.env.example` (committable):

```
# Populate from your Supabase Cloud project (Settings -> API).
# Plans 2 (apps/api/.env) and 3 (apps/web/.env*.local) consume these.

NEXT_PUBLIC_SUPABASE_URL=https://your-ref.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOi...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOi...
SUPABASE_JWT_SECRET=...
```

- [ ] **Step 4: Commit the example file**

```bash
git add apps/.env.example
git commit -m "docs: add apps/.env.example documenting required Supabase env vars"
```

---

### Task 32: Link local repo to the Cloud project + push migrations

**Files:** none (CLI configuration; secrets stay out of git)

- [ ] **Step 1: Link**

```bash
supabase link --project-ref <ref-from-task-31>
```

You'll be prompted for the database password from Task 31, step 1.

- [ ] **Step 2: Diff (sanity check)**

```bash
supabase db diff
```

Expected: shows the migrations from `supabase/migrations/` will be applied (project is empty).

- [ ] **Step 3: Push migrations**

```bash
supabase db push
```

Expected: each migration applies in order. Should take ~30 seconds.

- [ ] **Step 4: Verify cloud schema**

```bash
supabase db psql --linked -c "\dt public.*"
```

Expected: lists `profiles`, `api_keys`, `runs`.

```bash
supabase db psql --linked -c "select count(*) from public.profiles;"
```

Expected: `0` (the cloud DB has no seed users — that's local-dev only).

No commit — this is a deploy step. The `supabase/.temp/` directory may now hold a project-link metadata file; it's already gitignored from Task 2.

---

### Task 33: Final-state checklist

**Files:** none

- [ ] **Step 1: Confirm green status**

Run through this list and check off each item:

- [ ] `make db-test` passes locally (10 files green)
- [ ] CI is green on the draft PR
- [ ] `supabase db psql --linked -c "\dt public.*"` lists `profiles`, `api_keys`, `runs` on the cloud project
- [ ] `apps/.env.example` exists and is committed
- [ ] **Real** Supabase URL + anon key + service_role key are stored somewhere safe (password manager) — *not* in git
- [ ] `feature/foundation` branch has ~30 commits, each green at HEAD

- [ ] **Step 2: Mark the PR ready for review**

If working alone, just merge:

```bash
gh pr merge --squash --delete-branch
```

If working with reviewers, mark ready:

```bash
gh pr ready
```

After merge, delete the local branch:

```bash
git checkout main && git pull && git branch -D feature/foundation
```

**Plan 1 is done.** Plan 2 (FastAPI service) is now unblocked.

---

## Self-Review — what did the spec say, and is it covered?

### Spec coverage

| Spec section | Covered by tasks |
|---|---|
| §3 stack: Supabase Auth + Postgres + pgsodium | Tasks 5, 14, 16, 19, 21 |
| §5.3 schema: profiles, api_keys, runs (3 tables) | Tasks 11, 16, 23 |
| §5.3 RLS: profiles, api_keys, runs | Tasks 13, 16 (api_keys), 23, plus tests 12, 17, 24 |
| §5.3 pgsodium key rotation strategy | Out of scope for v1 (master key created in Task 14; rotation is a future task per spec) |
| §6 BYO key flow steps 1–3 | `vault_save_key` (Task 19), `vault_load_keys` (Task 21) |
| §7 row #12: waitlisted user blocked at `createRun` | `create_run` allowlist check (Task 26) + test (Task 25) |
| §8 testing strategy: pgTAP RLS assertions in CI | Tasks 12, 17, 24, 29 |
| §9 repo layout: `supabase/migrations/`, `supabase/tests/database/` | Phase 1–7 (entire layout) |

**Gaps?** None I see. The spec's §10 ("no queue" rationale) is documentation, not implementation. §11 decisions log is metadata. §12 open questions (domain, email sender, Render plan, branding) are deferred to later plans.

### Placeholder scan

- No "TBD"/"TODO"/"implement later" anywhere.
- Every code block contains real, runnable code.
- Every command has expected output.
- File paths are absolute or unambiguously repo-relative.

### Type/name consistency

- `vault_save_key(text, text)` defined in Task 19, called the same way in Task 18 test.
- `vault_load_keys(uuid, text[])` defined in Task 21, called the same way in Task 20 test.
- `create_run(jsonb)` defined in Task 26, called the same way in Task 25 test.
- `_byo_master_key_id()` defined in Task 14, called by Tasks 19 + 21.
- `tests.create_supabase_user`, `tests.authenticate_as`, `tests.get_supabase_uid` from Basejump helpers (Task 9), used consistently throughout.

No drift detected.

---

## Execution handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-30-foundation.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
