"""Per-run Alpha Vantage key injection.

`tradingagents.dataflows.alpha_vantage_common.get_api_key()` reads
`ALPHA_VANTAGE_API_KEY` from os.environ. With multi-tenant runs that
each carry their own user's BYO key, os.environ is unsafe — one user's
key can leak across concurrent runs sharing the process.

Replace `get_api_key()` with a ContextVar lookup. ContextVars are
asyncio-task-scoped and propagate through `asyncio.to_thread`, so the
worker thread running the engine sees the per-run key the request
handler set, with no cross-task contamination.
"""

from __future__ import annotations

import contextvars
import os

import tradingagents.dataflows.alpha_vantage_common as _av_common

current_key: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "alpha_vantage_current_key", default=None
)


def _patched_get_api_key() -> str:
    val = current_key.get()
    if val:
        return val
    fallback = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not fallback:
        raise ValueError("ALPHA_VANTAGE_API_KEY not set (no per-run key and no env fallback)")
    return fallback


def install() -> None:
    """Replace upstream get_api_key with the contextvar-aware version."""
    _av_common.get_api_key = _patched_get_api_key
