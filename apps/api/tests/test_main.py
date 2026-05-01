"""Smoke tests for the FastAPI app."""

from fastapi.testclient import TestClient

from api.main import create_app


def test_healthz_returns_ok():
    client = TestClient(create_app())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_preflight_for_runs_start(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://web.example.com")
    from api.settings import get_settings

    get_settings.cache_clear()

    client = TestClient(create_app())
    r = client.options(
        "/runs/00000000-0000-0000-0000-000000000aaa/start",
        headers={
            "Origin": "https://web.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "https://web.example.com"
