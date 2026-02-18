from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf


@dataclass(frozen=True)
class YahooSnapshot:
    ticker: str
    asof_utc: datetime
    history: pd.DataFrame  # columns: Open High Low Close Volume
    info: dict


def fetch_snapshot(ticker: str, lookback_days: int = 400) -> YahooSnapshot:
    """Fetch daily history + info from Yahoo Finance via yfinance.

    Notes:
    - Uses daily bars. For transparency, we compute indicators from daily *Close*.
    - `lookback_days` is calendar days; we request more than needed to ensure MA150.
    """
    asof_utc = datetime.now(timezone.utc)

    t = yf.Ticker(ticker)

    # 2y is safe for MA150 even with holidays; keep it simple.
    # We still allow lookback_days, but yfinance period is coarse; use max(lookback_days, 400).
    period_days = max(int(lookback_days), 400)
    period = "2y" if period_days >= 500 else "1y"

    hist = t.history(period=period, interval="1d", auto_adjust=False)
    if hist is None or hist.empty:
        raise RuntimeError(f"No Yahoo history returned for {ticker}")

    hist = hist[["Open", "High", "Low", "Close", "Volume"]].copy()
    hist.index = pd.to_datetime(hist.index)

    info = {}
    try:
        info = t.info or {}
    except Exception:
        # yfinance may fail on info occasionally; keep running, but the report must mark missing fields.
        info = {}

    return YahooSnapshot(ticker=ticker, asof_utc=asof_utc, history=hist, info=info)


def yahoo_quote_url(ticker: str) -> str:
    return f"https://finance.yahoo.com/quote/{ticker}"


def yahoo_history_url(ticker: str) -> str:
    return f"https://finance.yahoo.com/quote/{ticker}/history"
