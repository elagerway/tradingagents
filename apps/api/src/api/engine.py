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


# LangGraph node names → our snake_case agent keys used by the web UI.
# The engine's setup.py adds nodes with display-cased names like
# "Market Analyst" / "Research Manager"; the web AGENTS array uses
# "market_analyst" / "research_manager". Normalize at publish time.
_NODE_TO_AGENT_KEY: dict[str, str] = {
    "Market Analyst": "market_analyst",
    "Social Analyst": "social_analyst",
    "News Analyst": "news_analyst",
    "Fundamentals Analyst": "fundamentals_analyst",
    "Bull Researcher": "bull_researcher",
    "Bear Researcher": "bear_researcher",
    "Research Manager": "research_manager",
    "Trader": "trader",
    "Aggressive Analyst": "aggressive_analyst",
    "Neutral Analyst": "neutral_analyst",
    "Conservative Analyst": "conservative_analyst",
    "Portfolio Manager": "portfolio_manager",
}

# Agents the web UI renders as cards. Other LangGraph nodes (router chains,
# clear_messages helpers, the top-level graph) emit events that we suppress
# so the timeline doesn't fill up with noise the user can't act on.
_RENDERED_AGENTS: frozenset[str] = frozenset(_NODE_TO_AGENT_KEY.values())


def _agent_name(name: str | None, serialized: dict[str, Any] | None) -> str | None:
    raw = name or (serialized or {}).get("name") or ""
    if not raw:
        return None
    if raw in _NODE_TO_AGENT_KEY:
        return _NODE_TO_AGENT_KEY[raw]
    # Fall back to slugifying — keeps the event readable when the engine
    # adds a new node we haven't mapped yet.
    return raw.lower().replace(" ", "_")


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

    def on_chain_start(
        self, serialized, inputs, *, run_id: UUID, name: str | None = None, **kwargs
    ) -> None:
        agent = _agent_name(name, serialized)
        if agent not in _RENDERED_AGENTS:
            return
        self.bus.publish({"type": "agent_started", "agent": agent})

    def on_chain_end(self, outputs, *, run_id: UUID, name: str | None = None, **kwargs) -> None:
        agent = _agent_name(name, None)
        if agent not in _RENDERED_AGENTS:
            return
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
        self.bus.publish(
            {
                "type": "agent_completed",
                "agent": agent,
                "summary": _truncate(summary_text),
            }
        )

    def on_chain_error(self, error, *, run_id: UUID, name: str | None = None, **kwargs) -> None:
        agent = _agent_name(name, None)
        if agent not in _RENDERED_AGENTS:
            return
        self.bus.publish(
            {
                "type": "agent_error",
                "agent": agent,
                "error": _truncate(str(error)),
            }
        )

    # --- LLM-level (heartbeat) ------------------------------------------

    def on_chat_model_start(
        self, serialized, messages, *, run_id: UUID, name: str | None = None, **kwargs
    ) -> None:
        # LLM invocations don't carry a node name from LangGraph, so we'd
        # have to publish agent_thinking with an empty/unknown agent which
        # the client can't route. on_chain_start already signals "agent
        # active" for each rendered node — that's enough.
        return

    # --- tool events (verbose only) -------------------------------------

    def on_tool_start(self, serialized, input_str, *, run_id: UUID, **kwargs) -> None:
        if not self.verbose:
            return
        tool = (serialized or {}).get("name", "unknown")
        self.bus.publish(
            {"type": "tool_called", "tool": tool, "args": _truncate(str(input_str), 200)}
        )

    def on_tool_end(self, output, *, run_id: UUID, **kwargs) -> None:
        if not self.verbose:
            return
        self.bus.publish({"type": "tool_result", "result": _truncate(str(output), 200)})
