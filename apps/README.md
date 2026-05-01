# Hedgentic AI — application code

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
