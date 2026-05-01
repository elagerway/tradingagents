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
