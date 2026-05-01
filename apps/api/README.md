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
