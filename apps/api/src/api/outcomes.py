"""Compute realized returns for a (ticker, trade_date) pair via yfinance.

Mirrors the logic in upstream's TradingAgentsGraph._fetch_returns
(trading_graph.py:190-226) but as a standalone function we can call from
the FastAPI worker after a run completes.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from api.logging import get_logger

logger = get_logger(__name__)

DEFAULT_WINDOW_DAYS = 5
BENCHMARK_TICKER = "SPY"


def _fetch_history(ticker: str, start: date, end: date) -> pd.DataFrame:
    """Thin yfinance wrapper — separated for testability via patch()."""
    return yf.Ticker(ticker).history(start=start.isoformat(), end=end.isoformat(), auto_adjust=True)


def compute_realized_return(
    *,
    ticker: str,
    trade_date: date,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> tuple[float, float, int] | None:
    """Return (raw_return, alpha_return, actual_holding_days), or None if
    yfinance has insufficient data.
    """
    end = trade_date + timedelta(days=window_days + 7)
    try:
        ticker_hist = _fetch_history(ticker, trade_date, end)
        spy_hist = _fetch_history(BENCHMARK_TICKER, trade_date, end)
    except Exception as exc:
        logger.warning("yfinance fetch failed", ticker=ticker, error=str(exc)[:200])
        return None

    if len(ticker_hist) < 2 or len(spy_hist) < 2:
        return None

    actual_days = min(window_days, len(ticker_hist) - 1, len(spy_hist) - 1)
    t_start = ticker_hist["Close"].iloc[0]
    t_end = ticker_hist["Close"].iloc[actual_days]
    s_start = spy_hist["Close"].iloc[0]
    s_end = spy_hist["Close"].iloc[actual_days]

    raw = float((t_end - t_start) / t_start)
    alpha = float(raw - (s_end - s_start) / s_start)

    return raw, alpha, actual_days
