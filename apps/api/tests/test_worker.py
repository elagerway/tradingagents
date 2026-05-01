"""Tests for the async worker that runs an engine instance and feeds the bus."""

import asyncio

import pytest

from api.bus import SENTINEL, Bus
from api.engine import SSEPublisher
from api.fakes.fake_engine import FakeTradingAgentsGraph
from api.worker import run_engine


async def test_run_engine_completes_and_closes_bus():
    from datetime import date

    bus = Bus()
    publisher = SSEPublisher(bus=bus, run_id="r-happy", verbose=False)

    def make_engine() -> FakeTradingAgentsGraph:
        return FakeTradingAgentsGraph(callbacks=[publisher])

    queue = bus.subscribe()
    final_state, decision = await run_engine(
        make_engine=make_engine,
        ticker="NVDA",
        trade_date=date.today().isoformat(),
        bus=bus,
    )

    assert decision == "BUY"
    assert final_state["ticker"] == "NVDA"

    # Drain the queue until SENTINEL
    seen_types = []
    while True:
        event = await asyncio.wait_for(queue.get(), timeout=0.5)
        if event is SENTINEL:
            break
        seen_types.append(event.data["type"])
    assert "run_completed" in seen_types
    assert bus.closed


async def test_run_engine_failure_closes_bus_and_publishes_error():
    bus = Bus()
    publisher = SSEPublisher(bus=bus, run_id="r-fail", verbose=False)

    def make_engine() -> FakeTradingAgentsGraph:
        return FakeTradingAgentsGraph(callbacks=[publisher], raise_at="trader")

    queue = bus.subscribe()
    with pytest.raises(RuntimeError, match="trader"):
        await run_engine(
            make_engine=make_engine,
            ticker="NVDA",
            trade_date="2026-01-15",
            bus=bus,
        )

    seen_types = []
    while True:
        event = await asyncio.wait_for(queue.get(), timeout=0.5)
        if event is SENTINEL:
            break
        seen_types.append(event.data["type"])
    assert "run_failed" in seen_types
    assert bus.closed


async def test_run_engine_resolves_backdated_run_outcome():
    """After a successful run with trade_date in the past, the worker
    computes the realized return + reflection and resolves the pending
    memory entry."""
    from datetime import date, timedelta
    from unittest.mock import MagicMock, patch

    bus = Bus()
    publisher = SSEPublisher(bus=bus, run_id="r-backdated", verbose=False)

    fake_engine = FakeTradingAgentsGraph(callbacks=[publisher])
    # Attach a mock memory_log
    fake_engine.memory_log = MagicMock()

    def make_engine():
        return fake_engine

    backdated = (date.today() - timedelta(days=14)).isoformat()

    with (
        patch("api.outcomes.compute_realized_return") as mock_compute,
        patch("api.worker._reflect") as mock_reflect,
    ):
        mock_compute.return_value = (0.04, 0.02, 5)
        mock_reflect.return_value = "BUY was right; momentum thesis held."

        await run_engine(
            make_engine=make_engine,
            ticker="NVDA",
            trade_date=backdated,
            bus=bus,
        )

    fake_engine.memory_log.update_with_outcome.assert_called_once()
    kwargs = fake_engine.memory_log.update_with_outcome.call_args.kwargs
    assert kwargs["ticker"] == "NVDA"
    assert kwargs["raw_return"] == 0.04
    assert kwargs["alpha_return"] == 0.02
    assert kwargs["holding_days"] == 5
    assert "BUY was right" in kwargs["reflection"]
