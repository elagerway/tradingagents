"""Tests for the async worker that runs an engine instance and feeds the bus."""
import asyncio

import pytest

from api.bus import Bus, SENTINEL
from api.engine import SSEPublisher
from api.worker import run_engine
from tests.fakes.fake_engine import FakeTradingAgentsGraph


async def test_run_engine_completes_and_closes_bus():
    bus = Bus()
    publisher = SSEPublisher(bus=bus, run_id="r-happy", verbose=False)

    def make_engine() -> FakeTradingAgentsGraph:
        return FakeTradingAgentsGraph(callbacks=[publisher])

    queue = bus.subscribe()
    final_state, decision = await run_engine(
        make_engine=make_engine,
        ticker="NVDA",
        trade_date="2026-01-15",
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
