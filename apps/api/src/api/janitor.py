"""Janitor: scans `runs` for rows stuck in `running` state and marks them
failed. Designed to be invoked by a Render cron job every 5 minutes.

Entry point: `python -m api.janitor`
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import httpx

from api.logging import configure_logging, get_logger
from api.settings import get_settings

logger = get_logger(__name__)


async def sweep_stuck_runs(
    *,
    supabase_url: str,
    service_role_key: str,
    threshold_minutes: int,
    transport: httpx.AsyncBaseTransport | None = None,
) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=threshold_minutes)).isoformat()
    base = supabase_url.rstrip("/")
    headers = {
        "apikey": service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(transport=transport, timeout=10.0) as client:
        # Find stuck rows
        get = await client.get(
            f"{base}/rest/v1/runs",
            headers=headers,
            params={
                "status": "eq.running",
                "started_at": f"lt.{cutoff}",
                "select": "id,started_at",
            },
        )
        if get.status_code != 200:
            raise RuntimeError(f"janitor list {get.status_code}")
        stuck = get.json()
        if not stuck:
            return 0

        # Mark each one failed
        for row in stuck:
            patch = await client.patch(
                f"{base}/rest/v1/runs",
                headers=headers,
                params={"id": f"eq.{row['id']}"},
                content=json.dumps({
                    "status": "failed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "error": "Run timed out or worker died",
                }, default=str),
            )
            if patch.status_code not in (200, 204):
                logger.error("janitor patch failed",
                             run_id=row["id"], status=patch.status_code)

    logger.info("janitor sweep done", swept=len(stuck))
    return len(stuck)


def main() -> None:
    """Cron entrypoint: `python -m api.janitor`."""
    configure_logging()
    settings = get_settings()
    swept = asyncio.run(sweep_stuck_runs(
        supabase_url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
        threshold_minutes=settings.stuck_run_threshold_minutes,
    ))
    print(f"swept {swept} stuck runs")


if __name__ == "__main__":
    main()
