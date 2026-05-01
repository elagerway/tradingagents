"""Tests for the janitor that sweeps stuck runs."""

import json
from datetime import UTC, datetime, timedelta

import httpx

from api.janitor import sweep_stuck_runs


async def test_sweep_marks_old_running_rows_as_failed():
    captured = {"calls": []}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["calls"].append(
            {
                "method": request.method,
                "url": str(request.url),
                "body": json.loads(request.content) if request.content else None,
            }
        )
        if request.method == "GET":
            old = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
            return httpx.Response(
                200,
                json=[
                    {"id": "00000000-0000-0000-0000-000000000aaa", "started_at": old},
                ],
            )
        return httpx.Response(204, json=[])

    transport = httpx.MockTransport(handler)
    swept = await sweep_stuck_runs(
        supabase_url="http://test.local",
        service_role_key="srv",
        threshold_minutes=30,
        transport=transport,
    )
    assert swept == 1
    methods = [c["method"] for c in captured["calls"]]
    assert "GET" in methods
    assert "PATCH" in methods
    patch_call = next(c for c in captured["calls"] if c["method"] == "PATCH")
    assert patch_call["body"]["status"] == "failed"
    assert "Run timed out" in patch_call["body"]["error"]


async def test_sweep_returns_zero_when_no_stuck_rows():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    swept = await sweep_stuck_runs(
        supabase_url="http://test.local",
        service_role_key="srv",
        threshold_minutes=30,
        transport=transport,
    )
    assert swept == 0
