"""Subclass of TradingAgentsGraph that forwards `api_key` from config to LLM clients.

The upstream engine reads keys from os.environ by default. Setting env vars
per-call is unsafe under concurrency (process-global state). The subclass
pattern keeps each engine instance self-contained — its LLM clients are
constructed at __init__ time with the api_key baked in.

We don't modify the upstream package; we subclass it in our wrapper.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from tradingagents.graph.trading_graph import TradingAgentsGraph

from api.memory_log import SupabaseMemoryLog


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


class TradingAgentsGraphWithUserContext(TradingAgentsGraphWithApiKey):
    """Engine that replaces the local-file memory_log with a per-user
    Supabase-backed one and wires our callbacks into graph.invoke so the
    SSEPublisher receives per-node lifecycle events.

    The upstream's __init__ instantiates `self.memory_log = TradingMemoryLog(...)`.
    We let super().__init__ run normally, then reassign `self.memory_log` to
    our Supabase-backed subclass before any propagate() call sees it.
    """

    def __init__(
        self,
        *args,
        user_id: UUID,
        run_id: UUID | None,
        supabase_url: str,
        service_role_key: str,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.memory_log = SupabaseMemoryLog(
            config=self.config,
            user_id=user_id,
            run_id=run_id,
            supabase_url=supabase_url,
            service_role_key=service_role_key,
        )

    def propagate(self, ticker: str, trade_date: str):
        """Inject our callbacks into the propagator's graph args so that
        compiled-graph node lifecycle events (on_chain_start/end with the
        node's actual name like "Market Analyst") flow into the SSEPublisher.

        Without this, callbacks attach only to the LLM clients (via the
        upstream's `__init__`) and on_chain_start fires with name=None, so
        the publisher can't tell which agent is running.
        """
        if not self.callbacks:
            return super().propagate(ticker, trade_date)

        original_get_args = self.propagator.get_graph_args
        cbs = self.callbacks

        def get_args_with_callbacks(callbacks=None):
            merged = list(callbacks or []) + list(cbs)
            return original_get_args(callbacks=merged)

        self.propagator.get_graph_args = get_args_with_callbacks
        try:
            return super().propagate(ticker, trade_date)
        finally:
            self.propagator.get_graph_args = original_get_args
