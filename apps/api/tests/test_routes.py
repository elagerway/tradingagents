"""Integration tests for the runs endpoints."""

from unittest.mock import patch

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
        "id": RUN_ID,
        "user_id": USER_ID,
        "ticker": "NVDA",
        "trade_date": "2026-01-15",
        "status": "pending",
        "config": {"llm_provider": "openai"},
        "events": [],
    }
    with (
        patch("api.routes.fetch_run", return_value=fake_run),
        patch("api.routes.load_keys", return_value={"openai": "sk-test"}),
        patch("api.routes.mark_run_started", return_value=None),
        patch("api.routes.finalize_run", return_value=None),
    ):
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
    r = client.get("/runs/00000000-0000-0000-0000-000000000fff/stream", headers=auth_header)
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
        "Last-Event-ID": "1",  # we already saw event id=1
    }
    r = client.get(f"/runs/{RUN_ID}/stream", headers=headers)
    assert r.status_code == 200
    body = r.text

    # Should contain events 2 and 3 but not 1
    assert '"n": 2' in body
    assert '"n": 3' in body
    assert '"n": 1' not in body

    bus.close()
    registry.drop(RUN_ID)


def test_make_engine_factory_real_path_uses_subclass(monkeypatch):
    """When USE_FAKE_ENGINE=0, the factory should construct
    TradingAgentsGraphWithUserContext with config including api_key."""
    monkeypatch.setenv("USE_FAKE_ENGINE", "0")
    monkeypatch.setenv("SUPABASE_URL", "http://test.local")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "srv")

    from api.settings import get_settings

    get_settings.cache_clear()

    from unittest.mock import patch
    from uuid import UUID

    from api.routes import _make_engine_factory

    captured: dict = {}

    def fake_constructor(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs

        class Stub:
            def propagate(self, ticker, date):
                return ({"ticker": ticker}, "BUY")

        return Stub()

    test_user_id = UUID("11111111-2222-3333-4444-555555555555")

    with patch("api.real_engine.TradingAgentsGraphWithUserContext", fake_constructor):
        factory = _make_engine_factory(
            callbacks=[],
            fake=False,
            env={"openai": "sk-test-secret"},
            run_config={"llm_provider": "openai"},
            user_id=test_user_id,
            run_id=None,
        )
        engine = factory()

    assert engine is not None
    config = captured["kwargs"]["config"]
    assert config["api_key"] == "sk-test-secret"
    assert config["llm_provider"] == "openai"
    assert "deep_think_llm" in config
    assert "quick_think_llm" in config
    assert config["results_dir"].startswith("/tmp/")
    assert config["data_cache_dir"].startswith("/tmp/")


def test_make_engine_factory_real_path_threads_user_id_to_memory(monkeypatch):
    """Real engine path must construct a TradingAgentsGraph instance with
    SupabaseMemoryLog (user-scoped) replacing the default file-based one."""
    monkeypatch.setenv("USE_FAKE_ENGINE", "0")
    monkeypatch.setenv("SUPABASE_URL", "http://test.local")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "srv")

    from api.settings import get_settings

    get_settings.cache_clear()

    from unittest.mock import patch
    from uuid import UUID

    from api.routes import _make_engine_factory

    captured = {}

    def fake_constructor(*args, **kwargs):
        captured["kwargs"] = kwargs

        class Stub:
            def __init__(self):
                self.memory_log = None

            def propagate(self, *a, **kw):
                return ({}, "BUY")

        return Stub()

    test_user_id = UUID("11111111-2222-3333-4444-555555555555")

    with patch("api.real_engine.TradingAgentsGraphWithUserContext", fake_constructor):
        factory = _make_engine_factory(
            callbacks=[],
            fake=False,
            env={"openai": "sk-test-secret"},
            run_config={"llm_provider": "openai"},
            user_id=test_user_id,
            run_id=None,
        )
        factory()

    kwargs = captured["kwargs"]
    assert kwargs["user_id"] == test_user_id
    assert kwargs["supabase_url"] == "http://test.local"
    assert kwargs["service_role_key"] == "srv"
