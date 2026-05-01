"""Async worker that drives the (sync) LangGraph engine on a thread and
feeds events to a Bus. On completion, publishes a `run_completed` event
and closes the bus.

For backdated runs (trade_date >= 7 days in the past), also computes the
realized return via yfinance + generates a reflection via the engine's
Reflector + marks the corresponding pending memory entry as resolved —
all synchronously before the terminal SSE event."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date
from typing import Any

import api.outcomes as outcomes
from api.bus import Bus
from api.logging import get_logger

logger = get_logger(__name__)


def _reflect(engine, decision: str, raw: float, alpha: float) -> str:
    """Generate the reflection paragraph using the engine's reflector
    (which internally uses the engine's quick_think_llm).

    Module-level so tests can patch without touching engine internals.
    """
    return engine.reflector.reflect_on_final_decision(decision, raw, alpha)


async def run_engine(
    *,
    make_engine: Callable[[], Any],
    ticker: str,
    trade_date: str,
    bus: Bus,
) -> tuple[dict[str, Any], str]:
    """Run engine on a thread; on success, resolve backdated outcomes."""
    loop = asyncio.get_running_loop()

    engine_holder: dict[str, Any] = {}

    def _publish(event: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(bus.publish, event)

    def _run_sync() -> tuple[dict[str, Any], str]:
        engine = make_engine()
        engine_holder["engine"] = engine
        return engine.propagate(ticker, trade_date)

    try:
        final_state, decision = await asyncio.to_thread(_run_sync)
    except Exception as exc:
        logger.exception("engine run failed", ticker=ticker, trade_date=trade_date)
        bus.publish({"type": "run_failed", "error": str(exc)[:1000]})
        bus.close()
        raise

    # Resolve backdated outcomes (best-effort).
    engine = engine_holder.get("engine")
    if engine is not None and getattr(engine, "memory_log", None) is not None:
        try:
            td = date.fromisoformat(trade_date)
            if (date.today() - td).days >= 7:
                outcome = await asyncio.to_thread(
                    outcomes.compute_realized_return,
                    ticker=ticker,
                    trade_date=td,
                )
                if outcome:
                    raw, alpha, holding = outcome
                    reflection = await asyncio.to_thread(
                        _reflect,
                        engine,
                        final_state.get("final_trade_decision", ""),
                        raw,
                        alpha,
                    )
                    await asyncio.to_thread(
                        engine.memory_log.update_with_outcome,
                        ticker=ticker,
                        trade_date=trade_date,
                        raw_return=raw,
                        alpha_return=alpha,
                        holding_days=holding,
                        reflection=reflection,
                    )
                    bus.publish(
                        {
                            "type": "outcome_resolved",
                            "raw_return": raw,
                            "alpha": alpha,
                            "holding_days": holding,
                        }
                    )
        except Exception as exc:
            logger.warning(
                "outcome ingestion failed",
                ticker=ticker,
                trade_date=trade_date,
                error=str(exc)[:200],
            )

    bus.publish({"type": "run_completed", "decision": decision})
    bus.close()
    return final_state, decision
