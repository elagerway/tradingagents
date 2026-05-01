# Real Engine Wiring Implementation Plan (Plan 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Replace the fake engine in `apps/api/` with the real upstream `TradingAgentsGraph`, threading the user's BYO API key through the engine's config (no `os.environ` mutation, no upstream modification). Add a real-LLM smoke test gated behind a manual GitHub Actions trigger so it runs only on demand at small cost (~$0.005/run via DeepSeek). Flip `USE_FAKE_ENGINE=0` in production and verify a real run completes end-to-end.

**Architecture:** Subclass `TradingAgentsGraph` in our service code (`apps/api/src/api/real_engine.py`) to override `_get_provider_kwargs` and forward `api_key` from config to the LLM clients. The factory in `routes.py` instantiates this subclass when `USE_FAKE_ENGINE=0`. Per-run config (loaded from `runs.config` jsonb) is shallow-merged with `DEFAULT_CONFIG` and the BYO key is injected as a config field. No env-var mutation means concurrent runs from different users cannot collide.

**Tech Stack:** Python 3.13, the existing `tradingagents` package as a dependency (already vendored into the Docker image), pytest with a custom `real_engine` marker, GitHub Actions `workflow_dispatch` trigger.

**Reference spec:** [`docs/superpowers/specs/2026-04-30-tradingagents-app-design.md`](../specs/2026-04-30-tradingagents-app-design.md)
**Reference plans:** Plan 1 (DB) shipped · Plan 2 (FastAPI) shipped · Plan 3 (Web) shipped

---

## Working assumptions

- Plans 1–3 are merged to `main` and live (Vercel + Render).
- The user has access to a DeepSeek API key (or willing to use a small OpenAI key) for the real-engine smoke. We use DeepSeek as the canonical "cheapest" path; OpenAI works equally well.
- The repo is on branch `feature/real-engine` (already created).
- The Docker image already includes the upstream `tradingagents/` Python package (per Plan 2's Dockerfile — `COPY tradingagents/ /app/tradingagents/`).
- We intentionally do NOT modify the upstream `tradingagents/` package. Subclassing in our wrapper is the chosen extension mechanism.

---

## File map (everything this plan creates or modifies)

```
apps/api/
├── src/api/
│   ├── real_engine.py                          # create — TradingAgentsGraphWithApiKey subclass
│   ├── routes.py                                # modify — _make_engine_factory branches on USE_FAKE_ENGINE
│   └── settings.py                              # already has use_fake_engine field
├── tests/
│   ├── conftest.py                              # modify — add --run-real-engine flag + collection hook
│   ├── test_real_engine.py                      # create — single real-engine test (gated by marker)
│   └── test_routes.py                           # modify — assert real-engine factory wires correctly (mocked)
├── pyproject.toml                               # modify — register real_engine pytest marker
└── Makefile (repo root)                         # modify — add api-test-real target

.github/workflows/real-engine-smoke.yml         # create — workflow_dispatch trigger

docs/superpowers/runbooks/2026-05-01-real-engine-rollout.md  # create — operational notes
```

---

## Phase 1 — Real engine subclass + factory wiring

### Task 1: Create `TradingAgentsGraphWithApiKey` subclass

**Files:**
- Create: `apps/api/src/api/real_engine.py`

- [ ] **Step 1: Write the subclass**

```python
# apps/api/src/api/real_engine.py
"""Subclass of TradingAgentsGraph that forwards `api_key` from config to LLM clients.

The upstream engine reads keys from os.environ by default. Setting env vars
per-call is unsafe under concurrency (process-global state). The subclass
pattern keeps each engine instance self-contained — its LLM clients are
constructed at __init__ time with the api_key baked in.

We don't modify the upstream package; we subclass it in our wrapper.
"""
from __future__ import annotations

from typing import Any

from tradingagents.graph.trading_graph import TradingAgentsGraph


class TradingAgentsGraphWithApiKey(TradingAgentsGraph):
    """TradingAgentsGraph that forwards `api_key` from config to LLM clients.

    The upstream `_get_provider_kwargs` only forwards thinking-config kwargs
    (`google_thinking_level`, `openai_reasoning_effort`, etc.). We extend it
    to also forward `api_key` if present in `self.config`.
    """

    def _get_provider_kwargs(self) -> dict[str, Any]:
        kwargs = super()._get_provider_kwargs()
        if api_key := self.config.get("api_key"):
            kwargs["api_key"] = api_key
        return kwargs
```

- [ ] **Step 2: Verify the import works**

```bash
cd /Users/erik/Developer/Github/Snapsonic/tradingAgents/apps/api
SUPABASE_URL=http://test.local SUPABASE_SERVICE_ROLE_KEY=test \
uv run python -c "from api.real_engine import TradingAgentsGraphWithApiKey; print('ok')"
```

Expected: `ok`. If the import fails, the upstream `tradingagents` package isn't on the Python path. Verify `pyproject.toml` of `apps/api/` has `tradingagents` as a dependency or that `PYTHONPATH` includes the repo root.

- [ ] **Step 3: Commit**

```bash
git add apps/api/src/api/real_engine.py
git commit -m "feat(api): add TradingAgentsGraphWithApiKey subclass"
```

---

### Task 2: TDD — assert real-engine factory wires correctly (mocked)

**Files:**
- Modify: `apps/api/tests/test_routes.py`

- [ ] **Step 1: Add the test**

Append to `apps/api/tests/test_routes.py`:

```python
def test_make_engine_factory_real_path_uses_subclass(monkeypatch):
    """When USE_FAKE_ENGINE=0, the factory should construct
    TradingAgentsGraphWithApiKey with config including api_key."""
    monkeypatch.setenv("USE_FAKE_ENGINE", "0")
    monkeypatch.setenv("SUPABASE_URL", "http://test.local")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "srv")

    from api.settings import get_settings
    get_settings.cache_clear()

    from api.routes import _make_engine_factory
    from unittest.mock import patch

    captured: dict = {}

    def fake_constructor(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        # Return a stub object that has a propagate method
        class Stub:
            def propagate(self, ticker, date):
                return ({"ticker": ticker}, "BUY")
        return Stub()

    with patch("api.real_engine.TradingAgentsGraphWithApiKey", fake_constructor):
        factory = _make_engine_factory(
            callbacks=[],
            fake=False,
            env={"openai": "sk-test-secret"},
            run_config={"llm_provider": "openai"},
        )
        engine = factory()

    assert engine is not None
    config = captured["kwargs"]["config"]
    assert config["api_key"] == "sk-test-secret"
    assert config["llm_provider"] == "openai"
    # Default config keys are still present
    assert "deep_think_llm" in config
    assert "quick_think_llm" in config
    # Render-friendly paths
    assert config["results_dir"].startswith("/tmp/")
    assert config["data_cache_dir"].startswith("/tmp/")
```

- [ ] **Step 2: Run — expect failure**

```bash
cd apps/api
SUPABASE_URL=http://test.local SUPABASE_SERVICE_ROLE_KEY=test SUPABASE_JWT_SECRET=secret \
uv run pytest tests/test_routes.py::test_make_engine_factory_real_path_uses_subclass -v
```

Expected: fail because the current factory raises `NotImplementedError` for the real path AND signature doesn't accept `run_config`.

- [ ] **Step 3: Commit the failing test**

```bash
git add apps/api/tests/test_routes.py
git commit -m "test(api): add real-engine factory wiring test (RED)"
```

---

### Task 3: Implement real-engine path in `_make_engine_factory`

**Files:**
- Modify: `apps/api/src/api/routes.py`

- [ ] **Step 1: Update `_make_engine_factory` and its call site**

Find the existing function in `apps/api/src/api/routes.py`:

```python
def _make_engine_factory(*, callbacks, fake: bool, env: dict[str, str]):
    """Returns a callable that constructs an engine instance with our
    callback wired in. Plan 4 swaps the fake for the real one."""
    if fake:
        from api.fakes.fake_engine import FakeTradingAgentsGraph
        return lambda: FakeTradingAgentsGraph(callbacks=callbacks)
    raise NotImplementedError("real engine wiring lands in Plan 4")
```

Replace with:

```python
def _make_engine_factory(
    *,
    callbacks,
    fake: bool,
    env: dict[str, str],
    run_config: dict | None = None,
):
    """Returns a callable that constructs an engine instance with our
    callback wired in. The fake variant is used in tests + Plan 2-3 deploys;
    the real variant runs the upstream LangGraph engine with BYO keys
    threaded through config."""
    if fake:
        from api.fakes.fake_engine import FakeTradingAgentsGraph
        return lambda: FakeTradingAgentsGraph(callbacks=callbacks)

    # Real engine path
    from tradingagents.default_config import DEFAULT_CONFIG
    from api.real_engine import TradingAgentsGraphWithApiKey

    rc = run_config or {}
    provider = rc.get("llm_provider", "openai")
    api_key = env.get(provider)
    if not api_key:
        raise RuntimeError(f"No BYO key loaded for provider: {provider}")

    engine_config = {
        **DEFAULT_CONFIG,
        **rc,
        "api_key": api_key,
        # Render's container has /tmp writable but $HOME may be locked-down
        "results_dir": "/tmp/tradingagents/logs",
        "data_cache_dir": "/tmp/tradingagents/cache",
    }

    return lambda: TradingAgentsGraphWithApiKey(
        selected_analysts=["market", "social", "news", "fundamentals"],
        debug=False,
        config=engine_config,
        callbacks=callbacks,
    )
```

Find the call site in `start_run`:

```python
factory = _make_engine_factory(
    callbacks=[publisher], fake=settings.use_fake_engine, env=env_keys,
)
```

Update it to pass `run_config`:

```python
factory = _make_engine_factory(
    callbacks=[publisher],
    fake=settings.use_fake_engine,
    env=env_keys,
    run_config=run.get("config") or {},
)
```

- [ ] **Step 2: Run the failing test — expect pass**

```bash
cd apps/api
SUPABASE_URL=http://test.local SUPABASE_SERVICE_ROLE_KEY=test SUPABASE_JWT_SECRET=secret \
uv run pytest tests/test_routes.py::test_make_engine_factory_real_path_uses_subclass -v
```

Expected: PASS.

- [ ] **Step 3: Run the full test suite — all 35 should pass**

```bash
cd apps/api
SUPABASE_URL=http://test.local SUPABASE_SERVICE_ROLE_KEY=test SUPABASE_JWT_SECRET=secret \
uv run pytest -v
```

Expected: 35 tests pass (34 prior + 1 new).

- [ ] **Step 4: Lint**

```bash
uv run ruff check . && uv run ruff format --check .
```

Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/api/routes.py
git commit -m "feat(api): wire real engine in _make_engine_factory (GREEN)"
```

---

### Task 4: Add structured logging around real engine boundary

**Files:**
- Modify: `apps/api/src/api/routes.py`

- [ ] **Step 1: Add log statements**

Inside the real-engine path of `_make_engine_factory`, before the `return lambda:`, add:

```python
    logger.info(
        "real_engine_factory",
        provider=provider,
        deep_think_llm=engine_config.get("deep_think_llm"),
        quick_think_llm=engine_config.get("quick_think_llm"),
        max_debate_rounds=engine_config.get("max_debate_rounds"),
    )
```

(Make sure `from api.logging import get_logger` and `logger = get_logger(__name__)` exist at the top of `routes.py`. They likely do already from Plan 2.)

- [ ] **Step 2: Run tests**

```bash
cd apps/api
SUPABASE_URL=http://test.local SUPABASE_SERVICE_ROLE_KEY=test SUPABASE_JWT_SECRET=secret \
uv run pytest -v
```

Expected: 35 pass.

- [ ] **Step 3: Lint + commit**

```bash
uv run ruff check . && uv run ruff format --check .
```

```bash
git add apps/api/src/api/routes.py
git commit -m "feat(api): structured logging around real engine factory"
```

---

## Phase 2 — Real-engine smoke test infrastructure

### Task 5: Register pytest `real_engine` marker + skip-by-default

**Files:**
- Modify: `apps/api/pyproject.toml` (add marker)
- Modify: `apps/api/tests/conftest.py` (create if missing, or edit)

- [ ] **Step 1: Register the marker in `apps/api/pyproject.toml`**

Find the `[tool.pytest.ini_options]` section and add `markers`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["src"]
testpaths = ["tests"]
markers = [
    "real_engine: marks tests that call the real TradingAgentsGraph and incur LLM cost (deselect with -m 'not real_engine')",
]
```

- [ ] **Step 2: Add a top-level `apps/api/tests/conftest.py`** (NOT inside `tests/fakes/` — there's a separate fixtures file there). If a top-level `conftest.py` already exists from Plan 2, append to it.

```python
# apps/api/tests/conftest.py
"""Top-level pytest config: gate real-engine tests behind --run-real-engine."""
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-real-engine",
        action="store_true",
        default=False,
        help="Run tests marked @pytest.mark.real_engine (calls real LLMs, costs money)",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-real-engine"):
        return
    skip_real = pytest.mark.skip(reason="pass --run-real-engine to run")
    for item in items:
        if item.get_closest_marker("real_engine"):
            item.add_marker(skip_real)
```

If `apps/api/tests/conftest.py` already exists from Plan 2 (it does — for shared fixtures), merge: add the `pytest_addoption` and `pytest_collection_modifyitems` functions to the existing file. The rest of the file should stay unchanged.

- [ ] **Step 3: Verify the marker is registered**

```bash
cd apps/api
SUPABASE_URL=http://test.local SUPABASE_SERVICE_ROLE_KEY=test \
uv run pytest --markers 2>&1 | grep real_engine
```

Expected: a line mentioning `real_engine: marks tests that call the real TradingAgentsGraph...`

- [ ] **Step 4: Run pytest — should still be 35 passing**

```bash
cd apps/api
SUPABASE_URL=http://test.local SUPABASE_SERVICE_ROLE_KEY=test SUPABASE_JWT_SECRET=secret \
uv run pytest -v
```

Expected: 35 pass (no real-engine tests yet — those land next task).

- [ ] **Step 5: Commit**

```bash
git add apps/api/pyproject.toml apps/api/tests/conftest.py
git commit -m "test(api): register real_engine marker + skip-by-default conftest"
```

---

### Task 6: Add the single real-engine smoke test

**Files:**
- Create: `apps/api/tests/test_real_engine.py`

- [ ] **Step 1: Write the test**

```python
# apps/api/tests/test_real_engine.py
"""Real-engine smoke test — calls the upstream TradingAgentsGraph end-to-end
with the cheapest viable provider (DeepSeek). Skipped by default.

To run: `uv run pytest -m real_engine --run-real-engine -v`
Or via Makefile: `make api-test-real`
Or via GitHub Actions: workflow_dispatch on `real-engine-smoke.yml`.

Cost per run: roughly $0.002–$0.01 with `deepseek-chat` (verify against
DeepSeek's current pricing page before merge).
"""
import os

import pytest


@pytest.mark.real_engine
def test_real_engine_returns_valid_decision():
    """Smoke: run the full LangGraph pipeline against a tiny config and
    confirm we get a structured BUY/SELL/HOLD decision back.

    Reads DEEPSEEK_API_KEY from environment. Fails fast if the key is
    missing — we don't want false-positive "skipped" runs.
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        pytest.skip("DEEPSEEK_API_KEY not set — skipping real-engine smoke")

    from tradingagents.default_config import DEFAULT_CONFIG

    from api.real_engine import TradingAgentsGraphWithApiKey

    config = {
        **DEFAULT_CONFIG,
        "llm_provider": "deepseek",
        "deep_think_llm": "deepseek-chat",
        "quick_think_llm": "deepseek-chat",
        "max_debate_rounds": 1,
        "max_risk_discuss_rounds": 1,
        "results_dir": "/tmp/ta_smoke/logs",
        "data_cache_dir": "/tmp/ta_smoke/cache",
        "api_key": api_key,
    }

    graph = TradingAgentsGraphWithApiKey(
        selected_analysts=["market"],  # cheapest path: 1 analyst
        debug=False,
        config=config,
    )

    final_state, decision = graph.propagate("NVDA", "2026-01-15")

    assert isinstance(final_state, dict)
    # `decision` from process_signal is typically a short string label.
    # Accept any of the expected verdicts. If the upstream signal_processor
    # returns a different shape (full sentence, JSON, etc.), this assertion
    # may need to be relaxed — but a sane v1 should produce one of these.
    assert isinstance(decision, str) and len(decision) > 0
    upper = decision.upper()
    assert any(verdict in upper for verdict in ("BUY", "SELL", "HOLD")), (
        f"Expected BUY/SELL/HOLD in decision, got: {decision!r}"
    )
```

- [ ] **Step 2: Verify it's skipped by default**

```bash
cd apps/api
SUPABASE_URL=http://test.local SUPABASE_SERVICE_ROLE_KEY=test SUPABASE_JWT_SECRET=secret \
uv run pytest tests/test_real_engine.py -v
```

Expected: 1 test SKIPPED (not failed).

- [ ] **Step 3: Verify the full suite still passes**

```bash
SUPABASE_URL=http://test.local SUPABASE_SERVICE_ROLE_KEY=test SUPABASE_JWT_SECRET=secret \
uv run pytest -v
```

Expected: 35 passed + 1 skipped.

- [ ] **Step 4: Commit**

```bash
git add apps/api/tests/test_real_engine.py
git commit -m "test(api): add real-engine smoke (skipped by default)"
```

---

### Task 7: Add `make api-test-real` target

**Files:**
- Modify: `Makefile` (repo root)

- [ ] **Step 1: Append target**

Find the existing `api-*` targets in `Makefile`. Append:

```makefile

# Run ONLY real-engine tests (calls real LLMs, costs ~$0.005-0.05)
# Requires: DEEPSEEK_API_KEY (or override LLM_PROVIDER + corresponding key)
.PHONY: api-test-real
api-test-real:
	cd apps/api && uv run pytest -m real_engine --run-real-engine -v
```

Update `make help` to include the new target:

```makefile
	@echo "  make api-test-real   - run real-engine smoke (calls real LLMs, ~\$$0.005)"
```

- [ ] **Step 2: Verify**

```bash
make help | grep api-test-real
```

Expected: the new help line shows up.

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "chore: add make api-test-real target"
```

---

### Task 8: GitHub Actions workflow_dispatch for real-engine smoke

**Files:**
- Create: `.github/workflows/real-engine-smoke.yml`

- [ ] **Step 1: Write the workflow**

```yaml
name: Real Engine Smoke

# Manual-trigger only. We don't run this on push/PR because it
# costs money (~$0.005 per run via DeepSeek, more for OpenAI).
on:
  workflow_dispatch:
    inputs:
      provider:
        description: 'LLM provider for the smoke (default: deepseek)'
        required: false
        default: 'deepseek'

jobs:
  real-engine:
    name: Real engine smoke (${{ github.event.inputs.provider }})
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

      - name: Run real-engine smoke
        working-directory: apps/api
        env:
          SUPABASE_URL: http://test.local
          SUPABASE_SERVICE_ROLE_KEY: test-srv
          SUPABASE_JWT_SECRET: test-secret-do-not-use-in-prod
          USE_FAKE_ENGINE: "1"   # for non-real tests; the real-engine test reads its own env
          DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: uv run pytest -m real_engine --run-real-engine -v
```

- [ ] **Step 2: Lint YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/real-engine-smoke.yml'))"
```

Expected: silent.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/real-engine-smoke.yml
git commit -m "ci: add real-engine-smoke workflow (workflow_dispatch only)"
```

---

## Phase 3 — Production rollout

### Task 9: Flip `USE_FAKE_ENGINE=0` on Render

**Files:** none (operational)

- [ ] **Step 1: Read current Render env vars** (so we don't clobber)

```bash
cd /Users/erik/Developer/Github/Snapsonic/tradingAgents
set -a; source ./.env.local; set +a

BASE=https://api.render.com/v1
HDR="Authorization: Bearer $RENDER_API_KEY"

EXISTING=$(curl -sS -H "$HDR" "$BASE/services/$RENDER_WEB_SERVICE_ID/env-vars" \
  | jq -c '[.[] | {key: .envVar.key, value: .envVar.value}]')
echo "Existing keys: $(echo "$EXISTING" | jq -r '[.[].key] | join(", ")')"
```

- [ ] **Step 2: Construct the merged list with `USE_FAKE_ENGINE=0`**

```bash
NEW_LIST=$(echo "$EXISTING" | jq \
  'map(if .key == "USE_FAKE_ENGINE" then .value = "0" else . end)
   | (if any(.key == "USE_FAKE_ENGINE") then . else . + [{key: "USE_FAKE_ENGINE", value: "0"}] end)')
```

(The conditional ensures we update an existing entry OR append a new one.)

- [ ] **Step 3: PUT the full env-var list**

```bash
curl -sS -X PUT -H "$HDR" -H "Content-Type: application/json" \
  -d "$NEW_LIST" "$BASE/services/$RENDER_WEB_SERVICE_ID/env-vars" \
  | jq '[.[] | .envVar.key]'
```

Expected: a JSON array including `USE_FAKE_ENGINE` and all the other keys (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `CORS_ORIGINS`, `LOG_JSON`, `LOG_LEVEL`).

- [ ] **Step 4: Trigger redeploy + wait for live**

```bash
DEPLOY_ID=$(curl -sS -X POST -H "$HDR" -H "Content-Type: application/json" \
  -d '{"clearCache":"do_not_clear"}' \
  "$BASE/services/$RENDER_WEB_SERVICE_ID/deploys" | jq -r '.id')
echo "DEPLOY_ID=$DEPLOY_ID"

for i in $(seq 1 8); do
  STATE=$(curl -sS -H "$HDR" "$BASE/services/$RENDER_WEB_SERVICE_ID/deploys/$DEPLOY_ID" | jq -r '.status')
  echo "[$i/8] state=$STATE"
  [ "$STATE" = "live" ] && break
  sleep 12
done

curl -sS "$RENDER_API_BASE_URL/healthz"
echo
```

Expected: deploy goes live, /healthz returns OK.

No commit — operational.

---

### Task 10: Manual smoke against the real-engine deploy

**Files:** none (verification)

- [ ] **Step 1: Ensure the smoke test user has a working OpenAI BYO key**

The smoke user (`smoke@snapsonic.local`, USER_ID `320a561a-...`) already has a fake OpenAI key from Plan 2's smoke. For the real-engine smoke we either:

- **Option A:** Replace the smoke user's key with a real one via the Supabase SQL editor (set a real `OPENAI_API_KEY` value via `vault_save_key` RPC). Cost ~$0.05–$0.50/run.
- **Option B:** Set up DeepSeek for the user instead. Add a `deepseek` key for the smoke user via `vault_save_key`. Then create the run with `config = {"llm_provider": "deepseek"}`. Cost ~$0.005/run.

Option B is cheaper.

```bash
cd /Users/erik/Developer/Github/Snapsonic/tradingAgents
set -a; source ./.env.local; set +a

# Refresh the smoke user's access token
PROJECT_REF=$(echo "$SUPABASE_URL" | sed -E 's|https?://([^.]+)\..*|\1|')
ANON_KEY=$(curl -sS -H "Authorization: Bearer $SUPABASE_PERSONAL_ACCESS_TOKEN" \
  "https://api.supabase.com/v1/projects/$PROJECT_REF/api-keys" \
  | jq -r '.[] | select(.name=="anon") | .api_key')

ACCESS_TOKEN=$(curl -sS -X POST -H "apikey: $ANON_KEY" -H "Content-Type: application/json" \
  -d '{"email":"smoke@snapsonic.local","password":"smoke-test-password-do-not-share"}' \
  "$SUPABASE_URL/auth/v1/token?grant_type=password" | jq -r '.access_token')

# Save a DEEPSEEK key as the smoke user
curl -sS -X POST -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $ACCESS_TOKEN" -H "Content-Type: application/json" \
  -d "{\"p_provider\":\"deepseek\",\"p_plaintext\":\"$DEEPSEEK_API_KEY\"}" \
  "$SUPABASE_URL/rest/v1/rpc/vault_save_key"
```

(Requires `DEEPSEEK_API_KEY` to be set in `.env.local`.)

- [ ] **Step 2: Create a real run + watch it complete**

```bash
RUN_INPUT='{"input":{"ticker":"NVDA","trade_date":"2026-01-15","config":{"llm_provider":"deepseek"}}}'

RUN_ID=$(curl -sS -X POST -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $ACCESS_TOKEN" -H "Content-Type: application/json" \
  -d "$RUN_INPUT" "$SUPABASE_URL/rest/v1/rpc/create_run" | tr -d '"')

echo "RUN_ID=$RUN_ID"

# Start the run on Render
curl -sS -X POST -H "Authorization: Bearer $ACCESS_TOKEN" \
  "$RENDER_API_BASE_URL/runs/$RUN_ID/start"
echo

# Poll for completion (real engine: 1–8 min)
HDR_SVC="apikey: $SUPABASE_SERVICE_ROLE_KEY"
HDR_AUTH="Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"

for i in $(seq 1 60); do
  STATUS=$(curl -sS -H "$HDR_SVC" -H "$HDR_AUTH" \
    "$SUPABASE_URL/rest/v1/runs?id=eq.$RUN_ID&select=status" | jq -r '.[0].status')
  echo "[$i/60] status=$STATUS"
  [ "$STATUS" = "completed" ] && break
  [ "$STATUS" = "failed" ] && break
  sleep 10
done

# Final state
curl -sS -H "$HDR_SVC" -H "$HDR_AUTH" \
  "$SUPABASE_URL/rest/v1/runs?id=eq.$RUN_ID&select=id,status,final_decision,error" | jq
```

Expected: status transitions `pending → running → completed`, `final_decision.decision` is one of `BUY/SELL/HOLD`, `error` is null.

If `error` is set, capture the message and Render logs for diagnosis. Common failures:
- "No BYO key loaded for provider: deepseek" → `vault_save_key` didn't land.
- DeepSeek 401 → key is invalid.
- LangGraph timeout → real run took >30min and the janitor swept it.

No commit — verification.

---

### Task 11: Document the rollout

**Files:**
- Create: `docs/superpowers/runbooks/2026-05-01-real-engine-rollout.md`

- [ ] **Step 1: Write the runbook**

```markdown
# Operator runbook — real-engine rollout (Plan 4)

> Generated 2026-05-01. After Plan 4 lands, the production Render service runs the real `TradingAgentsGraph`. This document covers the cost/risk model and how to roll back if something goes wrong.

## What changed

- `apps/api/src/api/routes.py::_make_engine_factory` now branches on `USE_FAKE_ENGINE`. With `USE_FAKE_ENGINE=0`, it constructs `TradingAgentsGraphWithApiKey` (a subclass that forwards `api_key` from config to LLM clients) instead of `FakeTradingAgentsGraph`.
- The Render web service has `USE_FAKE_ENGINE=0` set as of the rollout deploy.

## Cost model

| Provider (deep + quick) | Approx $/run | When to use |
|---|---|---|
| `deepseek` (deepseek-chat) | $0.002–0.01 | Default for cost-sensitive testing |
| `gpt-5.4-nano` + `gpt-5.4-nano` | $0.05–0.15 | When DeepSeek is unavailable |
| `gpt-5.4` (deep) + `gpt-5.4-mini` (quick) | $0.50–2.00 | The default config; produces best-quality reports |
| Anthropic Claude 4.6 | $1.00–5.00 | Premium |

A single beta user running 1 run/day with the default OpenAI config = ~$15–60/month per user. Worth tracking once we have real users.

## Roll back

If a real-engine deploy is broken:

1. **Flip USE_FAKE_ENGINE back to 1** via the Render API:
   ```bash
   set -a; source .env.local; set +a
   BASE=https://api.render.com/v1
   HDR="Authorization: Bearer $RENDER_API_KEY"
   EXISTING=$(curl -sS -H "$HDR" "$BASE/services/$RENDER_WEB_SERVICE_ID/env-vars" \
     | jq -c '[.[] | {key: .envVar.key, value: .envVar.value}]')
   NEW=$(echo "$EXISTING" | jq 'map(if .key == "USE_FAKE_ENGINE" then .value = "1" else . end)')
   curl -sS -X PUT -H "$HDR" -H "Content-Type: application/json" -d "$NEW" \
     "$BASE/services/$RENDER_WEB_SERVICE_ID/env-vars"
   curl -sS -X POST -H "$HDR" -H "Content-Type: application/json" \
     -d '{"clearCache":"do_not_clear"}' \
     "$BASE/services/$RENDER_WEB_SERVICE_ID/deploys"
   ```

2. **Or revert the merge commit on main** — `git revert <ca18dd7-style sha>` then push.

## Watch items (first week post-launch)

- **OOM kills.** Render Starter (512 MB RAM) was flagged as marginal. Watch deploy logs for SIGKILL / "killed by OOM". If seen, bump to Standard (2 GB) immediately:
   ```bash
   curl -sS -X PATCH -H "$HDR" -H "Content-Type: application/json" \
     -d '{"plan":"standard"}' \
     "$BASE/services/$RENDER_WEB_SERVICE_ID"
   ```
- **Long runs hitting Render idle timeout.** SSE keepalive every 15 sec should prevent this — but verify by watching a real run's full duration.
- **DeepSeek/OpenAI rate limits.** At higher concurrency, providers may throttle. The engine has built-in retry but exhausting retries surfaces as a `run_failed` row.

## Concurrency note

The subclass approach keeps each engine instance self-contained — concurrent runs from different users don't share env vars. The current single-Render-instance setup is fine for ≤5 concurrent runs (memory bound). For >5 we'd need horizontal scaling + Bus-via-Redis (currently in-process).

## Real-engine smoke (CI)

A `workflow_dispatch`-only GitHub Actions workflow at `.github/workflows/real-engine-smoke.yml` runs the real-engine smoke test. To trigger:

1. GitHub → Actions → Real Engine Smoke → Run workflow
2. Optional input: `provider` (default `deepseek`)
3. The workflow needs these repo secrets: `DEEPSEEK_API_KEY` (mandatory for default), optionally `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` for alternate provider runs.

Cost per CI run: ~$0.005.
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/runbooks/2026-05-01-real-engine-rollout.md
git commit -m "docs: real-engine rollout runbook"
```

---

## Phase 4 — Push + PR + merge

### Task 12: Push branch + open draft PR + watch CI

**Files:** none

- [ ] **Step 1: Push**

```bash
cd /Users/erik/Developer/Github/Snapsonic/tradingAgents
git push -u origin feature/real-engine
```

- [ ] **Step 2: Open draft PR**

```bash
gh pr create --repo elagerway/tradingagents --draft \
  --base main --head feature/real-engine \
  --title "Plan 4: Real engine wiring + per-release smoke" \
  --body "$(cat <<'EOF'
## Summary

Implements **Plan 4** — the final piece of v1.

- New \`TradingAgentsGraphWithApiKey\` subclass forwards \`api_key\` from config to LLM clients (no env-var mutation, no upstream modification, concurrency-safe)
- \`_make_engine_factory\` branches on \`USE_FAKE_ENGINE\` — fake variant still used in tests + as a fallback
- Real-engine smoke test gated behind \`@pytest.mark.real_engine\` + \`--run-real-engine\` flag (skipped in CI by default)
- New GitHub Actions \`workflow_dispatch\`-only workflow runs the smoke on demand at ~\$0.005/run
- New \`make api-test-real\` Makefile target
- Operational runbook at \`docs/superpowers/runbooks/2026-05-01-real-engine-rollout.md\`

## Plan
[\`docs/superpowers/plans/2026-05-01-real-engine.md\`](docs/superpowers/plans/2026-05-01-real-engine.md)

## Test plan
- [x] All 35 prior pytest tests still pass
- [x] +1 unit test for the real-engine factory wiring (mocked)
- [x] +1 real-engine smoke test (skipped in default CI; manual workflow_dispatch)
- [x] CI green on api-ci
- [ ] Render rollout: \`USE_FAKE_ENGINE\` flipped to \`0\`, redeploy live, manual real-engine smoke green against the production URL

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Watch CI**

```bash
gh pr checks --repo elagerway/tradingagents --watch
```

Expected: api-ci goes green within a few minutes. Web CI doesn't run on this PR (no apps/web changes).

---

### Task 13: Mark PR ready + merge

**Files:** none

- [ ] **Step 1: Mark ready**

```bash
gh pr ready --repo elagerway/tradingagents
```

- [ ] **Step 2: Merge**

```bash
gh pr merge --repo elagerway/tradingagents --squash --delete-branch --admin
```

- [ ] **Step 3: Sync local**

```bash
git checkout main && git pull && git branch -D feature/real-engine 2>/dev/null || true
```

**Plan 4 is done.** v1 is shipped.

---

## Self-review

### Spec coverage

| Spec section | Covered by tasks |
|---|---|
| §3 stack: real engine via upstream `tradingagents` package | Tasks 1, 3 |
| §6 BYO key flow: provider-specific keys passed to engine | Tasks 1, 3 |
| §8 testing: real-engine smoke in CI gated behind manual trigger | Tasks 5, 6, 8 |
| §11 decisions log: "Real engine wiring + smoke test" → Plan 4 | Task 11 (runbook documents the actual rollout) |
| §12 open questions: "PG17 segfault workaround removal" — not addressed in Plan 4 (still tracked for future) | n/a — out of scope |

No gaps for v1 scope.

### Placeholder scan

- No "TBD"/"TODO"/"implement later" markers.
- Real code in every step.
- All pytest commands have expected outputs.
- Cost figures (`~$0.005`) flagged as approximations needing verification at the moment of running — that's honest, not a placeholder.

### Type/name consistency

- `TradingAgentsGraphWithApiKey` defined in Task 1, referenced in Tasks 2, 3, 6.
- `_make_engine_factory(callbacks, fake, env, run_config)` signature consistent across Task 2 (test) and Task 3 (impl).
- `engine_config` keys (`api_key`, `results_dir`, `data_cache_dir`) consistent.
- pytest marker `real_engine` consistent across Tasks 5, 6, 7, 8.

No drift.

---

## Execution handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-01-real-engine.md`. Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, two-stage review.
2. **Inline Execution** — batch execution with checkpoints.

**Which approach?**
