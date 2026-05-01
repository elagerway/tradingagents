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
    from api.bus import BUFFER_SIZE, Bus

    bus = Bus()
    for i in range(BUFFER_SIZE + 50):
        bus.publish({"i": i})

    # Replay since 0 should give us the most recent BUFFER_SIZE events.
    replayed = bus.replay_since(0)
    assert len(replayed) == BUFFER_SIZE
    assert replayed[0].data["i"] == 50  # earliest 50 evicted
    assert replayed[-1].data["i"] == BUFFER_SIZE + 49


async def test_replay_since_returns_only_newer_events():
    bus = Bus()
    bus.publish({"i": 1})
    bus.publish({"i": 2})
    bus.publish({"i": 3})

    replayed = bus.replay_since(last_event_id=1)
    assert [e.id for e in replayed] == [2, 3]
    assert [e.data["i"] for e in replayed] == [2, 3]


async def test_close_pushes_sentinel_to_all_subscribers():
    from api.bus import SENTINEL, Bus

    bus = Bus()
    queue_a = bus.subscribe()
    queue_b = bus.subscribe()

    bus.close()

    assert (await asyncio.wait_for(queue_a.get(), timeout=0.1)) is SENTINEL
    assert (await asyncio.wait_for(queue_b.get(), timeout=0.1)) is SENTINEL
    assert bus.closed is True

    with pytest.raises(RuntimeError, match="closed"):
        bus.publish({"too": "late"})


async def test_bus_registry_returns_same_instance_per_run_id():
    from api.bus import BusRegistry

    registry = BusRegistry()
    bus1 = registry.get_or_create("run-abc")
    bus2 = registry.get_or_create("run-abc")
    bus3 = registry.get_or_create("run-xyz")

    assert bus1 is bus2
    assert bus1 is not bus3


async def test_bus_registry_drops_closed_buses():
    from api.bus import BusRegistry

    registry = BusRegistry()
    bus = registry.get_or_create("run-abc")
    bus.close()
    registry.drop("run-abc")
    new_bus = registry.get_or_create("run-abc")
    assert new_bus is not bus
