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
