"""FastAPI routes for runs."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sse_starlette.sse import EventSourceResponse

from api.auth import current_user_id
from api.bus import registry
from api.engine import SSEPublisher
from api.keys import KeyVaultError, load_keys
from api.logging import get_logger
from api.settings import get_settings
from api.supabase_runs import (
    fail_run,
    fetch_run,
    finalize_run,
    mark_run_started,
)
from api.worker import run_engine

router = APIRouter()
logger = get_logger(__name__)


def _make_engine_factory(*, callbacks, fake: bool, env: dict[str, str]):
    """Returns a callable that constructs an engine instance with our
    callback wired in. Plan 4 swaps the fake for the real one."""
    if fake:
        from api.fakes.fake_engine import FakeTradingAgentsGraph

        return lambda: FakeTradingAgentsGraph(callbacks=callbacks)
    raise NotImplementedError("real engine wiring lands in Plan 4")


@router.post("/runs/{run_id}/start", status_code=status.HTTP_202_ACCEPTED)
async def start_run(
    run_id: UUID,
    user_id: Annotated[UUID, Depends(current_user_id)],
):
    settings = get_settings()

    # 1. Load run row
    run = await fetch_run(
        run_id=run_id,
        supabase_url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
    )
    if str(run["user_id"]) != str(user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not your run")

    # 2. Load BYO keys (synchronous w.r.t. start: fail fast if missing)
    config = run.get("config") or {}
    provider = config.get("llm_provider", "openai")
    try:
        env_keys = await load_keys(
            user_id=user_id,
            providers=[provider],
            supabase_url=settings.supabase_url,
            service_role_key=settings.supabase_service_role_key,
        )
    except KeyVaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # 3. Mark run started + create bus
    await mark_run_started(
        run_id=run_id,
        supabase_url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
    )
    bus = registry.get_or_create(str(run_id))
    publisher = SSEPublisher(bus=bus, run_id=str(run_id), verbose=False)

    factory = _make_engine_factory(
        callbacks=[publisher],
        fake=settings.use_fake_engine,
        env=env_keys,
    )

    # 4. Kick off the run as a background task
    async def _drive():
        events_for_persist: list[dict[str, Any]] = []
        try:
            final_state, decision = await run_engine(
                make_engine=factory,
                ticker=run["ticker"],
                trade_date=run["trade_date"],
                bus=bus,
            )
            await finalize_run(
                run_id=run_id,
                decision=decision,
                events=events_for_persist,
                final_state_keys=list(final_state.keys()),
                supabase_url=settings.supabase_url,
                service_role_key=settings.supabase_service_role_key,
            )
        except Exception as exc:
            await fail_run(
                run_id=run_id,
                error=str(exc),
                events=events_for_persist,
                supabase_url=settings.supabase_url,
                service_role_key=settings.supabase_service_role_key,
            )
        finally:
            registry.drop(str(run_id))

    asyncio.create_task(_drive())
    return {"run_id": str(run_id), "status": "started"}


@router.get("/runs/{run_id}/stream")
async def stream_run(
    run_id: UUID,
    user_id: Annotated[UUID, Depends(current_user_id)],
    last_event_id: Annotated[int | None, Header()] = None,
):
    bus = registry.get(str(run_id))
    if bus is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no live run")

    queue = bus.subscribe()

    async def _generator():
        # Replay missed events
        for event in bus.replay_since(last_event_id):
            yield {"id": str(event.id), "data": _json(event.data)}
        # If bus was already closed before we subscribed, stop here
        if bus.closed:
            bus.unsubscribe(queue)
            return
        # Live stream
        from api.bus import SENTINEL

        try:
            while True:
                event = await queue.get()
                if event is SENTINEL:
                    return
                yield {"id": str(event.id), "data": _json(event.data)}
        finally:
            bus.unsubscribe(queue)

    return EventSourceResponse(_generator(), ping=15)


def _json(obj) -> str:
    import json

    return json.dumps(obj)
