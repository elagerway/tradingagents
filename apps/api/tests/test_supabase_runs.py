"""Tests for the runs-table service-role REST client."""

import json
from uuid import UUID

import httpx

from api.supabase_runs import (
    fetch_run,
    mark_run_started,
)

RUN_ID = UUID("00000000-0000-0000-0000-000000000aaa")
USER_ID = UUID("11111111-2222-3333-4444-555555555555")


def make_transport(*, status: int, payload):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload)

    return httpx.MockTransport(handler)


async def test_fetch_run_returns_dict():
    transport = make_transport(
        status=200,
        payload=[
            {
                "id": str(RUN_ID),
                "user_id": str(USER_ID),
                "ticker": "NVDA",
                "trade_date": "2026-01-15",
                "status": "pending",
                "config": {"llm_provider": "openai"},
                "events": [],
            }
        ],
    )
    run = await fetch_run(
        run_id=RUN_ID,
        supabase_url="http://test.local",
        service_role_key="srv",
        transport=transport,
    )
    assert run["ticker"] == "NVDA"
    assert run["status"] == "pending"


async def test_mark_run_started_patches_status():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    await mark_run_started(
        run_id=RUN_ID,
        supabase_url="http://test.local",
        service_role_key="srv",
        transport=transport,
    )
    assert captured["body"]["status"] == "running"
    assert "started_at" in captured["body"]
