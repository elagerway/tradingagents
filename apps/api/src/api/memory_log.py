"""Supabase-backed memory log — drop-in replacement for the upstream
TradingMemoryLog's local-file storage. User-scoped via user_id; never
crosses user boundaries.

The upstream writes a single markdown file at memory_log_path. We override
the public methods that read and write entries; the inherited helper
formatters (_format_full, _format_reflection_only, _parse_entry) are
reused as-is — no file I/O happens in them.
"""

from __future__ import annotations

import json
from uuid import UUID

import httpx
from tradingagents.agents.utils.memory import TradingMemoryLog
from tradingagents.agents.utils.rating import parse_rating

from api.logging import get_logger

logger = get_logger(__name__)


class SupabaseMemoryLog(TradingMemoryLog):
    """User-scoped memory log backed by the public.user_memory table."""

    def __init__(
        self,
        config: dict,
        *,
        user_id: UUID,
        run_id: UUID | None,
        supabase_url: str,
        service_role_key: str,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 5.0,
    ):
        super().__init__(config)
        self.user_id = str(user_id)
        self.run_id = str(run_id) if run_id else None
        self._base = supabase_url.rstrip("/")
        self._headers = {
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        self._transport = transport
        self._timeout = timeout

    # ----- write methods --------------------------------------------------

    def store_decision(
        self,
        ticker: str,
        trade_date: str,
        final_trade_decision: str,
    ) -> None:
        """Insert a pending entry. Idempotent via the unique constraint."""
        rating = parse_rating(final_trade_decision) or "Hold"
        body = {
            "user_id": self.user_id,
            "run_id": self.run_id,
            "ticker": ticker,
            "trade_date": str(trade_date),
            "rating": rating,
            "decision": final_trade_decision,
            "resolved": False,
        }
        headers = {
            **self._headers,
            "Prefer": "return=representation,resolution=ignore-duplicates",
        }
        with httpx.Client(transport=self._transport, timeout=self._timeout) as c:
            r = c.post(f"{self._base}/rest/v1/user_memory", headers=headers, json=body)
        if r.status_code not in (200, 201):
            logger.error("store_decision failed", status=r.status_code, user_id=self.user_id)
            raise RuntimeError(f"store_decision returned {r.status_code}")

    def update_with_outcome(
        self,
        ticker: str,
        trade_date: str,
        raw_return: float,
        alpha_return: float,
        holding_days: int,
        reflection: str,
    ) -> None:
        """Resolve a single pending entry."""
        body = {
            "resolved": True,
            "raw_return": raw_return,
            "alpha_return": alpha_return,
            "holding_days": holding_days,
            "reflection": reflection,
            "resolved_at": "now()",
        }
        params = {
            "user_id": f"eq.{self.user_id}",
            "ticker": f"eq.{ticker}",
            "trade_date": f"eq.{trade_date}",
            "resolved": "eq.false",
        }
        with httpx.Client(transport=self._transport, timeout=self._timeout) as c:
            r = c.patch(
                f"{self._base}/rest/v1/user_memory",
                headers=self._headers,
                params=params,
                content=json.dumps(body, default=str),
            )
        if r.status_code not in (200, 204):
            raise RuntimeError(f"update_with_outcome returned {r.status_code}")

    def batch_update_with_outcomes(self, updates: list[dict]) -> None:
        """Sequential single-row updates — fine for the small N we expect (<10)."""
        for u in updates:
            self.update_with_outcome(**u)

    # ----- read methods ---------------------------------------------------

    def load_entries(self) -> list[dict]:
        """Return the user's full memory in upstream's parsed-entry shape."""
        select_cols = (
            "trade_date,ticker,rating,resolved,"
            "raw_return,alpha_return,holding_days,decision,reflection"
        )
        params = {
            "user_id": f"eq.{self.user_id}",
            "select": select_cols,
            "order": "created_at.desc",
        }
        with httpx.Client(transport=self._transport, timeout=self._timeout) as c:
            r = c.get(
                f"{self._base}/rest/v1/user_memory",
                headers=self._headers,
                params=params,
            )
        if r.status_code != 200:
            raise RuntimeError(f"load_entries returned {r.status_code}")
        rows = r.json()
        return [
            {
                "date": row["trade_date"],
                "ticker": row["ticker"],
                "rating": row["rating"],
                "pending": not row["resolved"],
                "raw": row.get("raw_return"),
                "alpha": row.get("alpha_return"),
                "holding": row.get("holding_days"),
                "decision": row["decision"],
                "reflection": row.get("reflection") or "",
            }
            for row in rows
        ]

    def get_pending_entries(self) -> list[dict]:
        return [e for e in self.load_entries() if e["pending"]]
