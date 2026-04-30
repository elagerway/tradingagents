# Design — Stand TradingAgents up as a hosted application

- **Date:** 2026-04-30
- **Status:** Approved (sections 1–5)
- **Author:** Erik (Snapsonic) + Claude (via Superpowers `brainstorming`)
- **Source repo:** https://github.com/TauricResearch/TradingAgents (cloned to `/Users/erik/Developer/Github/Snapsonic/tradingAgents`)
- **Next step:** invoke `superpowers:writing-plans` to produce an implementation plan

---

## 1. Goal

Take the existing TauricResearch `tradingagents` Python package — a LangGraph multi-agent framework that emits a trading decision for a `(ticker, date)` pair — and stand it up as a **hosted web application** for a closed beta of 10–200 trusted invitees who supply their own LLM API keys.

The upstream engine is treated as a black box: we wrap it, never fork it. The "application" is everything around the engine — auth, history, BYO-key vault, live agent streaming UI.

## 2. Scope

### v1 (this design)

- Auth-gated web app at a single URL.
- Magic-link login, allowlisted (no public sign-up).
- BYO API keys per user, encrypted at rest.
- One-click "new run" form with sensible defaults.
- Live streaming view of agent activity while a run executes.
- Persistent history of every user's past runs and decisions.
- Operates as a closed beta (≤200 users), no billing.

### Explicitly out of scope for v1 (roadmap)

These are deferred to discrete future projects, each with their own brainstorm → spec → plan cycle:

| Phase | Feature | Approx. complexity |
|---|---|---|
| v1.1 | Per-user concurrency cap | trivial (one `int` column + one check) |
| v2 | Watchlist of saved tickers with one-click re-run | small |
| v3 | Compare runs view (same ticker different dates, or different tickers same date) | small |
| v4 | Paper-trading portfolio + P&L tracking | large (backtest plumbing, time-series chart, P&L math) |
| v5 | Recurring runs / alerts (cron-driven, email notifications) | medium |
| v6 | Public sign-up + Stripe billing + plan tiers | large |

The v1 architecture is shaped so each phase above is additive — no rewrites required.

### Anti-goals

- We do not modify upstream `tradingagents/` source code in v1. All wrapping happens around it.
- We do not run the LLM on our infrastructure. Users bring their own keys.
- We do not implement a job queue. The browser's SSE connection is the queue. (See §10.)
- We do not snapshot the UI in tests. We do not chase 100% coverage.

## 3. Stack

| Concern | Choice | Why |
|---|---|---|
| Frontend & SSR | **Next.js (App Router) on Vercel** | App Router for nested layouts; Vercel for zero-ops deploys |
| Python engine host | **Render Web Service** | User already operates Render; long-running processes work cleanly with SSE; Dockerfile-first |
| Auth | **Supabase Auth** (magic link) | Tight Postgres integration; allowlist enforced via DB column |
| Database | **Supabase Postgres** | Same vendor as auth; RLS policies isolate user data |
| BYO key storage | **`pgsodium`** (Supabase's transparent encryption) | At-rest encryption with vault-backed keys; decrypts only on Render via service-role RPC |
| Component library | **shadcn/ui + Tailwind** | Vercel-native, copy-paste components, no runtime dependency |
| Streaming protocol | **Server-Sent Events (SSE)** | One-way is sufficient; native `EventSource` reconnect with `Last-Event-ID` |
| Browser → Python auth | **Supabase JWT verified against JWKS on Render** | Stateless; Render doesn't hold sessions |

## 4. Architecture

```
                                              ┌───────────────────┐
                                              │   Browser         │
                                              │  (Next.js client) │
                                              └────┬─────────┬────┘
                                                   │         │
                            HTTPS (auth, pages,    │         │ HTTPS + SSE
                            run history, BYO key   │         │ (live agent
                            settings)              │         │  events)
                                                   ▼         ▼
                                  ┌──────────────────┐   ┌──────────────────────┐
                                  │   Vercel         │   │   Render             │
                                  │   Next.js App    │   │   FastAPI engine     │
                                  │   (App Router)   │   │   (tradingagents     │
                                  │                  │   │    package as-is)    │
                                  │   - SSR pages    │   │                      │
                                  │   - Server       │   │   - JWT verify       │
                                  │     Actions      │   │   - Run executor     │
                                  │   - Supabase     │   │   - LangGraph        │
                                  │     SSR client   │   │     callbacks → SSE  │
                                  └────────┬─────────┘   └──────────┬───────────┘
                                           │                        │
                                           │   service-role         │   service-role
                                           │   (writes runs,        │   (read BYO keys,
                                           │   reads user data      │   write final
                                           │   subject to RLS)      │   decision)
                                           ▼                        ▼
                                  ┌──────────────────────────────────────────────┐
                                  │   Supabase                                   │
                                  │   - Auth (magic link, allowlisted)           │
                                  │   - Postgres: profiles, api_keys, runs       │
                                  │   - pgsodium: encrypted BYO keys at rest     │
                                  │   - RLS: users see only their own data       │
                                  └──────────────────────────────────────────────┘
```

The split: **Vercel handles "everything that's a page or a record" — auth, history, settings. Render handles "everything that takes minutes and streams" — the agent run itself.** Supabase is the shared truth between them, with RLS keeping users isolated automatically.

The browser talks to two origins (Vercel + Render). That's a small CORS configuration, not a real complexity, and it's the price for keeping the long-running stream off Vercel's clock.

## 5. Components

### 5.1 Vercel — Next.js app

**Pages** (App Router, all auth-gated except `/login`):

- `/login` — Supabase magic-link form. After click-through, allowlist check runs server-side; non-allowlisted users see a "request access" message. No public sign-up in v1. Authenticated users hitting `/login` are redirected to `/`.
- `/` — runs list. Table of past runs (ticker, date, status, decision, started). Click → `/runs/[id]`.
- `/runs/new` — form: ticker, trade date, provider, deep model, quick model, debate rounds, analysts to enable. Sensible defaults from `default_config.py`.
- `/runs/[id]` — live view. Agent timeline as SSE events arrive; for completed runs, hydrates from Supabase instead of streaming.
- `/settings` — BYO API keys, paste-once-show-masked UX.

**Server Actions** (small surface):

- `saveApiKey(provider, key)` — upsert into `api_keys` with pgsodium encryption.
- `deleteApiKey(provider)` — soft-delete.
- `createRun(input)` — insert a `runs` row in `pending`, return `run_id`.

**Client packages:** `@supabase/ssr`, `shadcn/ui`, Tailwind, native `EventSource`.

### 5.2 Render — FastAPI service

**Endpoints:**

- `POST /runs/{run_id}/start` — auth header carries the user's Supabase JWT. Verifies token, loads the run row + the user's BYO keys, kicks off `TradingAgentsGraph().propagate()` in a background asyncio task, returns `202 Accepted`.
- `GET /runs/{run_id}/stream` — SSE. Subscribes to an in-process pub/sub keyed by `run_id`. Replays buffered events on reconnect (last ~200 events per active run kept in a ring buffer).
- `GET /healthz` — Render health check.

**Internal modules:**

- `auth.py` — JWT verification against Supabase JWKS (cached for 24h).
- `keys.py` — fetches + decrypts only the BYO keys actually needed by the run's chosen config (e.g., if the run uses OpenAI + Alpha Vantage, we don't decrypt Anthropic). Calls a service-role Supabase RPC that wraps `pgsodium` decryption. The RPC also bumps `last_used_at` for each returned key. Plaintext lives only in process memory; never logged; goes out of scope when the run ends.
- `engine.py` — wraps `TradingAgentsGraph` with a callback that translates LangGraph node lifecycle events into typed SSE messages (`{type: "node_start", node: "fundamentals_analyst"}`, etc.).
- `bus.py` — tiny in-process pub/sub (`asyncio.Queue` per `run_id`) with a ring buffer for `Last-Event-ID` replay.
- `worker.py` — background task entry point. On completion, writes final decision + full transcript to Supabase, sets `runs.status='completed'`, closes the bus topic.
- `janitor.py` — periodic task (every 5 min) that marks any `running` row older than 30 min as `failed`.

### 5.3 Supabase — schema (3 tables, all RLS-protected)

```sql
-- profiles
id            uuid primary key references auth.users(id) on delete cascade
email         text not null
display_name  text
allowed_at    timestamptz   -- null = waitlisted, non-null = beta member
created_at    timestamptz default now()

-- api_keys (BYO)
user_id       uuid not null references auth.users(id) on delete cascade
provider      text not null check (provider in (
                'openai','anthropic','google','xai','deepseek',
                'dashscope','zhipu','openrouter','alpha_vantage'
              ))
key_encrypted bytea not null    -- pgsodium-encrypted
last_used_at  timestamptz
created_at    timestamptz default now()
primary key (user_id, provider)

-- runs
id              uuid primary key default gen_random_uuid()
user_id         uuid not null references auth.users(id) on delete cascade
ticker          text not null
trade_date      date not null
status          text not null check (status in ('pending','running','completed','failed'))
config          jsonb not null               -- snapshot of user's choices
events          jsonb default '[]'::jsonb    -- append-only event log written by Render during/after run
final_decision  jsonb                        -- null until completed
error           text                         -- non-null on failure
created_at      timestamptz default now()
started_at      timestamptz
completed_at    timestamptz
```

**RLS policies (sketch):**

- `profiles`: `select where id = auth.uid()`. Inserts via a trigger on `auth.users`.
- `api_keys`: full CRUD where `user_id = auth.uid()`.
- `runs`: full select where `user_id = auth.uid()`. Inserts are denied for `authenticated` role — the Server Action calls a SECURITY DEFINER function `create_run(input)` that re-checks `auth.uid()` and inserts on the user's behalf. Updates on Render-side use the service role and bypass RLS.

**pgsodium key-rotation strategy:** one key for the whole instance, stored in Supabase Vault. Re-encrypt-on-rotation handled offline if/when needed.

## 6. Data flow (lifecycle of a single run)

```
TIME  BROWSER                 VERCEL (Next.js)         RENDER (FastAPI)         SUPABASE (Postgres)
────  ───────────────────     ──────────────────       ──────────────────       ──────────────────────
t0    User submits ticker
      via /runs/new form  ──▶ Server Action
                              "createRun(input)"   ──────────────────────────▶  insert runs row
                                                                                (status='pending')
                                                                                returns run_id
                              ◀─── return run_id ────────────────────────────
      Client navigates
      to /runs/[id]      ◀──  redirect (SSR shell)
      ─────────────────────────────────────────────────────────────────────────
t1    EventSource opens
      to Render:
      GET /runs/{id}/stream ─────────────────────▶  verify Supabase JWT
                                                     against JWKS (cached)
                                                     │
                                                     │  fetch run row + BYO keys
                                                     │ ─────────────────────────▶  select runs where id=$1
                                                     │                              and user_id=jwt.sub
                                                     │                              call rpc decrypt_keys()
                                                     │ ◀──────────────────────── { config, plaintext_keys }
                                                     │
                                                     │  spawn asyncio task:
                                                     │    TradingAgentsGraph(
                                                     │      config,
                                                     │      callbacks=[SSEPublisher(bus, run_id)]
                                                     │    ).propagate(ticker, date)
                                                     │
                                                     │  attach SSE response
                                                     │  to bus.subscribe(run_id)
                                                     │
                                                     │  also: update runs row ──▶  update runs set
                                                     │                              status='running',
                                                     │                              started_at=now()
      ◀─── data: {type:"run_started"} ─────────────  emit on bus
      ─────────────────────────────────────────────────────────────────────────
t2..N LangGraph executes; each
      node lifecycle hits the
      LangChain callback,
      which the SSEPublisher
      converts to events on
      the bus ─────────────────────────────────────  events flow:
                                                     - node_start(market_analyst)
                                                     - tool_call(get_stock_data)
                                                     - node_end(market_analyst, summary)
                                                     - debate_round(bull_msg)
                                                     - debate_round(bear_msg)
                                                     - node_end(research_manager)
                                                     - trader_decision
                                                     - risk_round_*
                                                     - portfolio_manager_decision
      ◀─── data: {type:"node_end",...} (per event)
      UI reveals progressively
      (timeline panel updates)
      ─────────────────────────────────────────────────────────────────────────
tN+1                                                  background task finishes:
                                                       write final state ──────▶  update runs set
                                                                                  status='completed',
                                                                                  final_decision=$1,
                                                                                  events=$2,
                                                                                  completed_at=now()
                                                       emit final event on bus
      ◀─── data: {type:"completed",
            decision:"BUY"} ────────────────────────  bus.close(run_id)
      EventSource closes
      Client refreshes server
      component                ──▶  RSC re-fetches
                                    runs row     ──────────────────────────▶  select runs where id=$1
                                                                                (RLS: user_id=auth.uid)
```

### Plain-English summary

1. **Submit.** User fills `/runs/new`. Server Action validates input, inserts a `pending` row, returns the `run_id`, redirects to `/runs/[id]`. **No LLM call yet.**
2. **Connect.** `/runs/[id]` opens an SSE connection to Render with the user's Supabase JWT. Render validates the token (against Supabase's JWKS, cached 24h), confirms the run belongs to the user, fetches+decrypts the BYO keys, and starts the agent run as an asyncio task.
3. **Stream.** Each LangGraph node's start/end (and tool calls inside) hits a callback that publishes a structured event onto an in-process bus keyed by `run_id`. The SSE response subscribes to that bus and forwards events to the browser. UI renders them into a timeline as they arrive.
4. **Persist.** When the agent run completes (success or failure), the worker writes the final state — full event log, decision, error if any — to the `runs` row and sets `status='completed'` (or `'failed'`). It then publishes a terminal event and closes the bus topic.
5. **Hydrate.** Browser sees the terminal event, closes its EventSource, and triggers a server-component re-render. Now the page reads from Supabase via SSR — same view, but durable.

### Reconnect & history

- **Reconnect during a live run:** SSE endpoint honors `Last-Event-ID`. The bus keeps the last ~200 events per active run in a ring buffer. On reconnect we replay from that ID forward. If the run finished while disconnected, the endpoint returns the final event and closes.
- **Re-opening a completed run:** `/runs/[id]` detects `status='completed'` server-side and never opens an SSE connection. It renders the timeline directly from `runs.events` jsonb. Same component, two data sources.

### BYO key flow (security-critical)

1. User pastes key on `/settings`. Server Action calls Supabase RPC `vault_save_key(user_id, provider, plaintext)`, which uses `pgsodium` to encrypt with the instance's vault key, then inserts into `api_keys.key_encrypted` as `bytea`. **Plaintext leaves Vercel's memory immediately.**
2. When Render needs the key, it calls a service-role RPC `vault_load_keys(user_id, providers[])` that takes the *minimum* set of providers needed for this run, decrypts only those, returns plaintext, and bumps `last_used_at` for each. Render puts plaintext into a Python dict passed to LangGraph; never logs it; never persists it; the dict goes out of scope when the run ends.
3. UI never re-displays plaintext — settings page shows only the masked last-4.

## 7. Error handling & failure modes

| # | Failure | Where it surfaces | Behavior |
|---|---|---|---|
| 1 | User has no BYO key for chosen provider | Render, **synchronously during `POST /runs/{id}/start`, before the asyncio task is spawned** | Fail fast: `runs.status='failed'`, `error="No API key configured for openai. Add one in Settings."`, emit `{type:"error",...}` on bus, close bus, return HTTP 400 from the start endpoint. UI shows banner + deep link to `/settings`. |
| 2 | BYO key invalid (401 from provider) | Inside run, on first call | Same shape as #1, with the provider's response. UI: "OpenAI rejected your key — re-add it." |
| 3 | Provider rate limit (429) | During run | LangGraph's existing retry handles transient ones. Exhausted retries → fail with `error="Provider rate limit exceeded after 3 retries"`. |
| 4 | Provider 5xx / timeout | During run | Same as #3. |
| 5 | LangGraph hits `max_recur_limit` (100) | During run | Fail with `error="Agent recursion limit exceeded"`. Surface partial event log so user sees where it spun. |
| 6 | yfinance / Alpha Vantage data fetch fails | Tool call inside an analyst | Tool returns error string; analyst proceeds with partial data. Don't fail the run. (Existing CLI behavior — unchanged.) |
| 7 | Render process dies mid-run (OOM, deploy, crash) | SSE drops | Browser EventSource auto-reconnects with `Last-Event-ID`. If run is still in-process, replay from buffer. If process restarted, bus is empty: row is `running` in Supabase but unreachable. **Janitor marks `running` rows older than 30 min as `failed`.** User clicks "retry". |
| 8 | Browser disconnects (tab closed, sleep, network drop) | SSE drops | Run continues server-side. On return to `/runs/[id]`, page reconnects to the bus if live, or renders from Supabase if finished. **User never loses a run by closing the tab.** |
| 9 | Vercel ↔ Render network blip during SSE | SSE drops | Same as #8 — auto reconnect with replay. |
| 10 | Supabase write fails when persisting final result | Render worker, after run completes | Retry 3× with backoff. If still failing, log loudly and emit `{type:"error",...}` on bus. User gets the decision in real-time but history won't show it until manual fix. (Rare; v1 accepts the risk.) |
| 11 | Bad JWT (expired, malformed, wrong signer) | Render, on SSE handshake | 401. Browser refreshes Supabase session, retries once. Still 401 → redirect to `/login`. |
| 12 | Waitlisted user (no `allowed_at`) tries to run | Vercel, in `createRun` Server Action | Returns error string; form shows "Beta access pending — we'll email you." No row created. |
| 13 | Two browser tabs on same `/runs/[id]` | Both subscribe to bus | Fine — bus fan-outs to N subscribers. `Last-Event-ID` keeps them in sync. |
| 14 | Same user submits 5 runs concurrently | Render | No per-user concurrency cap in v1. Beta users are trusted. (v1.1 adds `profiles.max_concurrent_runs`.) |
| 15 | Engine code raises unhandled Python exception | Render worker | Outer try/except in `worker.py`: `runs.status='failed'`, `error=str(e)[:1000]`, emit `{type:"error"}`, close bus. Full exception goes to Render structured logs (with run_id) for debugging. |

### Cross-cutting principles

- **Fail loudly to the user, fail safely in the DB.** Every error path ends with `runs.status='failed'` and a human-readable `error` field. No "stuck in `running` forever."
- **The janitor is the safety net.** A periodic Render task (every 5 min) scans for `running` rows whose `started_at` is older than 30 min — marks them `failed` with `error="Run timed out or worker died"`.
- **Logs go to Render, secrets never go to logs.** Logging middleware redacts BYO key plaintext from any log line. We log JWT subject (user_id) and run_id liberally.
- **No silent degradation.** If a tool call fails inside an analyst, that analyst's report says so explicitly. The downstream Trader/Portfolio Manager sees that and weights accordingly.
- **No retries on the user's side for cost reasons.** A retry costs $0.50–$5. We never auto-retry an entire run; we surface failure clearly and let the user decide. Only retries we do are *inside* a single run (provider rate-limit → retry one LLM call).

## 8. Testing strategy

The Superpowers TDD skill expects RED-GREEN-REFACTOR for new code. We don't mock LLM providers in CI — instead, the strategy is **shaped around making the LLM unreachable in tests** via a fake engine.

### What we test

**1. Engine layer (upstream `tradingagents` package) — leave alone.** Upstream's `tests/` runs as-is in CI. We don't modify it. If upstream breaks, we know immediately.

**2. FastAPI layer — full unit + integration coverage.**

| Module | What we test | How |
|---|---|---|
| `auth.py` (JWT verify) | Valid JWT passes; expired/wrong-signer/malformed all 401 | Static keypair, sign test JWTs locally |
| `keys.py` (BYO key fetch) | Returns correct keys; raises on missing key for chosen provider; never logs plaintext (assertion on `caplog`) | Mock Supabase RPC at the httpx layer |
| `bus.py` (pub/sub) | Multi-subscriber fan-out; `Last-Event-ID` replay from ring buffer; `bus.close()` ends all subscribers | pytest-asyncio, no external deps |
| `engine.py` (callback adapter) | Given a fake LangGraph callback sequence, produces the expected SSE event sequence | A `FakeTradingAgentsGraph` that emits a canned script through the real callback machinery — no LLM calls |
| `POST /runs/{id}/start` | Auth gate, ownership check, BYO-key check, kicks off worker | TestClient + fake engine |
| `GET /runs/{id}/stream` | SSE format correctness, `Last-Event-ID` reconnect, terminal close on completion | httpx streaming client |
| `worker.py` exception path | Unhandled Python error → `runs.status='failed'`, error written, bus closed | Fake engine that raises mid-run |
| Janitor | `running` rows older than 30 min get marked `failed` | Time-travel via a `now()` injection point |

Stack: `pytest`, `pytest-asyncio`, `httpx`, `freezegun`.

**3. Next.js layer — vitest for logic, Playwright for one smoke path.**

- **vitest:** form validation in `/runs/new`, masking logic in `/settings`, allowlist gate in auth callback. No component snapshot tests.
- **Playwright (one smoke test):** log in → create run → see ≥3 SSE events arrive → wait for `completed` → confirm row appears on `/`. Runs against a Vercel preview + a Render preview, both pointing at a dedicated `staging` Supabase project. Fake engine is enabled via `USE_FAKE_ENGINE=1` so the smoke test costs $0 and finishes in <30s. The same Playwright test runs against the real engine once per release on manual workflow dispatch.

**4. Supabase RLS — pgTAP-style policy assertions.**

A `tests/rls.sql` file uses `set role authenticated; set request.jwt.claim.sub = '<user-a-uuid>'` to impersonate users. Asserts:

- User A cannot select User B's runs.
- User A cannot read User B's `api_keys`.
- Service role (used by Render) can read any row but only via `vault_load_keys`.
- A waitlisted user (no `allowed_at`) cannot insert into `runs`.

Run as part of `supabase db reset` in CI.

**5. End-to-end against real LLMs — once per release, manual.**

A `pnpm test:e2e:real` workflow runs the same Playwright smoke test against the real engine with a *test* OpenAI key (cheap model, single debate round). One run, one ticker, asserts a decision is produced. Costs ~$0.10–$0.50 per release.

### What we don't do

- Snapshot tests of UI markup
- 100% coverage targets
- Mocking LLM providers in unit tests (use the fake engine)
- Load testing at v1 scale
- Visual regression testing

### CI shape (GitHub Actions, two parallel jobs)

```
┌─ python ─────────────┐    ┌─ web ─────────────────────┐
│ uv sync              │    │ pnpm install              │
│ pytest tests/        │    │ pnpm lint                 │
│ pytest apps/api/     │    │ pnpm test                 │
│ supabase db reset \  │    │ playwright test (smoke,   │
│   --include rls.sql  │    │   fake engine)            │
└──────────────────────┘    └───────────────────────────┘
```

Each job ~3–5 min. Total wall time on a green PR: ~5 min.

### TDD discipline going forward

Every new FastAPI module starts with a failing test. Every Server Action with non-trivial logic starts with a failing test. We don't write implementation before red. Fake engine + JWT signing helpers + Supabase test fixtures are built once early and reused.

## 9. Repository layout (proposed)

```
tradingAgents/                          # existing repo, unchanged
├── tradingagents/                      # upstream package — DO NOT MODIFY
├── cli/                                # upstream CLI — DO NOT MODIFY
├── tests/                              # upstream tests — keep green
├── apps/                               # NEW — our application code
│   ├── api/                            # FastAPI service deployed to Render
│   │   ├── pyproject.toml              # depends on the upstream tradingagents pkg
│   │   ├── Dockerfile                  # for Render deploy
│   │   ├── src/api/
│   │   │   ├── main.py                 # FastAPI app
│   │   │   ├── auth.py
│   │   │   ├── keys.py
│   │   │   ├── engine.py               # LangGraph callback adapter
│   │   │   ├── bus.py
│   │   │   ├── worker.py
│   │   │   └── janitor.py
│   │   └── tests/
│   │       ├── fakes/fake_engine.py    # FakeTradingAgentsGraph
│   │       ├── test_auth.py
│   │       ├── test_keys.py
│   │       ├── test_bus.py
│   │       ├── test_engine.py
│   │       ├── test_routes.py
│   │       └── test_janitor.py
│   └── web/                            # Next.js app deployed to Vercel
│       ├── package.json
│       ├── next.config.ts
│       ├── tailwind.config.ts
│       ├── app/
│       │   ├── (auth)/login/page.tsx
│       │   ├── (app)/page.tsx          # runs list
│       │   ├── (app)/runs/new/page.tsx
│       │   ├── (app)/runs/[id]/page.tsx
│       │   ├── (app)/settings/page.tsx
│       │   └── api/                    # minimal — most logic in Server Actions
│       ├── lib/
│       │   ├── supabase/server.ts
│       │   ├── supabase/client.ts
│       │   └── actions/
│       │       ├── createRun.ts
│       │       ├── saveApiKey.ts
│       │       └── deleteApiKey.ts
│       ├── components/                 # shadcn/ui composed components
│       └── tests/
│           ├── unit/                   # vitest
│           └── e2e/                    # playwright smoke
├── supabase/                           # NEW — Supabase migrations, RLS, RPC
│   ├── config.toml
│   ├── migrations/
│   │   ├── 0001_init.sql               # tables + RLS + indexes
│   │   ├── 0002_pgsodium_keys.sql      # encryption setup + RPCs
│   │   └── 0003_allowlist.sql
│   └── tests/
│       └── rls.sql                     # pgTAP-style RLS assertions
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-04-30-tradingagents-app-design.md   # this document
```

Notes:
- `apps/api/` reuses the upstream package as a *dependency* (installed via `pip install -e ../../`). No source modifications upstream.
- `apps/web/` and `apps/api/` are independently deployable.
- `supabase/` migrations run via the Supabase CLI in CI and on local dev.

## 10. Why "no queue" and "in-process bus"

For v1 we have one Render machine. The browser connects directly to that machine. We don't need cross-machine event distribution until we scale to N replicas, and at that point Render (or any host) can pin SSE connections via sticky session routing or we move to Supabase Realtime / Redis-backed pub/sub. **Approach 3 (queue + Realtime) from the brainstorm is the well-defined v3+ migration path** — the engine code doesn't change, we just swap out `bus.py` and add a worker process. This is intentional YAGNI: build for the load we have.

## 11. Decisions log

| Topic | Choice | Alternatives considered | Why |
|---|---|---|---|
| App shape | Hosted multi-user web app | Local CLI only; single-user web app; API-only; OSS self-host | User picked C (hosted multi-user) |
| Audience | Closed beta, 10–200 users | Internal tool; public SaaS | User picked B; lets us skip billing |
| LLM cost model | BYO API keys, pgsodium-encrypted | Shared keys with quotas; hybrid | User picked BYO; cleanest for beta, $0 cost to us |
| Frontend host | Vercel + Next.js App Router | All-in-one host | Vercel-native ecosystem, best Next.js DX |
| Python host | Render Web Service | Fly.io; Modal; Railway; self-host | User already operates Render; switch cost not justified by Fly's marginal wins |
| Auth + DB | Supabase | Clerk + Neon; Auth0 + Postgres on Render; NextAuth + own DB | One vendor, RLS for tenancy, pgsodium for keys |
| Run execution model | Approach 1 (direct SSE, in-process bus) | Approach 2 (Vercel proxy); Approach 3 (queue + Realtime) | Smallest viable architecture; A3 is migration path |
| MVP feature scope | A only (run, watch, history, settings) | B/C/D/E; F (kitchen sink) | Ship A; B–E become discrete future projects |
| Streaming protocol | SSE | WebSocket; long-poll | One-way is enough; native reconnect; simpler |
| Browser→Render auth | Supabase JWT, verified against JWKS | Service-role key on Render; mTLS | Stateless; defense in depth (Render can only act on behalf of the authenticated user) |
| Event log storage | jsonb column on `runs` | Separate `run_events` table | Simpler; promote to a table when we need filtering |

## 12. Open questions / explicit non-decisions

These are things we have *not* decided in this design — flagging so the implementation plan picks them up:

- **Domain name** for the hosted app (e.g., `trading.snapsonic.com` vs. a fresh domain). Default: subdomain of an existing Snapsonic-owned domain.
- **Email sender** for magic links — Supabase's default for v1, swap to Resend if delivery becomes an issue.
- **Specific Render plan** — Starter ($7/mo) is the floor; we'll right-size after first deploy.
- **Logo / branding** — placeholder for v1; not on critical path.
- **Whether to fork the upstream repo** — for v1 we treat it as a dependency. If we ever need engine changes, we fork at that moment.
