"""Smoke tests for the FastAPI app."""
from fastapi.testclient import TestClient

from api.main import create_app


def test_healthz_returns_ok():
    client = TestClient(create_app())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
