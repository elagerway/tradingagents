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
