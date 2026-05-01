"""Async worker that drives the (sync) LangGraph engine on a thread and
feeds events to a Bus. On completion, publishes a `run_completed` event
and closes the bus."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from api.bus import Bus
from api.logging import get_logger

logger = get_logger(__name__)


async def run_engine(
    *,
    make_engine: Callable[[], Any],
    ticker: str,
    trade_date: str,
    bus: Bus,
) -> tuple[dict[str, Any], str]:
    """Spawn the engine on a thread; publish `run_completed` and close bus
    when it finishes successfully. Errors propagate (caller decides how to
    write status='failed' in Supabase)."""
    loop = asyncio.get_running_loop()

    def _publish(event: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(bus.publish, event)

    def _run_sync() -> tuple[dict[str, Any], str]:
        engine = make_engine()
        return engine.propagate(ticker, trade_date)

    try:
        final_state, decision = await asyncio.to_thread(_run_sync)
    except Exception as exc:
        logger.exception("engine run failed", ticker=ticker, trade_date=trade_date)
        # We're back on the event loop thread here, so publish directly
        bus.publish({"type": "run_failed", "error": str(exc)[:1000]})
        bus.close()
        raise

    bus.publish({"type": "run_completed", "decision": decision})
    bus.close()
    return final_state, decision
