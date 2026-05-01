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

2. **Or revert the merge commit on main** — `git revert <merge-commit-sha>` then push.

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
