# Operator runbook — per-user memory rollout (Plan 5)

## What changed

- New `user_memory` table in Supabase (RLS-scoped per-user)
- New `SupabaseMemoryLog` Python class (subclass of upstream `TradingMemoryLog`) replaces local-file storage
- New `TradingAgentsGraphWithUserContext` engine subclass injects per-user memory
- After each successful run, if `trade_date` is ≥7 days in the past, the worker computes realized return via yfinance + generates a reflection via `Reflector.reflect_on_final_decision` + resolves the pending entry — all synchronously, before sending the terminal SSE event
- Engine's Portfolio Manager prompt now sees the user's prior decisions + reflections (cross-ticker lessons + same-ticker history)

## Privacy posture

Per-user RLS: a user can read only their own `user_memory` rows. Writes go through service-role (Render container's `SUPABASE_SERVICE_ROLE_KEY`).

The upstream's single-tenant memory file (`~/.tradingagents/memory/trading_memory.md`) is no longer touched in production. (The default constructor still creates it as an empty file inside the container — harmless, never read.)

## Watch items (first week)

- **Reflection cost.** Each backdated run now has 1 extra LLM call (the reflection). At DeepSeek prices ~$0.001/call. Negligible.
- **yfinance failures.** The compute step is best-effort — failures log a warning but don't fail the run. Watch `outcome ingestion failed` log lines.
- **Memory growth.** No rotation in v1. After 1000 entries per user, `load_entries()` becomes slow. Add a `LIMIT 50` clause if it bites.

## Roll back

Revert the merge commit. The engine falls back to the file-based memory; users see no error, just no memory persistence across container restarts.

## How users see it

- A user runs NVDA today, decision is BUY, gets stored as resolved=false (since trade_date is today).
- A week later the user runs NVDA again. The engine's `_resolve_pending_entries` runs at the start of `propagate()`, finds the pending entry, computes the realized return via yfinance, generates the reflection, marks resolved=true.
- The Portfolio Manager prompt for THIS run now sees the resolved entry: "Your previous BUY on NVDA had +4.2% raw / +2.1% alpha. Reflection: momentum thesis held."
- For backdated runs (e.g., user runs NVDA on 2024-05-10 today), the resolution happens synchronously at the end of THAT run, so the next run sees it immediately.
