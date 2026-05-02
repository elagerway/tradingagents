"""FastAPI routes for runs."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sse_starlette.sse import EventSourceResponse

from api import alpha_vantage_runtime
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


# Web/DB provider names → engine provider names. The web form + api_keys
# table use "dashscope"/"zhipu" (the API endpoint's marketing names);
# the engine's LLM client factory expects "qwen"/"glm".
_PROVIDER_NAME_TO_ENGINE: dict[str, str] = {
    "dashscope": "qwen",
    "zhipu": "glm",
}


# Default (deep_think_llm, quick_think_llm) per engine provider. Without
# these, the engine inherits OpenAI's gpt-5.4* defaults from
# DEFAULT_CONFIG and every non-OpenAI provider rejects the request as
# "unknown model". Sourced from tradingagents.llm_clients.model_catalog.
_PROVIDER_DEFAULT_MODELS: dict[str, tuple[str, str]] = {
    "openai": ("gpt-5.4", "gpt-5.4-mini"),
    "anthropic": ("claude-opus-4-7", "claude-sonnet-4-6"),
    "google": ("gemini-3.1-pro-preview", "gemini-3-flash-preview"),
    "xai": ("grok-4-0709", "grok-4-1-fast-non-reasoning"),
    "deepseek": ("deepseek-reasoner", "deepseek-chat"),
    "qwen": ("qwen3.6-plus", "qwen3.5-flash"),
    "glm": ("glm-5.1", "glm-4.7"),
}


def _build_engine_config(
    *,
    run_config: dict,
    api_key: str,
    has_alpha_vantage: bool = False,
) -> dict[str, Any]:
    """Compose the engine_config dict for TradingAgentsGraph.

    Picks provider-appropriate model defaults if `run_config` doesn't
    explicitly set deep_think_llm / quick_think_llm, translates
    web-side provider names ("dashscope"/"zhipu") to the engine names
    ("qwen"/"glm"), and — if the user has an Alpha Vantage key in their
    vault — flips the news_data vendor to AV with yfinance fallback.
    """
    from tradingagents.default_config import DEFAULT_CONFIG

    provider_web = run_config.get("llm_provider", "openai")
    provider_engine = _PROVIDER_NAME_TO_ENGINE.get(provider_web, provider_web)
    deep_default, quick_default = _PROVIDER_DEFAULT_MODELS.get(
        provider_engine, _PROVIDER_DEFAULT_MODELS["openai"]
    )

    # Merge data_vendors: defaults < run_config override < AV-aware override.
    data_vendors = {
        **DEFAULT_CONFIG.get("data_vendors", {}),
        **run_config.get("data_vendors", {}),
    }
    if has_alpha_vantage:
        # Comma list = primary then fallback; engine falls back automatically
        # on AlphaVantageRateLimitError. yfinance news is weaker so AV first.
        data_vendors["news_data"] = "alpha_vantage,yfinance"

    return {
        **DEFAULT_CONFIG,
        **run_config,
        "llm_provider": provider_engine,
        "deep_think_llm": run_config.get("deep_think_llm", deep_default),
        "quick_think_llm": run_config.get("quick_think_llm", quick_default),
        "api_key": api_key,
        "data_vendors": data_vendors,
        # Render's container has /tmp writable but $HOME may be locked-down
        "results_dir": "/tmp/tradingagents/logs",
        "data_cache_dir": "/tmp/tradingagents/cache",
    }


def _make_engine_factory(
    *,
    callbacks,
    fake: bool,
    env: dict[str, str],
    run_config: dict | None = None,
    user_id: UUID | None = None,
    run_id: UUID | None = None,
):
    """Returns a callable that constructs an engine instance with our
    callback wired in. The fake variant is used in tests + Plan 2-3 deploys;
    the real variant runs the upstream LangGraph engine with BYO keys
    threaded through config."""
    if fake:
        from api.fakes.fake_engine import FakeTradingAgentsGraph

        return lambda: FakeTradingAgentsGraph(callbacks=callbacks)

    # Real engine path
    from api.real_engine import TradingAgentsGraphWithUserContext

    rc = run_config or {}
    provider = rc.get("llm_provider", "openai")
    api_key = env.get(provider)
    if not api_key:
        raise RuntimeError(f"No BYO key loaded for provider: {provider}")
    if user_id is None:
        raise RuntimeError("user_id is required for real-engine factory")

    settings = get_settings()
    engine_config = _build_engine_config(
        run_config=rc,
        api_key=api_key,
        has_alpha_vantage="alpha_vantage" in env,
    )

    logger.info(
        "real_engine_factory",
        provider_web=provider,
        provider_engine=engine_config["llm_provider"],
        deep_think_llm=engine_config.get("deep_think_llm"),
        quick_think_llm=engine_config.get("quick_think_llm"),
        max_debate_rounds=engine_config.get("max_debate_rounds"),
        user_id=str(user_id),
    )

    return lambda: TradingAgentsGraphWithUserContext(
        selected_analysts=["market", "social", "news", "fundamentals"],
        debug=False,
        config=engine_config,
        callbacks=callbacks,
        user_id=user_id,
        run_id=run_id,
        supabase_url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
    )


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

    # 2. Load BYO keys. The LLM provider key is required; alpha_vantage is
    # best-effort — if the user has it, the engine flips news_data to AV.
    config = run.get("config") or {}
    provider = config.get("llm_provider", "openai")
    try:
        env_keys = await load_keys(
            user_id=user_id,
            providers=[provider],
            optional_providers=["alpha_vantage"],
            supabase_url=settings.supabase_url,
            service_role_key=settings.supabase_service_role_key,
        )
    except KeyVaultError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # 2b. Inject the user's Alpha Vantage key into the per-task contextvar.
    # asyncio.create_task copies the current context, so the worker thread
    # spawned via asyncio.to_thread sees this user's key — not a leaked one
    # from another concurrent run.
    av_key = env_keys.get("alpha_vantage")
    if av_key:
        alpha_vantage_runtime.current_key.set(av_key)

    # 3. Mark run started + create bus
    await mark_run_started(
        run_id=run_id,
        supabase_url=settings.supabase_url,
        service_role_key=settings.supabase_service_role_key,
    )
    bus = registry.get_or_create(str(run_id))
    publisher = SSEPublisher(bus=bus, run_id=str(run_id), verbose=True)

    factory = _make_engine_factory(
        callbacks=[publisher],
        fake=settings.use_fake_engine,
        env=env_keys,
        run_config=run.get("config") or {},
        user_id=user_id,
        run_id=run_id,
    )

    # 4. Kick off the run as a background task
    async def _drive():
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
                events=bus.snapshot(),
                final_state_keys=list(final_state.keys()),
                supabase_url=settings.supabase_url,
                service_role_key=settings.supabase_service_role_key,
            )
        except Exception as exc:
            await fail_run(
                run_id=run_id,
                error=str(exc),
                events=bus.snapshot(),
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
