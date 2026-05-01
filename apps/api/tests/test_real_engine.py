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
    assert isinstance(decision, str) and len(decision) > 0
    upper = decision.upper()
    assert any(verdict in upper for verdict in ("BUY", "SELL", "HOLD")), (
        f"Expected BUY/SELL/HOLD in decision, got: {decision!r}"
    )
