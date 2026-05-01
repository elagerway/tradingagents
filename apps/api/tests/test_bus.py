"""Tests for the in-process SSE event bus."""
import asyncio

import pytest

from api.bus import Bus, BusEvent


async def test_publish_fans_out_to_all_subscribers():
    bus = Bus()
    queue_a = bus.subscribe()
    queue_b = bus.subscribe()

    bus.publish({"type": "agent_started", "agent": "market_analyst"})

    event_a = await asyncio.wait_for(queue_a.get(), timeout=0.1)
    event_b = await asyncio.wait_for(queue_b.get(), timeout=0.1)

    assert isinstance(event_a, BusEvent)
    assert event_a.id == 1
    assert event_a.data == {"type": "agent_started", "agent": "market_analyst"}
    assert event_b.id == 1
    assert event_b.data == event_a.data


async def test_buffer_evicts_old_events():
    from api.bus import Bus, BUFFER_SIZE

    bus = Bus()
    for i in range(BUFFER_SIZE + 50):
        bus.publish({"i": i})

    # Replay since 0 should give us the most recent BUFFER_SIZE events.
    replayed = bus.replay_since(0)
    assert len(replayed) == BUFFER_SIZE
    assert replayed[0].data["i"] == 50  # earliest 50 evicted
    assert replayed[-1].data["i"] == BUFFER_SIZE + 49
