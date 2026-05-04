# v1.0.1 Hotfix Sweep — 2026-05-04

First-day-of-real-use bug bash on Hedgentic AI. Run end-to-end, hit
real failures, ship fixes. All shipped to main and live on Vercel +
Render.

## What landed

| Commit | Subject | Why |
|---|---|---|
| `feat(web)` 822e4e8 | Block New Run when no API keys, modal directing to /settings | Without keys, `POST /start` rejected and ran got stranded as `pending` with no UX feedback. |
| `fix(api)` 235f8c7 | Pick provider-specific model defaults instead of OpenAI's | Engine inherited `gpt-5.4-mini` for every provider. DeepSeek 400'd on a real run. New `_PROVIDER_DEFAULT_MODELS` table + `dashscope→qwen` / `zhipu→glm` translation. |
| `feat(web)` 48abb49 | OpenRouter model picker modal on New Run | OpenRouter requires `provider/model` strings — no sensible default. Modal asks for deep + quick on submit. |
| `feat(api)` 0949cd5 | Per-user Alpha Vantage key + flip news_data to AV | Engine reads `ALPHA_VANTAGE_API_KEY` from env. Replaced with a ContextVar (asyncio-task-scoped, `asyncio.to_thread`-safe) so concurrent users don't leak each other's keys. `data_vendors.news_data = "alpha_vantage,yfinance"` when AV present. |
| `fix(api)` 8090e13 | Persist SSE event log on `finalize_run` + `fail_run` | `events_for_persist = []` was never appended to. Reading `bus.snapshot()` instead. Buffer 200 → 1000. |
| `fix` d9c40d2 | Stream events live when a run flips pending→running | Two bugs: web didn't `router.refresh()` after `POST /start`, and `Bus.replay_since(None)` returned `[]` instead of the full buffer. |
| `fix(api)` d053f37 | Wire SSE callbacks into LangGraph node lifecycle | Callbacks were attached to LLM clients only — `on_chain_start` never fired with node names. Patched `propagator.get_graph_args` from inside `TradingAgentsGraphWithUserContext.propagate`. Names normalized to snake_case web AGENTS keys. |
| `fix(api)` e79d648 | Correlate chain start/end via `run_id`, not name | LangGraph quirk: `on_chain_start` carries `name="Market Analyst"`, but `on_chain_end` fires with `name=None`. Track `run_id → agent` in `self._active`, pop on end. |
| `feat(web)` c8548a2 | Render timestamps in America/Vancouver | `trade_date` defaulted to UTC date — at 5pm PT, that was tomorrow. Centralized `vancouverDateString` / `vancouverDateTimeString` helpers. |

## Verified end-to-end

Ran `TradingAgentsGraphWithApiKey.propagate("NVDA", "2026-05-02")` locally
with single analyst, single debate round on DeepSeek. Captured 50 events:

- 12 × `agent_started`
- 12 × `agent_completed` (paired by `run_id`)
- 13 × `tool_called`
- 13 × `tool_result`
- All agents normalized to `market_analyst` / `bull_researcher` / etc.
- No leaked names (no `NormalizedChatOpenAI`, no display-cased names)
- Decision: `Hold`

## Architectural notes worth preserving

1. **Render deploys kill in-flight runs.** The bus + worker live in the
   API process; on container swap, `runs.status` stays `running` until the
   janitor catches it on its sweep. Add a SIGTERM handler that calls
   `fail_run(error="container shutting down")` for any active buses
   before exit — would clean up the DB state immediately. Two-line PR.

2. **Hedgentic Supabase project uses ES256 (asymmetric) JWTs.** Can't
   mint test tokens for the deployed API without the private key — local
   testing uses `SUPABASE_JWT_SECRET` (HS256) instead. Means E2E
   verification against prod has to come through the web UI or a real
   user session.

3. **LangGraph `on_chain_end` fires with `name=None`.** Always correlate
   start/end events by `run_id` (UUID), not by inferred names. Tags carry
   `graph:step:N` for top-level node events vs `seq:step:N` for inner
   runnables — useful as a secondary filter if needed.

## Followups (not done today)

- Graceful shutdown handler that fails active runs on SIGTERM
- Cards for the 5 non-rendered agents (Bull/Bear Researcher, Aggressive/Neutral/Conservative Analyst); their events are filtered out today
- Render auto-revalidate so the runs-list "completed" badge updates without manual refresh
- Catalog the actual current model names per provider — DeepSeek's API claims `deepseek-v4-pro`/`deepseek-v4-flash` are the supported names but `deepseek-chat`/`deepseek-reasoner` worked fine in practice
