"""Tests for compute_realized_return — yfinance-driven return calc for
backdated runs."""

from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

from api.outcomes import compute_realized_return


def make_history(prices: list[float], start: date) -> pd.DataFrame:
    """Helper: synthesize a yfinance-shaped history DataFrame with business-day index."""
    dates = pd.date_range(start=start, periods=len(prices), freq="B")
    return pd.DataFrame({"Close": prices}, index=dates)


def test_compute_realized_return_simple_buy_5d():
    """5-day window, ticker up 5%, SPY up 2% → alpha=3%."""
    ticker_hist = make_history([100, 101, 102, 103, 104, 105], date(2026, 1, 12))
    spy_hist = make_history([400, 402, 404, 406, 408, 408], date(2026, 1, 12))

    with patch("api.outcomes._fetch_history") as mock:
        mock.side_effect = lambda t, *a, **kw: ticker_hist if t == "NVDA" else spy_hist

        result = compute_realized_return(
            ticker="NVDA",
            trade_date=date(2026, 1, 12),
            window_days=5,
        )

    assert result is not None
    raw, alpha, holding = result
    assert raw == pytest.approx(0.05, abs=0.001)
    assert alpha == pytest.approx(0.03, abs=0.001)
    assert holding == 5


def test_compute_realized_return_returns_none_when_no_data():
    """If yfinance returns empty/short history, we return None."""
    with patch("api.outcomes._fetch_history") as mock:
        mock.return_value = pd.DataFrame()
        result = compute_realized_return(
            ticker="NVDA",
            trade_date=date(2030, 1, 1),
            window_days=5,
        )
    assert result is None


def test_compute_realized_return_handles_partial_window():
    """If the window straddles weekends/holidays, returns the partial-window
    result without erroring."""
    ticker_hist = make_history([100, 102, 103, 104], date(2026, 1, 12))
    spy_hist = make_history([400, 401, 402, 403], date(2026, 1, 12))

    with patch("api.outcomes._fetch_history") as mock:
        mock.side_effect = lambda t, *a, **kw: ticker_hist if t == "NVDA" else spy_hist

        result = compute_realized_return(
            ticker="NVDA",
            trade_date=date(2026, 1, 12),
            window_days=5,
        )

    assert result is not None
    raw, alpha, holding = result
    assert holding == 3
    assert raw == pytest.approx(0.04, abs=0.001)
