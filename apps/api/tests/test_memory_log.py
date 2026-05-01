"""Tests for SupabaseMemoryLog — Supabase-backed replacement for the
upstream's TradingMemoryLog (which uses a local markdown file)."""

import json
from uuid import UUID

import httpx

from api.memory_log import SupabaseMemoryLog

USER_ID = UUID("11111111-2222-3333-4444-555555555555")


def make_transport(handler):
    return httpx.MockTransport(handler)


def test_store_decision_inserts_pending_row():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content) if request.content else None
        captured["prefer"] = request.headers.get("Prefer", "")
        return httpx.Response(201, json=[{"id": "abc"}])

    log = SupabaseMemoryLog(
        config={"memory_log_path": "/tmp/ignored.md", "memory_log_max_entries": None},
        user_id=USER_ID,
        run_id=None,
        supabase_url="http://test.local",
        service_role_key="srv",
        transport=make_transport(handler),
    )

    log.store_decision(
        ticker="NVDA",
        trade_date="2026-01-15",
        final_trade_decision="**BUY** — strong momentum + earnings beat.",
    )

    assert captured["method"] == "POST"
    assert "/rest/v1/user_memory" in captured["url"]
    body = captured["body"]
    assert body["user_id"] == str(USER_ID)
    assert body["ticker"] == "NVDA"
    assert body["trade_date"] == "2026-01-15"
    assert "BUY" in body["decision"]
    assert body["resolved"] is False
    assert "resolution=ignore-duplicates" in captured["prefer"]
