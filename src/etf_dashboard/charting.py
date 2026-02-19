from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .indicators import sma


@dataclass(frozen=True)
class ChartData:
    df: pd.DataFrame


def prepare_chart_data(
    hist: pd.DataFrame,
    ma_windows: list[int] | None = None,
    volume_avg_window: int = 20,
) -> ChartData:
    """Prepare a chart-ready dataframe.

    Output columns:
    - Open/High/Low/Close/Volume
    - MA{n} for each n in ma_windows
    - VAVG{volume_avg_window}

    Assumes hist index is datetime-like.
    """
    if ma_windows is None:
        ma_windows = [5, 10, 20, 50, 60, 150, 200]

    df = hist[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index = pd.to_datetime(df.index)

    close = df["Close"].astype(float)
    for w in ma_windows:
        df[f"MA{w}"] = sma(close, int(w))

    v = df["Volume"].astype(float)
    df[f"VAVG{int(volume_avg_window)}"] = v.rolling(window=int(volume_avg_window), min_periods=int(volume_avg_window)).mean()

    return ChartData(df=df)
