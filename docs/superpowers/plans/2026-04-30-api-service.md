# API Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI service in `apps/api/` that hosts the LangGraph engine on Render — JWT-verified user requests, BYO key fetching via the Plan 1 vault RPCs, in-process pub/sub for live SSE streaming, a worker that runs the engine, a janitor cron for stuck rows, and a Dockerized deploy. v1 ships behind a fake engine (`USE_FAKE_ENGINE=1`); real `tradingagents` wiring is **Plan 4**.

**Architecture:** Three module clusters: (a) infra primitives — `bus.py`, `auth.py`, `keys.py`; (b) execution — `engine.py` (LangChain callback → SSE adapter), `worker.py` (async run orchestrator), `janitor.py` (stuck-row sweep); (c) HTTP surface — `main.py` + `routes.py`. The browser opens an SSE connection straight to Render carrying its Supabase JWT; Render verifies it, loads the user's BYO keys via service-role, kicks off the run in a thread, and streams agent events back. The fake engine emits a canned event sequence through the same callback machinery as the real engine — so swapping in Plan 4 is a thin substitution.

**Tech Stack:** Python 3.13, `uv`, FastAPI, `sse-starlette` (or `fastapi.sse.EventSourceResponse` on FastAPI ≥0.135), PyJWT (with `PyJWKClient` for ES256/RS256, falls back to HS256), `httpx`, `structlog`, `pytest` + `pytest-asyncio` + `freezegun`, `langchain-core` (for `BaseCallbackHandler` types), Docker, Render Blueprint.

**Reference spec:** [`docs/superpowers/specs/2026-04-30-tradingagents-app-design.md`](../specs/2026-04-30-tradingagents-app-design.md)
**Reference plan:** [`docs/superpowers/plans/2026-04-30-foundation.md`](2026-04-30-foundation.md) (Plan 1 — already shipped)

---

## Working assumptions

- Engineer is on macOS or Linux. Windows users adapt paths.
- `uv` is installed (`brew install uv` or `curl -fsSL https://astral.sh/uv/install.sh | sh`).
- Docker Desktop is running.
- The repo is on branch `feature/api` (already created by the writing-plans flow).
- `.env.local` at repo root holds Supabase URL, service-role key, JWT secret, and PAT (per Plan 1's `apps/.env.example`).
- The Plan 1 schema is live both locally and on the Cloud project at `rhkxooyygufqgkpxmjvr.supabase.co`.
- Pushes happen at the end of each phase, not after every commit.

---

## File map (everything this plan creates or modifies)

```
apps/
└── api/
    ├── pyproject.toml                     # create
    ├── uv.lock                            # create
    ├── README.md                          # create
    ├── Dockerfile                         # create
    ├── .dockerignore                      # create
    ├── src/
    │   └── api/
    │       ├── __init__.py                # create
    │       ├── main.py                    # create — FastAPI app factory + /healthz
    │       ├── routes.py                  # create — POST /runs/{id}/start, GET /runs/{id}/stream
    │       ├── auth.py                    # create — JWT verify dependency
    │       ├── keys.py                    # create — vault_load_keys client
    │       ├── bus.py                     # create — in-process pub/sub
    │       ├── engine.py                  # create — LangChain callback adapter (SSEPublisher)
    │       ├── worker.py                  # create — async run orchestrator
    │       ├── janitor.py                 # create — stuck-row sweeper (cron entrypoint)
    │       ├── settings.py                # create — pydantic-settings config
    │       └── logging.py                 # create — structlog setup
    └── tests/
        ├── __init__.py                    # create
        ├── conftest.py                    # create — fixtures
        ├── fakes/
        │   ├── __init__.py                # create
        │   └── fake_engine.py             # create — FakeTradingAgentsGraph
        ├── test_bus.py                    # create
        ├── test_auth.py                   # create
        ├── test_keys.py                   # create
        ├── test_engine.py                 # create
        ├── test_worker.py                 # create
        ├── test_routes.py                 # create
        └── test_janitor.py                # create

render.yaml                                # modify — replace placeholder with real config

.github/workflows/api-ci.yml               # create — pytest in CI
```

---

## Phase 1 — Scaffold (Python tooling + hello-world FastAPI)

### Task 1: Initialize `apps/api` Python project

**Files:**
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/uv.lock`
- Create: `apps/api/README.md`
- Create: `apps/api/src/api/__init__.py`

- [ ] **Step 1: Write `apps/api/pyproject.toml`**

```toml
[project]
name = "tradingagents-api"
version = "0.1.0"
description = "FastAPI service hosting the LangGraph trading-agents engine on Render."
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sse-starlette>=2.1",
    "pyjwt[crypto]>=2.9",
    "httpx>=0.27",
    "pydantic>=2.9",
    "pydantic-settings>=2.5",
    "structlog>=24.4",
    "langchain-core>=0.3",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "freezegun>=1.5",
    "ruff>=0.7",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/api"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
```

- [ ] **Step 2: Create the package skeleton**

```bash
mkdir -p apps/api/src/api apps/api/tests/fakes
touch apps/api/src/api/__init__.py
touch apps/api/tests/__init__.py
touch apps/api/tests/fakes/__init__.py
```

- [ ] **Step 3: Lock and install**

```bash
cd apps/api
uv sync
cd ../..
```

Expected: `uv.lock` is generated, `.venv/` is created (gitignored), no errors.

- [ ] **Step 4: Write `apps/api/README.md`**

```markdown
# tradingagents-api

FastAPI service hosting the LangGraph trading-agents engine. Deploys to Render.

## Local development

```bash
cd apps/api
uv sync
uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

## Tests

```bash
cd apps/api
uv run pytest -v
```

## Architecture

See [`docs/superpowers/specs/2026-04-30-tradingagents-app-design.md`](../../docs/superpowers/specs/2026-04-30-tradingagents-app-design.md).
```

- [ ] **Step 5: Commit**

```bash
git add apps/api/pyproject.toml apps/api/uv.lock apps/api/README.md \
        apps/api/src/api/__init__.py apps/api/tests/__init__.py \
        apps/api/tests/fakes/__init__.py
git commit -m "chore(api): scaffold pyproject + uv lockfile"
```

---

### Task 2: Settings module + structlog setup

**Files:**
- Create: `apps/api/src/api/settings.py`
- Create: `apps/api/src/api/logging.py`

- [ ] **Step 1: Write `settings.py`**

```python
"""Runtime configuration via environment variables."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Supabase
    supabase_url: str = Field(..., description="https://<ref>.supabase.co")
    supabase_service_role_key: str = Field(..., description="Service role key (secret)")
    supabase_jwt_secret: str = Field("", description="HS256 secret if project uses legacy auth")

    # Engine
    use_fake_engine: bool = Field(True, description="Plan 2 ships with fake; Plan 4 flips this")

    # Janitor
    stuck_run_threshold_minutes: int = Field(30, description="Mark running rows older than this as failed")

    # Logging
    log_level: str = Field("INFO")
    log_json: bool = Field(True, description="Emit JSON logs (off in local dev for readability)")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 2: Write `logging.py`**

```python
"""Structlog-based JSON logging configured once at app start."""
import logging
import sys

import structlog

from api.settings import get_settings


def configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.log_json:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(level=level, stream=sys.stdout, format="%(message)s")


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/src/api/settings.py apps/api/src/api/logging.py
git commit -m "feat(api): add settings + structlog setup"
```

---

### Task 3: TDD — minimal `/healthz` endpoint

**Files:**
- Create: `apps/api/src/api/main.py`
- Create: `apps/api/tests/test_main.py`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_main.py`:

```python
"""Smoke tests for the FastAPI app."""
from fastapi.testclient import TestClient

from api.main import create_app


def test_healthz_returns_ok():
    client = TestClient(create_app())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run — expect failure**

```bash
cd apps/api
SUPABASE_URL=http://example.invalid \
SUPABASE_SERVICE_ROLE_KEY=test \
uv run pytest tests/test_main.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` for `api.main` (file doesn't exist yet).

- [ ] **Step 3: Write `apps/api/src/api/main.py`**

```python
"""FastAPI app factory."""
from fastapi import FastAPI

from api.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="tradingagents-api", version="0.1.0")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 4: Run — expect pass**

```bash
cd apps/api
SUPABASE_URL=http://example.invalid \
SUPABASE_SERVICE_ROLE_KEY=test \
uv run pytest tests/test_main.py -v
```

Expected: 1 test passes.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/api/main.py apps/api/tests/test_main.py
git commit -m "feat(api): minimal FastAPI app + /healthz endpoint"
```

---

### Task 4: Local dev `make` targets

**Files:**
- Modify: `Makefile` (repo root)

- [ ] **Step 1: Read existing Makefile**

```bash
cat Makefile
```

- [ ] **Step 2: Append API targets to `Makefile`**

Append to the end:

```makefile

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
```

Update the `help` target's body to include the new ones:

```makefile
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
```

- [ ] **Step 3: Verify**

```bash
make help
make api-test
```

Expected: help shows new targets; `api-test` runs the smoke test (1 pass).

- [ ] **Step 4: Commit**

```bash
git add Makefile
git commit -m "chore: add make api-* targets for FastAPI dev"
```

---

### Task 5: Verify hello-world via uvicorn

**Files:** none (verification only)

- [ ] **Step 1: Run the dev server**

In one terminal:

```bash
cd apps/api
SUPABASE_URL=http://example.invalid \
SUPABASE_SERVICE_ROLE_KEY=test \
uv run uvicorn api.main:app --port 8000
```

- [ ] **Step 2: Hit `/healthz`**

In another terminal:

```bash
curl -s http://localhost:8000/healthz
```

Expected: `{"status":"ok"}`.

- [ ] **Step 3: Stop the server**

`Ctrl-C` in the first terminal. No commit.

---

## Phase 2 — SSE Bus (in-process pub/sub with ring buffer)

### Task 6: TDD — `Bus.subscribe` + `Bus.publish` fan-out

**Files:**
- Create: `apps/api/tests/test_bus.py`
- Create: `apps/api/src/api/bus.py`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_bus.py`:

```python
"""Tests for the in-process SSE event bus."""
import asyncio

import pytest

from api.bus import Bus, BusEvent


async def test_publish_fans_out_to_all_subscribers():
    bus = Bus()
    queue_a = bus.subscribe()
    queue_b = bus.subscribe()

    bus.publish({"type": "agent_started", "agent": "market_analyst"})

    event_a = await asyncio.wait_for(queue_a.get(), timeout=0.1)
    event_b = await asyncio.wait_for(queue_b.get(), timeout=0.1)

    assert isinstance(event_a, BusEvent)
    assert event_a.id == 1
    assert event_a.data == {"type": "agent_started", "agent": "market_analyst"}
    assert event_b.id == 1
    assert event_b.data == event_a.data
```

- [ ] **Step 2: Run — expect failure**

```bash
cd apps/api && uv run pytest tests/test_bus.py -v
```

Expected: `ImportError: cannot import name 'Bus' from 'api.bus'`.

- [ ] **Step 3: Write `apps/api/src/api/bus.py`**

```python
"""In-process pub/sub bus with ring-buffered replay for SSE reconnect."""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from typing import Any

BUFFER_SIZE = 200
QUEUE_MAX_SIZE = 512
SENTINEL: Any = object()


@dataclass(frozen=True)
class BusEvent:
    id: int
    data: dict[str, Any]


class Bus:
    """In-process pub/sub bound to a single run_id.

    Producers call publish() (cheap, sync). Subscribers call subscribe() to
    get an asyncio.Queue and consume events. close() ends all subscribers.
    The last BUFFER_SIZE events are kept for Last-Event-ID replay.
    """

    def __init__(self) -> None:
        self._buffer: deque[BusEvent] = deque(maxlen=BUFFER_SIZE)
        self._subscribers: list[asyncio.Queue] = []
        self._counter: int = 0
        self._closed: bool = False

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    def publish(self, data: dict[str, Any]) -> BusEvent:
        if self._closed:
            raise RuntimeError("Bus is closed")
        self._counter += 1
        event = BusEvent(id=self._counter, data=data)
        self._buffer.append(event)
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # slow subscriber drops a message; ring buffer still has it
        return event

    def replay_since(self, last_event_id: int | None) -> list[BusEvent]:
        if last_event_id is None:
            return []
        return [e for e in self._buffer if e.id > last_event_id]

    def close(self) -> None:
        self._closed = True
        for q in list(self._subscribers):
            try:
                q.put_nowait(SENTINEL)
            except asyncio.QueueFull:
                pass

    @property
    def closed(self) -> bool:
        return self._closed
```

- [ ] **Step 4: Run — expect pass**

```bash
cd apps/api && uv run pytest tests/test_bus.py::test_publish_fans_out_to_all_subscribers -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/api/bus.py apps/api/tests/test_bus.py
git commit -m "feat(api): add in-process SSE Bus with fan-out"
```

---

### Task 7: TDD — Bus ring buffer eviction

**Files:**
- Modify: `apps/api/tests/test_bus.py`

- [ ] **Step 1: Add the test**

Append to `tests/test_bus.py`:

```python
async def test_buffer_evicts_old_events():
    from api.bus import Bus, BUFFER_SIZE

    bus = Bus()
    for i in range(BUFFER_SIZE + 50):
        bus.publish({"i": i})

    # Replay since 0 should give us the most recent BUFFER_SIZE events.
    replayed = bus.replay_since(0)
    assert len(replayed) == BUFFER_SIZE
    assert replayed[0].data["i"] == 50  # earliest 50 evicted
    assert replayed[-1].data["i"] == BUFFER_SIZE + 49
```

- [ ] **Step 2: Run — expect pass** (the deque(maxlen=...) handles this for free)

```bash
cd apps/api && uv run pytest tests/test_bus.py::test_buffer_evicts_old_events -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/test_bus.py
git commit -m "test(api): assert Bus ring buffer evicts old events"
```

---

### Task 8: TDD — Last-Event-ID replay

**Files:**
- Modify: `apps/api/tests/test_bus.py`

- [ ] **Step 1: Add the test**

Append to `tests/test_bus.py`:

```python
async def test_replay_since_returns_only_newer_events():
    bus = Bus()
    bus.publish({"i": 1})
    bus.publish({"i": 2})
    bus.publish({"i": 3})

    replayed = bus.replay_since(last_event_id=1)
    assert [e.id for e in replayed] == [2, 3]
    assert [e.data["i"] for e in replayed] == [2, 3]
```

- [ ] **Step 2: Run — expect pass**

```bash
cd apps/api && uv run pytest tests/test_bus.py::test_replay_since_returns_only_newer_events -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/test_bus.py
git commit -m "test(api): assert Bus.replay_since honors Last-Event-ID"
```

---

### Task 9: TDD — close() ends all subscribers

**Files:**
- Modify: `apps/api/tests/test_bus.py`

- [ ] **Step 1: Add the test**

Append:

```python
async def test_close_pushes_sentinel_to_all_subscribers():
    from api.bus import Bus, SENTINEL

    bus = Bus()
    queue_a = bus.subscribe()
    queue_b = bus.subscribe()

    bus.close()

    assert (await asyncio.wait_for(queue_a.get(), timeout=0.1)) is SENTINEL
    assert (await asyncio.wait_for(queue_b.get(), timeout=0.1)) is SENTINEL
    assert bus.closed is True

    with pytest.raises(RuntimeError, match="closed"):
        bus.publish({"too": "late"})
```

- [ ] **Step 2: Run — expect pass**

```bash
cd apps/api && uv run pytest tests/test_bus.py::test_close_pushes_sentinel_to_all_subscribers -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/test_bus.py
git commit -m "test(api): assert Bus.close ends all subscribers"
```

---

### Task 10: Bus registry — keyed lookup by run_id

**Files:**
- Modify: `apps/api/src/api/bus.py`
- Modify: `apps/api/tests/test_bus.py`

- [ ] **Step 1: Add a registry test**

Append to `tests/test_bus.py`:

```python
async def test_bus_registry_returns_same_instance_per_run_id():
    from api.bus import BusRegistry

    registry = BusRegistry()
    bus1 = registry.get_or_create("run-abc")
    bus2 = registry.get_or_create("run-abc")
    bus3 = registry.get_or_create("run-xyz")

    assert bus1 is bus2
    assert bus1 is not bus3


async def test_bus_registry_drops_closed_buses():
    from api.bus import BusRegistry

    registry = BusRegistry()
    bus = registry.get_or_create("run-abc")
    bus.close()
    registry.drop("run-abc")
    new_bus = registry.get_or_create("run-abc")
    assert new_bus is not bus
```

- [ ] **Step 2: Run — expect failure**

```bash
cd apps/api && uv run pytest tests/test_bus.py::test_bus_registry_returns_same_instance_per_run_id -v
```

Expected: FAIL — `BusRegistry` doesn't exist.

- [ ] **Step 3: Append to `apps/api/src/api/bus.py`**

```python


class BusRegistry:
    """Process-wide registry of Bus instances keyed by run_id."""

    def __init__(self) -> None:
        self._buses: dict[str, Bus] = {}

    def get_or_create(self, run_id: str) -> Bus:
        if run_id not in self._buses:
            self._buses[run_id] = Bus()
        return self._buses[run_id]

    def get(self, run_id: str) -> Bus | None:
        return self._buses.get(run_id)

    def drop(self, run_id: str) -> None:
        self._buses.pop(run_id, None)


# Process-wide singleton — wired into the FastAPI app at startup.
registry = BusRegistry()
```

- [ ] **Step 4: Run — expect pass**

```bash
cd apps/api && uv run pytest tests/test_bus.py -v
```

Expected: 5 tests pass (4 from earlier + 2 new).

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/api/bus.py apps/api/tests/test_bus.py
git commit -m "feat(api): add BusRegistry for run_id-keyed lookup"
```

---

## Phase 3 — JWT verification

### Task 11: TDD — JWT decode helper (HS256 path first; ES256/RS256 in Task 14)

**Files:**
- Create: `apps/api/tests/test_auth.py`
- Create: `apps/api/src/api/auth.py`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_auth.py`:

```python
"""Tests for JWT verification."""
import time
from uuid import UUID

import jwt
import pytest
from fastapi import HTTPException

from api.auth import decode_user_token


HS256_SECRET = "test-secret-do-not-use-in-prod"
SUB_UUID = "11111111-2222-3333-4444-555555555555"


def make_token(*, sub: str = SUB_UUID, exp_offset: int = 3600,
               aud: str = "authenticated", role: str = "authenticated") -> str:
    payload = {
        "sub": sub,
        "aud": aud,
        "role": role,
        "exp": int(time.time()) + exp_offset,
        "iss": "https://test.supabase.co/auth/v1",
    }
    return jwt.encode(payload, HS256_SECRET, algorithm="HS256")


def test_valid_hs256_token_returns_user_id():
    token = make_token()
    user_id = decode_user_token(token, hs256_secret=HS256_SECRET)
    assert user_id == UUID(SUB_UUID)


def test_expired_token_raises_401():
    token = make_token(exp_offset=-60)
    with pytest.raises(HTTPException) as exc:
        decode_user_token(token, hs256_secret=HS256_SECRET)
    assert exc.value.status_code == 401


def test_wrong_audience_raises_401():
    token = make_token(aud="anon")
    with pytest.raises(HTTPException) as exc:
        decode_user_token(token, hs256_secret=HS256_SECRET)
    assert exc.value.status_code == 401


def test_malformed_token_raises_401():
    with pytest.raises(HTTPException) as exc:
        decode_user_token("not.a.real.jwt", hs256_secret=HS256_SECRET)
    assert exc.value.status_code == 401
```

- [ ] **Step 2: Run — expect failure**

```bash
cd apps/api && uv run pytest tests/test_auth.py -v
```

Expected: `ImportError: cannot import name 'decode_user_token'`.

- [ ] **Step 3: Write `apps/api/src/api/auth.py`**

```python
"""JWT verification for Supabase user tokens.

Supports both legacy HS256 and modern ES256/RS256 JWKS-based projects.
The `decode_user_token` callable picks the right path based on the JWT's
header `alg` field. Project Settings -> API -> JWT Settings tells you which
your project uses.
"""
from __future__ import annotations

import jwt
from fastapi import HTTPException, status
from jwt import PyJWKClient
from uuid import UUID

from api.settings import get_settings

# Module-level JWKS client; lazy-initialized on first use.
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        settings = get_settings()
        _jwks_client = PyJWKClient(
            f"{settings.supabase_url}/auth/v1/.well-known/jwks.json",
            cache_jwk_set=True,
            lifespan=3600,
            cache_keys=True,
        )
    return _jwks_client


def decode_user_token(token: str, *, hs256_secret: str | None = None) -> UUID:
    """Verify a Supabase user JWT and return the user UUID.

    Picks HS256 vs ES256/RS256 based on the JWT's header. For HS256 the
    secret is required (passed in for testability). For asymmetric algos
    we fetch the signing key from Supabase's JWKS endpoint.
    """
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "")

        if alg == "HS256":
            if hs256_secret is None:
                hs256_secret = get_settings().supabase_jwt_secret
            if not hs256_secret:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="HS256 secret not configured",
                )
            payload = jwt.decode(
                token, hs256_secret, algorithms=["HS256"],
                audience="authenticated",
            )
        elif alg in ("ES256", "RS256"):
            signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token, signing_key.key, algorithms=[alg],
                audience="authenticated",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Unsupported JWT alg: {alg}",
            )

        sub = payload.get("sub")
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing sub claim",
            )
        return UUID(sub)
    except HTTPException:
        raise
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        ) from exc
```

- [ ] **Step 4: Run — expect pass**

```bash
cd apps/api && uv run pytest tests/test_auth.py -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/api/auth.py apps/api/tests/test_auth.py
git commit -m "feat(api): add HS256 JWT verification (decode_user_token)"
```

---

### Task 12: FastAPI dependency wrapping the decoder

**Files:**
- Modify: `apps/api/src/api/auth.py`
- Modify: `apps/api/tests/test_auth.py`

- [ ] **Step 1: Add a test for the dependency**

Append to `tests/test_auth.py`:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.auth import current_user_id


def _build_app(secret: str):
    app = FastAPI()

    @app.get("/whoami")
    async def whoami(user_id=current_user_id_dep(secret)):
        return {"user_id": str(user_id)}

    return app


def current_user_id_dep(secret):
    # Inline override so tests don't pull from settings.
    from fastapi import Header

    def _dep(authorization: str = Header(...)):
        if not authorization.startswith("Bearer "):
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Missing bearer")
        token = authorization.removeprefix("Bearer ")
        return decode_user_token(token, hs256_secret=secret)

    return _dep


def test_whoami_with_valid_token():
    client = TestClient(_build_app(HS256_SECRET))
    token = make_token()
    r = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"user_id": SUB_UUID}


def test_whoami_without_authorization_returns_401():
    client = TestClient(_build_app(HS256_SECRET))
    r = client.get("/whoami")
    assert r.status_code == 401
```

- [ ] **Step 2: Run — expect failure**

```bash
cd apps/api && uv run pytest tests/test_auth.py::test_whoami_with_valid_token -v
```

Expected: `ImportError: cannot import name 'current_user_id'`.

- [ ] **Step 3: Append to `apps/api/src/api/auth.py`**

```python


from fastapi import Header
from typing import Annotated


def current_user_id(
    authorization: Annotated[str, Header()],
) -> UUID:
    """FastAPI dependency: returns the user UUID for the bearer token."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    token = authorization.removeprefix("Bearer ")
    return decode_user_token(token)
```

- [ ] **Step 4: Run — expect pass**

```bash
cd apps/api && uv run pytest tests/test_auth.py -v
```

Expected: 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/api/auth.py apps/api/tests/test_auth.py
git commit -m "feat(api): add current_user_id FastAPI dependency"
```

---

## Phase 4 — Vault key fetcher (calls Plan 1's vault_load_keys RPC)

### Task 13: TDD — vault_load_keys client over httpx

**Files:**
- Create: `apps/api/tests/test_keys.py`
- Create: `apps/api/src/api/keys.py`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_keys.py`:

```python
"""Tests for the vault_load_keys client."""
import logging
from uuid import UUID

import httpx
import pytest

from api.keys import KeyVaultError, load_keys


USER_ID = UUID("11111111-2222-3333-4444-555555555555")


def make_mock_transport(*, status_code: int, payload):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)
    return httpx.MockTransport(handler)


async def test_load_keys_returns_decrypted_plaintext():
    transport = make_mock_transport(
        status_code=200,
        payload=[
            {"provider": "openai", "plaintext": "sk-test-openai"},
            {"provider": "anthropic", "plaintext": "sk-test-anthropic"},
        ],
    )
    keys = await load_keys(
        user_id=USER_ID,
        providers=["openai", "anthropic"],
        supabase_url="http://test.local",
        service_role_key="service-role-token",
        transport=transport,
    )
    assert keys == {"openai": "sk-test-openai", "anthropic": "sk-test-anthropic"}


async def test_load_keys_raises_on_missing_provider():
    transport = make_mock_transport(
        status_code=200,
        payload=[{"provider": "openai", "plaintext": "sk-test-openai"}],
    )
    with pytest.raises(KeyVaultError, match="anthropic"):
        await load_keys(
            user_id=USER_ID,
            providers=["openai", "anthropic"],
            supabase_url="http://test.local",
            service_role_key="service-role-token",
            transport=transport,
        )


async def test_load_keys_does_not_log_plaintext(caplog):
    transport = make_mock_transport(
        status_code=200,
        payload=[{"provider": "openai", "plaintext": "sk-secret-do-not-leak"}],
    )
    caplog.set_level(logging.DEBUG)
    await load_keys(
        user_id=USER_ID,
        providers=["openai"],
        supabase_url="http://test.local",
        service_role_key="service-role-token",
        transport=transport,
    )
    log_text = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "sk-secret-do-not-leak" not in log_text


async def test_load_keys_raises_on_5xx():
    transport = make_mock_transport(status_code=500, payload={"error": "boom"})
    with pytest.raises(KeyVaultError, match="500"):
        await load_keys(
            user_id=USER_ID,
            providers=["openai"],
            supabase_url="http://test.local",
            service_role_key="service-role-token",
            transport=transport,
        )
```

- [ ] **Step 2: Run — expect failure**

```bash
cd apps/api && uv run pytest tests/test_keys.py -v
```

Expected: ImportError.

- [ ] **Step 3: Write `apps/api/src/api/keys.py`**

```python
"""Client for the Plan 1 `vault_load_keys` RPC.

Fetches BYO API keys for a specific (user, providers) pair via Supabase's
PostgREST RPC endpoint, using the service-role key. Plaintext lives only
in the returned dict and never enters logs.
"""
from __future__ import annotations

from uuid import UUID

import httpx

from api.logging import get_logger

logger = get_logger(__name__)


class KeyVaultError(RuntimeError):
    """Raised when key vault access fails or required keys are missing."""


async def load_keys(
    *,
    user_id: UUID,
    providers: list[str],
    supabase_url: str,
    service_role_key: str,
    transport: httpx.AsyncBaseTransport | None = None,
    timeout: float = 5.0,
) -> dict[str, str]:
    """Fetch and decrypt the user's BYO keys for the given providers.

    Returns a dict {provider: plaintext}. Raises KeyVaultError if any
    requested provider has no stored key or the RPC errors.
    """
    url = f"{supabase_url.rstrip('/')}/rest/v1/rpc/vault_load_keys"
    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
    }
    payload = {"p_user_id": str(user_id), "p_providers": providers}

    async with httpx.AsyncClient(transport=transport, timeout=timeout) as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        logger.error(
            "vault_load_keys failed",
            status_code=response.status_code,
            user_id=str(user_id),
        )
        raise KeyVaultError(f"vault_load_keys returned {response.status_code}")

    rows = response.json()
    keys: dict[str, str] = {row["provider"]: row["plaintext"] for row in rows}

    missing = set(providers) - keys.keys()
    if missing:
        logger.warning(
            "vault_load_keys missing providers",
            user_id=str(user_id),
            missing_providers=sorted(missing),
        )
        raise KeyVaultError(
            f"No API key configured for: {', '.join(sorted(missing))}. "
            "Add one in Settings."
        )

    logger.info(
        "vault_load_keys ok",
        user_id=str(user_id),
        providers=sorted(keys.keys()),
    )
    return keys
```

- [ ] **Step 4: Run — expect pass**

```bash
cd apps/api && uv run pytest tests/test_keys.py -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/api/keys.py apps/api/tests/test_keys.py
git commit -m "feat(api): add vault_load_keys client + missing-provider guard"
```

---

## Phase 5 — Fake engine

### Task 14: TDD — `FakeTradingAgentsGraph` emits canned events

**Files:**
- Create: `apps/api/tests/fakes/fake_engine.py`
- Modify: `apps/api/tests/test_engine.py` (created in Task 15)

- [ ] **Step 1: Write the fake engine**

Create `apps/api/tests/fakes/fake_engine.py`:

```python
"""FakeTradingAgentsGraph — emits a canned sequence of LangChain callback
events through the real BaseCallbackHandler interface, so tests exercise the
same SSE adapter we'll use in production with the real engine."""
from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from langchain_core.callbacks import BaseCallbackHandler


CANNED_AGENTS = [
    "market_analyst",
    "social_analyst",
    "news_analyst",
    "fundamentals_analyst",
    "research_manager",
    "trader",
    "portfolio_manager",
]


class FakeTradingAgentsGraph:
    """Mimics tradingagents.graph.trading_graph.TradingAgentsGraph just
    enough for tests. propagate(ticker, date) iterates through CANNED_AGENTS,
    firing on_chain_start / on_chat_model_start / on_chain_end on every
    callback in self.callbacks. Returns (final_state, decision)."""

    def __init__(
        self,
        *,
        debug: bool = False,
        config: dict[str, Any] | None = None,
        callbacks: list[BaseCallbackHandler] | None = None,
        per_agent_delay_s: float = 0.0,
        raise_at: str | None = None,
    ):
        self.debug = debug
        self.config = config or {}
        self.callbacks = callbacks or []
        self.per_agent_delay_s = per_agent_delay_s
        self.raise_at = raise_at  # name of an agent to throw at

    def propagate(self, ticker: str, trade_date: str) -> tuple[dict[str, Any], str]:
        final_state: dict[str, Any] = {"ticker": ticker, "trade_date": trade_date}
        for agent in CANNED_AGENTS:
            if self.raise_at == agent:
                raise RuntimeError(f"fake engine forced failure at {agent}")
            run_id = uuid4()
            for cb in self.callbacks:
                cb.on_chain_start(
                    serialized={"name": agent},
                    inputs={"ticker": ticker},
                    run_id=run_id,
                    name=agent,
                )
                cb.on_chat_model_start(
                    serialized={"name": agent},
                    messages=[],
                    run_id=run_id,
                )
            if self.per_agent_delay_s:
                time.sleep(self.per_agent_delay_s)
            final_state[f"{agent}_report"] = f"<{agent} canned report for {ticker}>"
            for cb in self.callbacks:
                cb.on_chain_end(
                    outputs={f"{agent}_report": final_state[f"{agent}_report"]},
                    run_id=run_id,
                    name=agent,
                )
        decision = "BUY"
        final_state["final_trade_decision"] = decision
        return final_state, decision
```

- [ ] **Step 2: Verify it imports**

```bash
cd apps/api && uv run python -c "from tests.fakes.fake_engine import FakeTradingAgentsGraph; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/fakes/fake_engine.py
git commit -m "test(api): add FakeTradingAgentsGraph for engine adapter tests"
```

---

## Phase 6 — Engine adapter (LangChain callback → SSE events)

### Task 15: TDD — `SSEPublisher.on_chain_start` emits `agent_started`

**Files:**
- Create: `apps/api/tests/test_engine.py`
- Create: `apps/api/src/api/engine.py`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_engine.py`:

```python
"""Tests for the LangChain callback adapter that publishes SSE events."""
from uuid import uuid4

from api.bus import Bus
from api.engine import SSEPublisher


def test_on_chain_start_publishes_agent_started():
    bus = Bus()
    publisher = SSEPublisher(bus=bus, run_id="run-1", verbose=False)

    publisher.on_chain_start(
        serialized={"name": "market_analyst"},
        inputs={},
        run_id=uuid4(),
        name="market_analyst",
    )

    # One event in the buffer.
    events = bus.replay_since(0)
    assert len(events) == 1
    assert events[0].data["type"] == "agent_started"
    assert events[0].data["agent"] == "market_analyst"


def test_on_chain_end_publishes_agent_completed_with_summary():
    bus = Bus()
    publisher = SSEPublisher(bus=bus, run_id="run-1", verbose=False)

    publisher.on_chain_end(
        outputs={"market_analyst_report": "Long report. " * 50},
        run_id=uuid4(),
        name="market_analyst",
    )

    events = bus.replay_since(0)
    assert len(events) == 1
    e = events[0].data
    assert e["type"] == "agent_completed"
    assert e["agent"] == "market_analyst"
    assert "summary" in e
    assert len(e["summary"]) <= 500  # adapter truncates


def test_on_chat_model_start_emits_agent_thinking_keepalive():
    bus = Bus()
    publisher = SSEPublisher(bus=bus, run_id="run-1", verbose=False)
    publisher.on_chat_model_start(
        serialized={}, messages=[], run_id=uuid4(), name="trader",
    )
    events = bus.replay_since(0)
    assert len(events) == 1
    assert events[0].data["type"] == "agent_thinking"
    assert events[0].data["agent"] == "trader"


def test_tool_events_only_in_verbose_mode():
    bus_quiet = Bus()
    SSEPublisher(bus=bus_quiet, run_id="r", verbose=False).on_tool_start(
        serialized={"name": "get_stock_data"}, input_str="NVDA", run_id=uuid4(),
    )
    assert bus_quiet.replay_since(0) == []  # nothing emitted

    bus_verbose = Bus()
    SSEPublisher(bus=bus_verbose, run_id="r", verbose=True).on_tool_start(
        serialized={"name": "get_stock_data"}, input_str="NVDA", run_id=uuid4(),
    )
    events = bus_verbose.replay_since(0)
    assert len(events) == 1
    assert events[0].data["type"] == "tool_called"
    assert events[0].data["tool"] == "get_stock_data"
```

- [ ] **Step 2: Run — expect failure**

```bash
cd apps/api && uv run pytest tests/test_engine.py -v
```

Expected: ImportError.

- [ ] **Step 3: Write `apps/api/src/api/engine.py`**

```python
"""LangChain BaseCallbackHandler that publishes SSE-shaped events to a Bus.

Wraps the upstream tradingagents engine without modifying it. Each LangGraph
node lifecycle event becomes a typed SSE event on a per-run_id Bus.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from api.bus import Bus

SUMMARY_LIMIT = 500


def _truncate(text: str, limit: int = SUMMARY_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _agent_name(name: str | None, serialized: dict[str, Any] | None) -> str:
    return name or (serialized or {}).get("name") or "unknown"


class SSEPublisher(BaseCallbackHandler):
    """Maps LangChain/LangGraph callback events to bus.publish() calls.

    `verbose=True` enables tool-level events; default emits only
    `agent_started`, `agent_thinking`, and `agent_completed`.
    """

    def __init__(self, *, bus: Bus, run_id: str, verbose: bool = False) -> None:
        super().__init__()
        self.bus = bus
        self.run_id = run_id
        self.verbose = verbose

    # --- node lifecycle --------------------------------------------------

    def on_chain_start(self, serialized, inputs, *, run_id: UUID, name: str | None = None, **kwargs) -> None:
        agent = _agent_name(name, serialized)
        self.bus.publish({"type": "agent_started", "agent": agent})

    def on_chain_end(self, outputs, *, run_id: UUID, name: str | None = None, **kwargs) -> None:
        agent = _agent_name(name, None)
        # Pull the report text out of outputs if present
        summary_text = ""
        if isinstance(outputs, dict):
            for key, value in outputs.items():
                if isinstance(value, str) and key.endswith("_report"):
                    summary_text = value
                    break
            if not summary_text:
                # fallback — stringify outputs
                summary_text = str(outputs)
        self.bus.publish({
            "type": "agent_completed",
            "agent": agent,
            "summary": _truncate(summary_text),
        })

    def on_chain_error(self, error, *, run_id: UUID, name: str | None = None, **kwargs) -> None:
        agent = _agent_name(name, None)
        self.bus.publish({
            "type": "agent_error",
            "agent": agent,
            "error": _truncate(str(error)),
        })

    # --- LLM-level (heartbeat) ------------------------------------------

    def on_chat_model_start(self, serialized, messages, *, run_id: UUID, name: str | None = None, **kwargs) -> None:
        agent = _agent_name(name, serialized)
        self.bus.publish({"type": "agent_thinking", "agent": agent})

    # --- tool events (verbose only) -------------------------------------

    def on_tool_start(self, serialized, input_str, *, run_id: UUID, **kwargs) -> None:
        if not self.verbose:
            return
        tool = (serialized or {}).get("name", "unknown")
        self.bus.publish({"type": "tool_called", "tool": tool, "args": _truncate(str(input_str), 200)})

    def on_tool_end(self, output, *, run_id: UUID, **kwargs) -> None:
        if not self.verbose:
            return
        self.bus.publish({"type": "tool_result", "result": _truncate(str(output), 200)})
```

- [ ] **Step 4: Run — expect pass**

```bash
cd apps/api && uv run pytest tests/test_engine.py -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/api/engine.py apps/api/tests/test_engine.py
git commit -m "feat(api): add SSEPublisher (LangChain callback → Bus events)"
```

---

### Task 16: TDD — fake engine end-to-end through the publisher

**Files:**
- Modify: `apps/api/tests/test_engine.py`

- [ ] **Step 1: Add the integration test**

Append:

```python
def test_fake_engine_emits_full_event_sequence():
    from tests.fakes.fake_engine import CANNED_AGENTS, FakeTradingAgentsGraph

    bus = Bus()
    publisher = SSEPublisher(bus=bus, run_id="r", verbose=False)
    fake = FakeTradingAgentsGraph(callbacks=[publisher])

    final_state, decision = fake.propagate("NVDA", "2026-01-15")

    types = [e.data["type"] for e in bus.replay_since(0)]
    # Each agent fires: started → thinking → completed (3 events × N agents)
    assert types.count("agent_started") == len(CANNED_AGENTS)
    assert types.count("agent_thinking") == len(CANNED_AGENTS)
    assert types.count("agent_completed") == len(CANNED_AGENTS)
    assert decision == "BUY"
```

- [ ] **Step 2: Run — expect pass**

```bash
cd apps/api && uv run pytest tests/test_engine.py::test_fake_engine_emits_full_event_sequence -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/test_engine.py
git commit -m "test(api): assert fake engine fires full SSE event sequence"
```

---

## Phase 7 — Worker (async run orchestrator)

### Task 17: TDD — `run_engine` happy path

**Files:**
- Create: `apps/api/tests/test_worker.py`
- Create: `apps/api/src/api/worker.py`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_worker.py`:

```python
"""Tests for the async worker that runs an engine instance and feeds the bus."""
import asyncio

import pytest

from api.bus import Bus, SENTINEL
from api.engine import SSEPublisher
from api.worker import run_engine
from tests.fakes.fake_engine import FakeTradingAgentsGraph


async def test_run_engine_completes_and_closes_bus():
    bus = Bus()
    publisher = SSEPublisher(bus=bus, run_id="r-happy", verbose=False)

    def make_engine() -> FakeTradingAgentsGraph:
        return FakeTradingAgentsGraph(callbacks=[publisher])

    queue = bus.subscribe()
    final_state, decision = await run_engine(
        make_engine=make_engine,
        ticker="NVDA",
        trade_date="2026-01-15",
        bus=bus,
    )

    assert decision == "BUY"
    assert final_state["ticker"] == "NVDA"

    # Drain the queue until SENTINEL
    seen_types = []
    while True:
        event = await asyncio.wait_for(queue.get(), timeout=0.5)
        if event is SENTINEL:
            break
        seen_types.append(event.data["type"])
    assert "run_completed" in seen_types
    assert bus.closed
```

- [ ] **Step 2: Run — expect failure**

```bash
cd apps/api && uv run pytest tests/test_worker.py::test_run_engine_completes_and_closes_bus -v
```

Expected: ImportError.

- [ ] **Step 3: Write `apps/api/src/api/worker.py`**

```python
"""Async worker that drives the (sync) LangGraph engine on a thread and
feeds events to a Bus. On completion, publishes a `run_completed` event
and closes the bus."""
from __future__ import annotations

import asyncio
from typing import Any, Callable

from api.bus import Bus
from api.logging import get_logger

logger = get_logger(__name__)


async def run_engine(
    *,
    make_engine: Callable[[], Any],
    ticker: str,
    trade_date: str,
    bus: Bus,
) -> tuple[dict[str, Any], str]:
    """Spawn the engine on a thread; publish `run_completed` and close bus
    when it finishes successfully. Errors propagate (caller decides how to
    write status='failed' in Supabase)."""
    loop = asyncio.get_running_loop()

    def _publish(event: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(bus.publish, event)

    def _run_sync() -> tuple[dict[str, Any], str]:
        engine = make_engine()
        return engine.propagate(ticker, trade_date)

    try:
        final_state, decision = await asyncio.to_thread(_run_sync)
    except Exception as exc:
        logger.exception("engine run failed", ticker=ticker, trade_date=trade_date)
        # Publish error then close bus
        _publish({"type": "run_failed", "error": str(exc)[:1000]})
        bus.close()
        raise

    bus.publish({"type": "run_completed", "decision": decision})
    bus.close()
    return final_state, decision
```

- [ ] **Step 4: Run — expect pass**

```bash
cd apps/api && uv run pytest tests/test_worker.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/api/worker.py apps/api/tests/test_worker.py
git commit -m "feat(api): add run_engine worker (thread-pinned propagate)"
```

---

### Task 18: TDD — exception path closes bus and re-raises

**Files:**
- Modify: `apps/api/tests/test_worker.py`

- [ ] **Step 1: Add the test**

Append:

```python
async def test_run_engine_failure_closes_bus_and_publishes_error():
    bus = Bus()
    publisher = SSEPublisher(bus=bus, run_id="r-fail", verbose=False)

    def make_engine() -> FakeTradingAgentsGraph:
        return FakeTradingAgentsGraph(callbacks=[publisher], raise_at="trader")

    queue = bus.subscribe()
    with pytest.raises(RuntimeError, match="trader"):
        await run_engine(
            make_engine=make_engine,
            ticker="NVDA",
            trade_date="2026-01-15",
            bus=bus,
        )

    seen_types = []
    while True:
        event = await asyncio.wait_for(queue.get(), timeout=0.5)
        if event is SENTINEL:
            break
        seen_types.append(event.data["type"])
    assert "run_failed" in seen_types
    assert bus.closed
```

- [ ] **Step 2: Run — expect pass**

```bash
cd apps/api && uv run pytest tests/test_worker.py::test_run_engine_failure_closes_bus_and_publishes_error -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/test_worker.py
git commit -m "test(api): assert worker closes bus + emits run_failed on error"
```

---

## Phase 8 — Supabase REST helper for `runs` writes

### Task 19: TDD — write `runs` row updates from FastAPI

**Files:**
- Create: `apps/api/src/api/supabase_runs.py`
- Create: `apps/api/tests/test_supabase_runs.py`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_supabase_runs.py`:

```python
"""Tests for the runs-table service-role REST client."""
import json
from uuid import UUID

import httpx

from api.supabase_runs import (
    fetch_run, mark_run_started, finalize_run, fail_run,
)


RUN_ID = UUID("00000000-0000-0000-0000-000000000aaa")
USER_ID = UUID("11111111-2222-3333-4444-555555555555")


def make_transport(*, status: int, payload):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload)
    return httpx.MockTransport(handler)


async def test_fetch_run_returns_dict():
    transport = make_transport(
        status=200,
        payload=[{
            "id": str(RUN_ID), "user_id": str(USER_ID),
            "ticker": "NVDA", "trade_date": "2026-01-15",
            "status": "pending",
            "config": {"llm_provider": "openai"},
            "events": [],
        }],
    )
    run = await fetch_run(
        run_id=RUN_ID, supabase_url="http://test.local",
        service_role_key="srv", transport=transport,
    )
    assert run["ticker"] == "NVDA"
    assert run["status"] == "pending"


async def test_mark_run_started_patches_status():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    await mark_run_started(
        run_id=RUN_ID, supabase_url="http://test.local",
        service_role_key="srv", transport=transport,
    )
    assert captured["body"]["status"] == "running"
    assert "started_at" in captured["body"]
```

- [ ] **Step 2: Run — expect failure**

```bash
cd apps/api && uv run pytest tests/test_supabase_runs.py -v
```

Expected: ImportError.

- [ ] **Step 3: Write `apps/api/src/api/supabase_runs.py`**

```python
"""Service-role REST helpers for the `runs` table.

Used by the worker to: load the run row, transition status, persist final
state. All calls bypass RLS (service_role)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from api.logging import get_logger

logger = get_logger(__name__)


def _headers(key: str) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


async def fetch_run(
    *, run_id: UUID, supabase_url: str, service_role_key: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    url = f"{supabase_url.rstrip('/')}/rest/v1/runs"
    async with httpx.AsyncClient(transport=transport, timeout=5.0) as client:
        r = await client.get(
            url,
            headers=_headers(service_role_key),
            params={"id": f"eq.{run_id}", "select": "*"},
        )
    if r.status_code != 200:
        raise RuntimeError(f"fetch_run {r.status_code}")
    rows = r.json()
    if not rows:
        raise RuntimeError(f"run {run_id} not found")
    return rows[0]


async def _patch_run(
    *, run_id: UUID, body: dict[str, Any],
    supabase_url: str, service_role_key: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> None:
    url = f"{supabase_url.rstrip('/')}/rest/v1/runs"
    async with httpx.AsyncClient(transport=transport, timeout=5.0) as client:
        r = await client.patch(
            url,
            headers=_headers(service_role_key),
            params={"id": f"eq.{run_id}"},
            content=json.dumps(body, default=str),
        )
    if r.status_code not in (200, 204):
        raise RuntimeError(f"patch_run {r.status_code}: {r.text[:200]}")


async def mark_run_started(
    *, run_id: UUID, supabase_url: str, service_role_key: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> None:
    await _patch_run(
        run_id=run_id,
        body={
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
        },
        supabase_url=supabase_url,
        service_role_key=service_role_key,
        transport=transport,
    )


async def finalize_run(
    *, run_id: UUID, decision: str, events: list[dict[str, Any]],
    final_state_keys: list[str],
    supabase_url: str, service_role_key: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> None:
    await _patch_run(
        run_id=run_id,
        body={
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "final_decision": {"decision": decision, "state_keys": final_state_keys},
            "events": events,
        },
        supabase_url=supabase_url,
        service_role_key=service_role_key,
        transport=transport,
    )


async def fail_run(
    *, run_id: UUID, error: str, events: list[dict[str, Any]],
    supabase_url: str, service_role_key: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> None:
    await _patch_run(
        run_id=run_id,
        body={
            "status": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error": error[:1000],
            "events": events,
        },
        supabase_url=supabase_url,
        service_role_key=service_role_key,
        transport=transport,
    )
```

- [ ] **Step 4: Run — expect pass**

```bash
cd apps/api && uv run pytest tests/test_supabase_runs.py -v
```

Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/api/supabase_runs.py apps/api/tests/test_supabase_runs.py
git commit -m "feat(api): add service-role REST client for runs table"
```

---

## Phase 9 — Routes (POST /runs/{id}/start, GET /runs/{id}/stream)

### Task 20: TDD — `POST /runs/{id}/start` happy path with fake engine

**Files:**
- Create: `apps/api/tests/conftest.py`
- Create: `apps/api/tests/test_routes.py`
- Create: `apps/api/src/api/routes.py`
- Modify: `apps/api/src/api/main.py`

- [ ] **Step 1: Write `apps/api/tests/conftest.py`**

```python
"""Shared fixtures for FastAPI integration tests."""
import time

import jwt
import pytest


HS256_SECRET = "test-secret-do-not-use-in-prod"
DEFAULT_USER_ID = "11111111-2222-3333-4444-555555555555"


def make_test_token(*, sub: str = DEFAULT_USER_ID, exp_offset: int = 3600) -> str:
    return jwt.encode(
        {
            "sub": sub,
            "aud": "authenticated",
            "role": "authenticated",
            "exp": int(time.time()) + exp_offset,
            "iss": "https://test.supabase.co/auth/v1",
        },
        HS256_SECRET,
        algorithm="HS256",
    )


@pytest.fixture
def hs256_secret() -> str:
    return HS256_SECRET


@pytest.fixture
def test_user_id() -> str:
    return DEFAULT_USER_ID


@pytest.fixture
def auth_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {make_test_token()}"}
```

- [ ] **Step 2: Write the failing test**

Create `apps/api/tests/test_routes.py`:

```python
"""Integration tests for the runs endpoints."""
import asyncio
from unittest.mock import patch
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from api.main import create_app


RUN_ID = "00000000-0000-0000-0000-000000000aaa"
USER_ID = "11111111-2222-3333-4444-555555555555"


@pytest.fixture
def app(monkeypatch, hs256_secret):
    monkeypatch.setenv("SUPABASE_URL", "http://test.local")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "srv-key")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", hs256_secret)
    monkeypatch.setenv("USE_FAKE_ENGINE", "1")
    from api.settings import get_settings
    get_settings.cache_clear()
    return create_app()


def test_start_run_requires_authorization(app):
    client = TestClient(app)
    r = client.post(f"/runs/{RUN_ID}/start")
    assert r.status_code == 401


def test_start_run_returns_202_with_fake_engine(app, auth_header):
    client = TestClient(app)

    # Patch the run row fetch + key fetch + supabase_runs writes.
    fake_run = {
        "id": RUN_ID, "user_id": USER_ID,
        "ticker": "NVDA", "trade_date": "2026-01-15", "status": "pending",
        "config": {"llm_provider": "openai"},
        "events": [],
    }
    with patch("api.routes.fetch_run", return_value=fake_run), \
         patch("api.routes.load_keys", return_value={"openai": "sk-test"}), \
         patch("api.routes.mark_run_started", return_value=None), \
         patch("api.routes.finalize_run", return_value=None):
        r = client.post(f"/runs/{RUN_ID}/start", headers=auth_header)

    assert r.status_code == 202
    assert r.json() == {"run_id": RUN_ID, "status": "started"}
```

- [ ] **Step 3: Run — expect failure**

```bash
cd apps/api && uv run pytest tests/test_routes.py -v
```

Expected: ImportError on `api.routes`.

- [ ] **Step 4: Write `apps/api/src/api/routes.py`**

```python
"""FastAPI routes for runs."""
from __future__ import annotations

import asyncio
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sse_starlette.sse import EventSourceResponse

from api.auth import current_user_id
from api.bus import registry
from api.engine import SSEPublisher
from api.keys import KeyVaultError, load_keys
from api.logging import get_logger
from api.settings import get_settings
from api.supabase_runs import (
    fail_run, fetch_run, finalize_run, mark_run_started,
)
from api.worker import run_engine

router = APIRouter()
logger = get_logger(__name__)


def _make_engine_factory(*, callbacks, fake: bool, env: dict[str, str]):
    """Returns a callable that constructs an engine instance with our
    callback wired in. Plan 4 swaps the fake for the real one."""
    if fake:
        from tests.fakes.fake_engine import FakeTradingAgentsGraph
        return lambda: FakeTradingAgentsGraph(callbacks=callbacks)
    # Plan 4 will wire the real engine here.
    raise NotImplementedError("real engine wiring lands in Plan 4")


@router.post("/runs/{run_id}/start", status_code=status.HTTP_202_ACCEPTED)
async def start_run(
    run_id: UUID,
    user_id: Annotated[UUID, Depends(current_user_id)],
):
    settings = get_settings()

    # 1. Load run row
    run = await fetch_run(
        run_id=run_id,
        supabase_url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
    )
    if str(run["user_id"]) != str(user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your run")

    # 2. Load BYO keys (synchronous w.r.t. start: fail fast if missing)
    config = run.get("config") or {}
    provider = config.get("llm_provider", "openai")
    try:
        env_keys = await load_keys(
            user_id=user_id,
            providers=[provider],
            supabase_url=settings.supabase_url,
            service_role_key=settings.supabase_service_role_key,
        )
    except KeyVaultError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    # 3. Mark run started + create bus
    await mark_run_started(
        run_id=run_id,
        supabase_url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
    )
    bus = registry.get_or_create(str(run_id))
    publisher = SSEPublisher(bus=bus, run_id=str(run_id), verbose=False)

    factory = _make_engine_factory(
        callbacks=[publisher], fake=settings.use_fake_engine, env=env_keys,
    )

    # 4. Kick off the run as a background task
    async def _drive():
        events_for_persist: list[dict[str, Any]] = []

        async def _capture():
            queue = bus.subscribe()
            try:
                while True:
                    event = await queue.get()
                    if event is None or event is bus._buffer.maxlen and False:
                        break
                    if hasattr(event, "data"):
                        events_for_persist.append(event.data)
            except Exception:
                pass

        capture_task = asyncio.create_task(_capture())
        try:
            final_state, decision = await run_engine(
                make_engine=factory,
                ticker=run["ticker"],
                trade_date=run["trade_date"],
                bus=bus,
            )
            await finalize_run(
                run_id=run_id,
                decision=decision,
                events=events_for_persist,
                final_state_keys=list(final_state.keys()),
                supabase_url=settings.supabase_url,
                service_role_key=settings.supabase_service_role_key,
            )
        except Exception as exc:
            await fail_run(
                run_id=run_id,
                error=str(exc),
                events=events_for_persist,
                supabase_url=settings.supabase_url,
                service_role_key=settings.supabase_service_role_key,
            )
        finally:
            capture_task.cancel()
            registry.drop(str(run_id))

    asyncio.create_task(_drive())
    return {"run_id": str(run_id), "status": "started"}


@router.get("/runs/{run_id}/stream")
async def stream_run(
    run_id: UUID,
    user_id: Annotated[UUID, Depends(current_user_id)],
    last_event_id: Annotated[int | None, Header()] = None,
):
    bus = registry.get(str(run_id))
    if bus is None:
        # Run is not in-memory — caller should have hit the start endpoint
        # first, OR the run already finished (caller should hydrate from DB).
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no live run")

    queue = bus.subscribe()

    async def _generator():
        # Replay missed events
        for event in bus.replay_since(last_event_id):
            yield {"id": str(event.id), "data": _json(event.data)}
        # Live stream
        from api.bus import SENTINEL
        try:
            while True:
                event = await queue.get()
                if event is SENTINEL:
                    return
                yield {"id": str(event.id), "data": _json(event.data)}
        finally:
            bus.unsubscribe(queue)

    return EventSourceResponse(_generator(), ping=15)


def _json(obj) -> str:
    import json
    return json.dumps(obj)
```

- [ ] **Step 5: Wire the router in `apps/api/src/api/main.py`**

Replace the contents of `apps/api/src/api/main.py`:

```python
"""FastAPI app factory."""
from fastapi import FastAPI

from api.logging import configure_logging
from api.routes import router as runs_router


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="tradingagents-api", version="0.1.0")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(runs_router)
    return app


app = create_app()
```

- [ ] **Step 6: Run — expect pass**

```bash
cd apps/api && uv run pytest tests/test_routes.py -v
```

Expected: 2 tests pass.

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/api/routes.py apps/api/src/api/main.py \
        apps/api/tests/test_routes.py apps/api/tests/conftest.py
git commit -m "feat(api): add POST /runs/{id}/start (fake-engine path)"
```

---

### Task 21: TDD — `GET /runs/{id}/stream` returns SSE

**Files:**
- Modify: `apps/api/tests/test_routes.py`

- [ ] **Step 1: Add the test**

Append to `tests/test_routes.py`:

```python
def test_stream_returns_sse_events(app, auth_header):
    """Smoke test that the SSE endpoint returns text/event-stream and at
    least one event when a run is in flight."""
    client = TestClient(app)

    # Manually populate the bus to simulate an in-flight run
    from api.bus import registry
    bus = registry.get_or_create(RUN_ID)
    bus.publish({"type": "agent_started", "agent": "market_analyst"})
    bus.publish({"type": "agent_completed", "agent": "market_analyst", "summary": "ok"})

    # Stream — close after we've seen 2 events
    with client.stream("GET", f"/runs/{RUN_ID}/stream",
                       headers={**auth_header, "accept": "text/event-stream"}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")

        # Read a chunk
        first_chunk = next(r.iter_text(chunk_size=512))
        assert "agent_started" in first_chunk

    # Cleanup
    bus.close()
    registry.drop(RUN_ID)


def test_stream_404_when_run_not_in_registry(app, auth_header):
    client = TestClient(app)
    r = client.get(f"/runs/00000000-0000-0000-0000-000000000fff/stream",
                   headers=auth_header)
    assert r.status_code == 404
```

- [ ] **Step 2: Run — expect pass**

```bash
cd apps/api && uv run pytest tests/test_routes.py -v
```

Expected: 4 tests pass.

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/test_routes.py
git commit -m "test(api): assert SSE stream endpoint emits live events"
```

---

### Task 22: TDD — Last-Event-ID replay on the stream endpoint

**Files:**
- Modify: `apps/api/tests/test_routes.py`

- [ ] **Step 1: Add the test**

Append:

```python
def test_stream_replays_with_last_event_id(app, auth_header):
    client = TestClient(app)

    from api.bus import registry
    bus = registry.get_or_create(RUN_ID)
    bus.publish({"type": "a", "n": 1})
    bus.publish({"type": "b", "n": 2})
    bus.publish({"type": "c", "n": 3})

    headers = {
        **auth_header,
        "accept": "text/event-stream",
        "Last-Event-ID": "1",   # we already saw event id=1
    }
    with client.stream("GET", f"/runs/{RUN_ID}/stream", headers=headers) as r:
        assert r.status_code == 200
        body = next(r.iter_text(chunk_size=2048))

    # Should contain events 2 and 3 but not 1
    assert "\"n\": 2" in body
    assert "\"n\": 3" in body
    assert "\"n\": 1" not in body

    bus.close()
    registry.drop(RUN_ID)
```

- [ ] **Step 2: Run — expect pass**

```bash
cd apps/api && uv run pytest tests/test_routes.py::test_stream_replays_with_last_event_id -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/test_routes.py
git commit -m "test(api): assert SSE Last-Event-ID replay"
```

---

## Phase 10 — Janitor (cron-driven sweep)

### Task 23: TDD — `sweep_stuck_runs` marks old running rows failed

**Files:**
- Create: `apps/api/tests/test_janitor.py`
- Create: `apps/api/src/api/janitor.py`

- [ ] **Step 1: Write the failing test**

Create `apps/api/tests/test_janitor.py`:

```python
"""Tests for the janitor that sweeps stuck runs."""
import json
from datetime import datetime, timedelta, timezone

import httpx

from api.janitor import sweep_stuck_runs


async def test_sweep_marks_old_running_rows_as_failed():
    captured = {"calls": []}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["calls"].append({
            "method": request.method,
            "url": str(request.url),
            "body": json.loads(request.content) if request.content else None,
        })
        if request.method == "GET":
            old = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            return httpx.Response(200, json=[
                {"id": "00000000-0000-0000-0000-000000000aaa", "started_at": old},
            ])
        return httpx.Response(204, json=[])

    transport = httpx.MockTransport(handler)
    swept = await sweep_stuck_runs(
        supabase_url="http://test.local",
        service_role_key="srv",
        threshold_minutes=30,
        transport=transport,
    )
    assert swept == 1
    methods = [c["method"] for c in captured["calls"]]
    assert "GET" in methods
    assert "PATCH" in methods
    patch_call = next(c for c in captured["calls"] if c["method"] == "PATCH")
    assert patch_call["body"]["status"] == "failed"
    assert "Run timed out" in patch_call["body"]["error"]


async def test_sweep_returns_zero_when_no_stuck_rows():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    swept = await sweep_stuck_runs(
        supabase_url="http://test.local",
        service_role_key="srv",
        threshold_minutes=30,
        transport=transport,
    )
    assert swept == 0
```

- [ ] **Step 2: Run — expect failure**

```bash
cd apps/api && uv run pytest tests/test_janitor.py -v
```

Expected: ImportError.

- [ ] **Step 3: Write `apps/api/src/api/janitor.py`**

```python
"""Janitor: scans `runs` for rows stuck in `running` state and marks them
failed. Designed to be invoked by a Render cron job every 5 minutes.

Entry point: `python -m api.janitor`
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import httpx

from api.logging import configure_logging, get_logger
from api.settings import get_settings

logger = get_logger(__name__)


async def sweep_stuck_runs(
    *,
    supabase_url: str,
    service_role_key: str,
    threshold_minutes: int,
    transport: httpx.AsyncBaseTransport | None = None,
) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=threshold_minutes)).isoformat()
    base = supabase_url.rstrip("/")
    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(transport=transport, timeout=10.0) as client:
        # Find stuck rows
        get = await client.get(
            f"{base}/rest/v1/runs",
            headers=headers,
            params={
                "status": "eq.running",
                "started_at": f"lt.{cutoff}",
                "select": "id,started_at",
            },
        )
        if get.status_code != 200:
            raise RuntimeError(f"janitor list {get.status_code}")
        stuck = get.json()
        if not stuck:
            return 0

        # Mark each one failed
        for row in stuck:
            patch = await client.patch(
                f"{base}/rest/v1/runs",
                headers=headers,
                params={"id": f"eq.{row['id']}"},
                content=json.dumps({
                    "status": "failed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "error": "Run timed out or worker died",
                }, default=str),
            )
            if patch.status_code not in (200, 204):
                logger.error("janitor patch failed",
                             run_id=row["id"], status=patch.status_code)

    logger.info("janitor sweep done", swept=len(stuck))
    return len(stuck)


def main() -> None:
    """Cron entrypoint: `python -m api.janitor`."""
    configure_logging()
    settings = get_settings()
    swept = asyncio.run(sweep_stuck_runs(
        supabase_url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
        threshold_minutes=settings.stuck_run_threshold_minutes,
    ))
    print(f"swept {swept} stuck runs")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run — expect pass**

```bash
cd apps/api && uv run pytest tests/test_janitor.py -v
```

Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/api/janitor.py apps/api/tests/test_janitor.py
git commit -m "feat(api): add janitor sweep_stuck_runs (cron entrypoint)"
```

---

## Phase 11 — Dockerfile

### Task 24: Write `Dockerfile` and `.dockerignore`

**Files:**
- Create: `apps/api/Dockerfile`
- Create: `apps/api/.dockerignore`

- [ ] **Step 1: Write `.dockerignore`**

Create `apps/api/.dockerignore`:

```
# Build context is the repo root (per render.yaml rootDir: .)
# Start from "exclude everything" then opt-in
**/*

# Include just what we need
!apps/api/pyproject.toml
!apps/api/uv.lock
!apps/api/src/
!tradingagents/
!tradingagents/**

# Exclude __pycache__ + tests
**/__pycache__
**/.pytest_cache
**/*.pyc
apps/api/tests/
```

- [ ] **Step 2: Write `Dockerfile`**

Create `apps/api/Dockerfile`:

```dockerfile
# syntax=docker/dockerfile:1.7

FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

# System deps (none required for v1, but keep the layer for future additions)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy upstream tradingagents package (engine — never modified)
COPY tradingagents/ /app/tradingagents/

# Copy our app
COPY apps/api/pyproject.toml apps/api/uv.lock /app/apps/api/
WORKDIR /app/apps/api
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project

COPY apps/api/src/ /app/apps/api/src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# Non-root
RUN useradd -m appuser && chown -R appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/apps/api/src:/app

# Render injects $PORT
CMD ["sh", "-c", "uv run uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

- [ ] **Step 3: Build locally**

```bash
docker build -t tradingagents-api:dev -f apps/api/Dockerfile .
```

Expected: image builds (takes 1–2 minutes on first run). Note image size at the end.

- [ ] **Step 4: Run the container**

```bash
docker run --rm -p 8000:8000 \
    -e SUPABASE_URL=http://example.invalid \
    -e SUPABASE_SERVICE_ROLE_KEY=test \
    -e USE_FAKE_ENGINE=1 \
    tradingagents-api:dev
```

In another terminal:

```bash
curl -s http://localhost:8000/healthz
```

Expected: `{"status":"ok"}`. Stop the container with Ctrl-C.

- [ ] **Step 5: Commit**

```bash
git add apps/api/Dockerfile apps/api/.dockerignore
git commit -m "build(api): add Dockerfile + dockerignore"
```

---

## Phase 12 — Render Blueprint update

### Task 25: Replace placeholder `render.yaml` with real config

**Files:**
- Modify: `render.yaml`

- [ ] **Step 1: Read existing**

```bash
cat render.yaml
```

- [ ] **Step 2: Replace contents**

Overwrite `render.yaml` with:

```yaml
services:
  - type: web
    name: tradingagents-api
    runtime: docker
    region: oregon
    plan: starter
    rootDir: .
    dockerfilePath: apps/api/Dockerfile
    healthCheckPath: /healthz
    autoDeploy: true
    envVars:
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_SERVICE_ROLE_KEY
        sync: false
      - key: SUPABASE_JWT_SECRET
        sync: false
      - key: USE_FAKE_ENGINE
        value: "1"
      - key: LOG_JSON
        value: "true"
      - key: LOG_LEVEL
        value: "INFO"

  - type: cron
    name: tradingagents-janitor
    runtime: docker
    region: oregon
    plan: starter
    schedule: "*/5 * * * *"
    rootDir: .
    dockerfilePath: apps/api/Dockerfile
    dockerCommand: python -m api.janitor
    envVars:
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_SERVICE_ROLE_KEY
        sync: false
      - key: STUCK_RUN_THRESHOLD_MINUTES
        value: "30"
```

- [ ] **Step 3: Lint**

```bash
python3 -c "import yaml; yaml.safe_load(open('render.yaml'))"
```

Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add render.yaml
git commit -m "build: render.yaml — web + cron services for FastAPI"
```

---

### Task 26: Add `.github/workflows/api-ci.yml`

**Files:**
- Create: `.github/workflows/api-ci.yml`

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/api-ci.yml`:

```yaml
name: API CI

on:
  pull_request:
    paths:
      - 'apps/api/**'
      - 'tradingagents/**'
      - '.github/workflows/api-ci.yml'
  push:
    branches:
      - main
    paths:
      - 'apps/api/**'

jobs:
  pytest:
    name: pytest (apps/api)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.13
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Install dependencies
        working-directory: apps/api
        run: uv sync --locked

      - name: Lint
        working-directory: apps/api
        run: uv run ruff check . && uv run ruff format --check .

      - name: Tests
        working-directory: apps/api
        env:
          SUPABASE_URL: http://test.local
          SUPABASE_SERVICE_ROLE_KEY: test-srv
          SUPABASE_JWT_SECRET: test-secret-do-not-use-in-prod
          USE_FAKE_ENGINE: "1"
        run: uv run pytest -v
```

- [ ] **Step 2: Lint**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/api-ci.yml'))"
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/api-ci.yml
git commit -m "ci: add api-ci workflow (pytest + ruff)"
```

---

## Phase 13 — Push + draft PR + Render provisioning

### Task 27: Push branch + open draft PR

**Files:** none

- [ ] **Step 1: Push**

```bash
git push -u origin feature/api
```

- [ ] **Step 2: Open draft PR**

```bash
gh pr create --repo elagerway/tradingagents --draft \
  --base main --head feature/api \
  --title "Plan 2: API service — FastAPI + SSE + fake engine + Render Blueprint" \
  --body "$(cat <<'EOF'
## Summary

Implements **Plan 2** — the FastAPI service in `apps/api/` that hosts the trading-agents engine on Render.

- Bus, JWT auth, vault key fetcher, SSE adapter, worker, janitor — all unit-tested with a fake engine
- POST /runs/{id}/start + GET /runs/{id}/stream + GET /healthz
- Dockerfile + render.yaml (web service + janitor cron)
- GitHub Actions CI (pytest + ruff)

Real engine wiring is **Plan 4**.

## Plan

[`docs/superpowers/plans/2026-04-30-api-service.md`](docs/superpowers/plans/2026-04-30-api-service.md)

## Test plan

- [ ] All pytest tests pass locally (`make api-test`)
- [ ] Docker image builds (`docker build -t tradingagents-api:dev -f apps/api/Dockerfile .`)
- [ ] Local container responds to `/healthz`
- [ ] CI green
- [ ] Render Blueprint applied + service deploys + `/healthz` responds on Render URL
- [ ] Render cron triggers `python -m api.janitor` once

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Watch CI**

```bash
gh pr checks --repo elagerway/tradingagents --watch
```

Expected: api-ci goes green within 5 minutes.

- No commit. Reverts to Task 28 if CI fails.

---

### Task 28: Apply Render Blueprint

**Files:** none (external action)

- [ ] **Step 1: Push hasn't been to main yet — but Render reads the Blueprint from the branch you point it at**

Open Render dashboard → New → Blueprint. Point at `elagerway/tradingagents` and select branch `feature/api`. Render parses `render.yaml`.

- [ ] **Step 2: Provide secret values**

When prompted, paste:
- `SUPABASE_URL` = `https://rhkxooyygufqgkpxmjvr.supabase.co`
- `SUPABASE_SERVICE_ROLE_KEY` = (from `.env.local`)
- `SUPABASE_JWT_SECRET` = (from Supabase dashboard → Settings → API → JWT Secret OR find via `supabase` CLI)

These are stored in Render's secret store and never committed.

- [ ] **Step 3: Deploy**

Click Apply. Render creates the web service and cron, builds the Docker image, and deploys.

Expected: ~5–8 minutes for the first deploy. After deploy, you'll have a URL like `https://tradingagents-api-xxxx.onrender.com`.

- [ ] **Step 4: Capture the service URL**

Add it to `.env.local` at the repo root:

```
RENDER_API_BASE_URL=https://tradingagents-api-xxxx.onrender.com
```

(Already gitignored.)

- [ ] **Step 5: Verify**

```bash
curl -s "$RENDER_API_BASE_URL/healthz"
```

Expected: `{"status":"ok"}`.

No commit (this is configuration outside the repo).

---

### Task 29: Final smoke — start a run via cURL

**Files:** none (verification)

- [ ] **Step 1: Manually create a run row in Supabase Cloud**

Use the Supabase SQL editor or run via psql with your DB password:

```sql
INSERT INTO public.runs (id, user_id, ticker, trade_date, status, config)
SELECT
  '99999999-0000-0000-0000-000000000001'::uuid,
  id,
  'NVDA', '2026-01-15', 'pending',
  '{"llm_provider":"openai"}'::jsonb
FROM auth.users WHERE email = 'dev@snapsonic.local';
```

(The dev user is allowlisted from Plan 1's seed — but seed only ran locally. For Cloud, you must allowlist a real user via `update public.profiles set allowed_at = now() where id = ...`.)

- [ ] **Step 2: Get a JWT for that user**

For local-loopback testing, mint an HS256 token signed with `SUPABASE_JWT_SECRET`:

```bash
cd apps/api
uv run python -c "
import jwt, time, os
from dotenv import load_dotenv
load_dotenv('../../.env.local')
print(jwt.encode({
    'sub': '<the-allowlisted-user-uuid>',
    'aud': 'authenticated',
    'role': 'authenticated',
    'exp': int(time.time()) + 3600,
}, os.environ['SUPABASE_JWT_SECRET'], algorithm='HS256'))
"
```

Save the token to a shell var:

```bash
TOKEN=<output-from-above>
```

- [ ] **Step 3: POST /runs/{id}/start**

```bash
curl -i -X POST "$RENDER_API_BASE_URL/runs/99999999-0000-0000-0000-000000000001/start" \
  -H "Authorization: Bearer $TOKEN"
```

Expected: HTTP 202 with `{"run_id":"99999999-...","status":"started"}`. (The run will fail at the BYO key check because the test user has no `vault_save_key` calls yet — that's fine; we're testing the routing.)

- [ ] **Step 4: GET /runs/{id}/stream**

```bash
curl -N -H "Authorization: Bearer $TOKEN" \
  "$RENDER_API_BASE_URL/runs/99999999-0000-0000-0000-000000000001/stream"
```

Expected: SSE stream. With the fake engine and a pre-loaded BYO key (insert via `vault_save_key`-equivalent), you'd see the canned event sequence. With no key, you'd see a `run_failed` event for the missing-key path.

No commit. This is end-to-end smoke validation.

---

### Task 30: Mark PR ready and merge

**Files:** none (external action)

- [ ] **Step 1: Confirm everything is green**

- ✅ Local pytest passes
- ✅ Docker build succeeds locally
- ✅ CI is green
- ✅ Render deploy succeeded
- ✅ `/healthz` responds on the live URL
- ✅ Manual cURL smoke produced expected behavior

- [ ] **Step 2: Mark ready**

```bash
gh pr ready --repo elagerway/tradingagents
```

- [ ] **Step 3: Merge**

```bash
gh pr merge --repo elagerway/tradingagents --squash --delete-branch --admin
```

- [ ] **Step 4: Sync local**

```bash
git checkout main && git pull && git branch -D feature/api 2>/dev/null || true
```

**Plan 2 done.** Plan 3 (Next.js web app) and Plan 4 (real engine wiring + smoke test against real LLMs) are now unblocked.

---

## Self-Review

### Spec coverage

| Spec section | Covered by tasks |
|---|---|
| §5.2 endpoints (`POST /runs/{id}/start`, `GET /runs/{id}/stream`, `/healthz`) | Tasks 3 (healthz), 20 (start), 21–22 (stream) |
| §5.2 internal modules (auth, keys, engine, bus, worker, janitor) | Tasks 6–18, 23 |
| §6 data flow — `Bus` per run, replay on reconnect, terminal close | Tasks 6–10, 18, 21–22 |
| §6 BYO key flow — service-role RPC, never logged, scoped to providers | Tasks 13 (load_keys + caplog assertion) |
| §7 row 1 — sync fail-fast on missing key | Task 20 (start endpoint maps `KeyVaultError` → 400) |
| §7 row 7 — Render process dies → janitor marks failed | Task 23 |
| §7 row 8 — browser disconnect → run continues server-side | Implicit in task design (Bus survives subscriber drop; only registry.drop fully ends it) |
| §7 row 11 — bad JWT → 401 | Tasks 11–12 |
| §7 row 14 — no per-user concurrency cap in v1 | Intentionally not implemented (deferred to v1.1) |
| §7 row 15 — unhandled engine exception → `runs.status='failed'` + error written | Task 18 (worker emits run_failed + close) + Task 20 (`fail_run` call in `_drive`'s except clause) |
| §8 testing — fake engine + httpx MockTransport | Tasks 14, 19, 23 |
| §11 decisions log — direct SSE Approach 1, in-process bus | Tasks 6–10, 21 |

**No gaps.**

### Placeholder scan

- No "TBD"/"TODO"/"implement later"
- Every code block contains real, runnable code
- Every command has expected output
- Real engine wiring at Task 20 is explicitly deferred to Plan 4 and the code raises `NotImplementedError` — that's a correct YAGNI placeholder, not a plan failure

### Type/name consistency

- `Bus`, `BusEvent`, `BusRegistry`, `SENTINEL` defined in Task 6/10, used same way in Tasks 16, 17, 20, 21, 22.
- `SSEPublisher(bus, run_id, verbose)` signature consistent across Tasks 15–17, 20.
- `decode_user_token(token, hs256_secret=...)` signature consistent across Tasks 11–12.
- `current_user_id` dependency consistent across Tasks 12, 20.
- `load_keys(user_id, providers, supabase_url, service_role_key, ...)` consistent in Tasks 13, 20.
- `fetch_run`, `mark_run_started`, `finalize_run`, `fail_run` consistent across Tasks 19, 20.
- `run_engine(make_engine, ticker, trade_date, bus)` consistent across Tasks 17, 18, 20.
- `sweep_stuck_runs(supabase_url, service_role_key, threshold_minutes, transport)` consistent across Tasks 23.

No drift detected.

---

## Execution handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-30-api-service.md`. Two execution options:**

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, two-stage review between tasks (spec then quality), commit on green.
2. **Inline Execution** — Execute tasks in this session using `executing-plans`, batch checkpoints.

**Which approach?**
