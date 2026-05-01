"""Integration tests for the runs endpoints."""
import asyncio
from unittest.mock import patch
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient

from api.main import create_app


RUN_ID = "00000000-0000-0000-0000-000000000aaa"
USER_ID = "11111111-2222-3333-4444-555555555555"


@pytest.fixture
def app(monkeypatch, hs256_secret):
    monkeypatch.setenv("SUPABASE_URL", "http://test.local")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "srv-key")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", hs256_secret)
    monkeypatch.setenv("USE_FAKE_ENGINE", "1")
    from api.settings import get_settings
    get_settings.cache_clear()
    return create_app()


def test_start_run_requires_authorization(app):
    client = TestClient(app)
    r = client.post(f"/runs/{RUN_ID}/start")
    assert r.status_code == 401


def test_start_run_returns_202_with_fake_engine(app, auth_header):
    client = TestClient(app)

    # Patch the run row fetch + key fetch + supabase_runs writes.
    fake_run = {
        "id": RUN_ID, "user_id": USER_ID,
        "ticker": "NVDA", "trade_date": "2026-01-15", "status": "pending",
        "config": {"llm_provider": "openai"},
        "events": [],
    }
    with patch("api.routes.fetch_run", return_value=fake_run), \
         patch("api.routes.load_keys", return_value={"openai": "sk-test"}), \
         patch("api.routes.mark_run_started", return_value=None), \
         patch("api.routes.finalize_run", return_value=None):
        r = client.post(f"/runs/{RUN_ID}/start", headers=auth_header)

    assert r.status_code == 202
    assert r.json() == {"run_id": RUN_ID, "status": "started"}


def test_stream_returns_sse_events(app, auth_header):
    """Smoke test that the SSE endpoint returns text/event-stream and at
    least one event when a run is in flight."""
    client = TestClient(app)

    # Manually populate the bus to simulate an in-flight run
    from api.bus import registry
    bus = registry.get_or_create(RUN_ID)
    bus.publish({"type": "agent_started", "agent": "market_analyst"})
    bus.publish({"type": "agent_completed", "agent": "market_analyst", "summary": "ok"})

    # Close the bus before streaming; use Last-Event-ID: 0 to replay all events
    bus.close()

    r = client.get(
        f"/runs/{RUN_ID}/stream",
        headers={**auth_header, "accept": "text/event-stream", "Last-Event-ID": "0"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert "agent_started" in r.text

    # Cleanup
    registry.drop(RUN_ID)


def test_stream_404_when_run_not_in_registry(app, auth_header):
    client = TestClient(app)
    r = client.get(f"/runs/00000000-0000-0000-0000-000000000fff/stream",
                   headers=auth_header)
    assert r.status_code == 404


def test_stream_replays_with_last_event_id(app, auth_header):
    client = TestClient(app)

    from api.bus import registry
    bus = registry.get_or_create(RUN_ID)
    bus.publish({"type": "a", "n": 1})
    bus.publish({"type": "b", "n": 2})
    bus.publish({"type": "c", "n": 3})

    # Close the bus so the stream terminates after replay
    bus.close()

    headers = {
        **auth_header,
        "accept": "text/event-stream",
        "Last-Event-ID": "1",   # we already saw event id=1
    }
    r = client.get(f"/runs/{RUN_ID}/stream", headers=headers)
    assert r.status_code == 200
    body = r.text

    # Should contain events 2 and 3 but not 1
    assert "\"n\": 2" in body
    assert "\"n\": 3" in body
    assert "\"n\": 1" not in body

    bus.close()
    registry.drop(RUN_ID)
