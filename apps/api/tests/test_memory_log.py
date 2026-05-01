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


def test_load_entries_returns_parsed_dicts():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json=[
                {
                    "trade_date": "2026-01-15",
                    "ticker": "NVDA",
                    "rating": "Buy",
                    "resolved": True,
                    "raw_return": 0.042,
                    "alpha_return": 0.021,
                    "holding_days": 5,
                    "decision": "long-form PM output",
                    "reflection": "BUY was right, momentum held.",
                },
                {
                    "trade_date": "2026-01-20",
                    "ticker": "AAPL",
                    "rating": "Hold",
                    "resolved": False,
                    "raw_return": None,
                    "alpha_return": None,
                    "holding_days": None,
                    "decision": "PM output",
                    "reflection": None,
                },
            ],
        )

    log = SupabaseMemoryLog(
        config={"memory_log_path": "/tmp/ignored.md", "memory_log_max_entries": None},
        user_id=USER_ID,
        run_id=None,
        supabase_url="http://test.local",
        service_role_key="srv",
        transport=make_transport(handler),
    )
    entries = log.load_entries()

    assert captured["params"]["user_id"] == f"eq.{USER_ID}"
    assert len(entries) == 2
    assert entries[0]["pending"] is False
    assert entries[0]["raw"] == 0.042
    assert entries[1]["pending"] is True
    assert entries[1]["reflection"] == ""


def test_get_pending_entries_filters_to_unresolved():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "trade_date": "2026-01-15",
                    "ticker": "NVDA",
                    "rating": "Buy",
                    "resolved": True,
                    "raw_return": 0.04,
                    "alpha_return": 0.02,
                    "holding_days": 5,
                    "decision": "x",
                    "reflection": "y",
                },
                {
                    "trade_date": "2026-01-20",
                    "ticker": "AAPL",
                    "rating": "Hold",
                    "resolved": False,
                    "raw_return": None,
                    "alpha_return": None,
                    "holding_days": None,
                    "decision": "x",
                    "reflection": None,
                },
            ],
        )

    log = SupabaseMemoryLog(
        config={"memory_log_path": "/tmp/ignored.md", "memory_log_max_entries": None},
        user_id=USER_ID,
        run_id=None,
        supabase_url="http://test.local",
        service_role_key="srv",
        transport=make_transport(handler),
    )
    pending = log.get_pending_entries()
    assert len(pending) == 1
    assert pending[0]["ticker"] == "AAPL"


def test_update_with_outcome_patches_row():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["params"] = dict(request.url.params)
        captured["body"] = json.loads(request.content) if request.content else None
        return httpx.Response(204, json=[])

    log = SupabaseMemoryLog(
        config={"memory_log_path": "/tmp/ignored.md", "memory_log_max_entries": None},
        user_id=USER_ID,
        run_id=None,
        supabase_url="http://test.local",
        service_role_key="srv",
        transport=make_transport(handler),
    )
    log.update_with_outcome(
        ticker="NVDA",
        trade_date="2026-01-15",
        raw_return=0.042,
        alpha_return=0.021,
        holding_days=5,
        reflection="BUY was right, momentum held.",
    )

    assert captured["method"] == "PATCH"
    assert captured["params"]["user_id"] == f"eq.{USER_ID}"
    assert captured["params"]["ticker"] == "eq.NVDA"
    assert captured["params"]["resolved"] == "eq.false"
    assert captured["body"]["resolved"] is True
    assert captured["body"]["raw_return"] == 0.042
    assert captured["body"]["reflection"].startswith("BUY")
