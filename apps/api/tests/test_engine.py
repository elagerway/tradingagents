"""Tests for the LangChain callback adapter that publishes SSE events."""

from uuid import uuid4

from api.bus import Bus
from api.engine import SSEPublisher


def test_on_chain_start_publishes_agent_started():
    bus = Bus()
    publisher = SSEPublisher(bus=bus, run_id="run-1", verbose=False)

    publisher.on_chain_start(
        serialized={"name": "market_analyst"},
        inputs={},
        run_id=uuid4(),
        name="market_analyst",
    )

    # One event in the buffer.
    events = bus.replay_since(0)
    assert len(events) == 1
    assert events[0].data["type"] == "agent_started"
    assert events[0].data["agent"] == "market_analyst"


def test_on_chain_end_publishes_agent_completed_with_summary():
    bus = Bus()
    publisher = SSEPublisher(bus=bus, run_id="run-1", verbose=False)

    publisher.on_chain_end(
        outputs={"market_analyst_report": "Long report. " * 50},
        run_id=uuid4(),
        name="market_analyst",
    )

    events = bus.replay_since(0)
    assert len(events) == 1
    e = events[0].data
    assert e["type"] == "agent_completed"
    assert e["agent"] == "market_analyst"
    assert "summary" in e
    assert len(e["summary"]) <= 500  # adapter truncates


def test_on_chat_model_start_emits_agent_thinking_keepalive():
    bus = Bus()
    publisher = SSEPublisher(bus=bus, run_id="run-1", verbose=False)
    publisher.on_chat_model_start(
        serialized={},
        messages=[],
        run_id=uuid4(),
        name="trader",
    )
    events = bus.replay_since(0)
    assert len(events) == 1
    assert events[0].data["type"] == "agent_thinking"
    assert events[0].data["agent"] == "trader"


def test_tool_events_only_in_verbose_mode():
    bus_quiet = Bus()
    SSEPublisher(bus=bus_quiet, run_id="r", verbose=False).on_tool_start(
        serialized={"name": "get_stock_data"},
        input_str="NVDA",
        run_id=uuid4(),
    )
    assert bus_quiet.replay_since(0) == []  # nothing emitted

    bus_verbose = Bus()
    SSEPublisher(bus=bus_verbose, run_id="r", verbose=True).on_tool_start(
        serialized={"name": "get_stock_data"},
        input_str="NVDA",
        run_id=uuid4(),
    )
    events = bus_verbose.replay_since(0)
    assert len(events) == 1
    assert events[0].data["type"] == "tool_called"
    assert events[0].data["tool"] == "get_stock_data"


def test_fake_engine_emits_full_event_sequence():
    from api.fakes.fake_engine import CANNED_AGENTS, FakeTradingAgentsGraph

    bus = Bus()
    publisher = SSEPublisher(bus=bus, run_id="r", verbose=False)
    fake = FakeTradingAgentsGraph(callbacks=[publisher])

    final_state, decision = fake.propagate("NVDA", "2026-01-15")

    types = [e.data["type"] for e in bus.replay_since(0)]
    # Each agent fires: started → thinking → completed (3 events × N agents)
    assert types.count("agent_started") == len(CANNED_AGENTS)
    assert types.count("agent_thinking") == len(CANNED_AGENTS)
    assert types.count("agent_completed") == len(CANNED_AGENTS)
    assert decision == "BUY"
