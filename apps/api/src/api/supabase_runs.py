"""Service-role REST helpers for the `runs` table.

Used by the worker to: load the run row, transition status, persist final
state. All calls bypass RLS (service_role)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from api.logging import get_logger

logger = get_logger(__name__)


def _headers(key: str) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


async def fetch_run(
    *, run_id: UUID, supabase_url: str, service_role_key: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    url = f"{supabase_url.rstrip('/')}/rest/v1/runs"
    async with httpx.AsyncClient(transport=transport, timeout=5.0) as client:
        r = await client.get(
            url,
            headers=_headers(service_role_key),
            params={"id": f"eq.{run_id}", "select": "*"},
        )
    if r.status_code != 200:
        raise RuntimeError(f"fetch_run {r.status_code}")
    rows = r.json()
    if not rows:
        raise RuntimeError(f"run {run_id} not found")
    return rows[0]


async def _patch_run(
    *, run_id: UUID, body: dict[str, Any],
    supabase_url: str, service_role_key: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> None:
    url = f"{supabase_url.rstrip('/')}/rest/v1/runs"
    async with httpx.AsyncClient(transport=transport, timeout=5.0) as client:
        r = await client.patch(
            url,
            headers=_headers(service_role_key),
            params={"id": f"eq.{run_id}"},
            content=json.dumps(body, default=str),
        )
    if r.status_code not in (200, 204):
        raise RuntimeError(f"patch_run {r.status_code}: {r.text[:200]}")


async def mark_run_started(
    *, run_id: UUID, supabase_url: str, service_role_key: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> None:
    await _patch_run(
        run_id=run_id,
        body={
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
        },
        supabase_url=supabase_url,
        service_role_key=service_role_key,
        transport=transport,
    )


async def finalize_run(
    *, run_id: UUID, decision: str, events: list[dict[str, Any]],
    final_state_keys: list[str],
    supabase_url: str, service_role_key: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> None:
    await _patch_run(
        run_id=run_id,
        body={
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "final_decision": {"decision": decision, "state_keys": final_state_keys},
            "events": events,
        },
        supabase_url=supabase_url,
        service_role_key=service_role_key,
        transport=transport,
    )


async def fail_run(
    *, run_id: UUID, error: str, events: list[dict[str, Any]],
    supabase_url: str, service_role_key: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> None:
    await _patch_run(
        run_id=run_id,
        body={
            "status": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error": error[:1000],
            "events": events,
        },
        supabase_url=supabase_url,
        service_role_key=service_role_key,
        transport=transport,
    )
