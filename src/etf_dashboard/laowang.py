from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class GapEvent:
    kind: str  # 'GAP_UP' | 'GAP_DOWN'
    date: str
    prev_date: str
    lower: float
    upper: float
    threshold: float


@dataclass(frozen=True)
class GapStatus:
    last_gap: GapEvent | None
    is_filled: bool | None
    fill_date: str | None


@dataclass(frozen=True)
class IslandReversal:
    start_gap_up: GapEvent
    end_gap_down: GapEvent


@dataclass(frozen=True)
class VolumeSpikeDefense:
    is_spike: bool | None
    defense_price: float | None
    date: str | None
    vol_today: float | None
    vol_avg: float | None


def _to_date_str(idx) -> str:
    # yfinance uses Timestamp index; keep report stable with ISO date.
    try:
        return pd.Timestamp(idx).date().isoformat()
    except Exception:
        return str(idx)


def _required_columns(hist: pd.DataFrame) -> bool:
    req = {"Open", "High", "Low", "Close", "Volume"}
    return req.issubset(set(hist.columns))


def detect_last_gap(hist: pd.DataFrame, gap_threshold: float = 0.003, lookback_days: int = 60) -> GapStatus:
    """Detect the most recent gap-up or gap-down.

    Simplified spec:
    - gap_up at t if Low[t] > High[t-1] * (1 + gap_threshold)
    - gap_down at t if High[t] < Low[t-1] * (1 - gap_threshold)

    Gap area:
    - gap_up: (lower=High[t-1], upper=Low[t])
    - gap_down: (lower=High[t], upper=Low[t-1])

    Fill definition:
    - gap_up is filled if any later day has Low <= High[t-1]
    - gap_down is filled if any later day has High >= Low[t-1]
    """
    if hist is None or hist.empty or not _required_columns(hist):
        return GapStatus(last_gap=None, is_filled=None, fill_date=None)

    df = hist[["Open", "High", "Low", "Close", "Volume"]].astype(float).tail(max(lookback_days + 2, 10)).copy()
    if len(df) < 2:
        return GapStatus(last_gap=None, is_filled=None, fill_date=None)

    highs = df["High"].to_numpy()
    lows = df["Low"].to_numpy()

    last_gap: GapEvent | None = None
    last_i: int | None = None

    start = max(1, len(df) - lookback_days)
    for i in range(start, len(df)):
        prev_high = float(highs[i - 1])
        prev_low = float(lows[i - 1])
        hi = float(highs[i])
        lo = float(lows[i])

        if lo > prev_high * (1.0 + float(gap_threshold)):
            last_gap = GapEvent(
                kind="GAP_UP",
                date=_to_date_str(df.index[i]),
                prev_date=_to_date_str(df.index[i - 1]),
                lower=prev_high,
                upper=lo,
                threshold=float(gap_threshold),
            )
            last_i = i
        elif hi < prev_low * (1.0 - float(gap_threshold)):
            last_gap = GapEvent(
                kind="GAP_DOWN",
                date=_to_date_str(df.index[i]),
                prev_date=_to_date_str(df.index[i - 1]),
                lower=hi,
                upper=prev_low,
                threshold=float(gap_threshold),
            )
            last_i = i

    if last_gap is None or last_i is None:
        return GapStatus(last_gap=None, is_filled=None, fill_date=None)

    # Fill search starts AFTER the gap day
    is_filled = False
    fill_date: str | None = None
    if last_gap.kind == "GAP_UP":
        gap_fill_level = float(last_gap.lower)  # High[t-1]
        for j in range(last_i + 1, len(df)):
            if float(df["Low"].iloc[j]) <= gap_fill_level:
                is_filled = True
                fill_date = _to_date_str(df.index[j])
                break
    else:
        gap_fill_level = float(last_gap.upper)  # Low[t-1]
        for j in range(last_i + 1, len(df)):
            if float(df["High"].iloc[j]) >= gap_fill_level:
                is_filled = True
                fill_date = _to_date_str(df.index[j])
                break

    return GapStatus(last_gap=last_gap, is_filled=is_filled, fill_date=fill_date)


def detect_island_reversal(
    hist: pd.DataFrame,
    gap_threshold: float = 0.003,
    min_separation_days: int = 2,
    max_separation_days: int = 10,
    lookback_days: int = 120,
) -> IslandReversal | None:
    """Detect simplified island reversal: GAP_UP then within N days GAP_DOWN that overlaps/returns.

    We search within lookback_days, from oldest to newest, and return the latest matching pattern.

    Overlap/return condition (simplified):
    - Let gap_up area be [up_lower=High[t-1], up_upper=Low[t]]
    - Let gap_down area be [down_lower=High[s], down_upper=Low[s-1]]
    We require down_upper >= up_lower (price returned into/through the prior gap zone).
    """
    if hist is None or hist.empty or not _required_columns(hist):
        return None

    df = hist[["Open", "High", "Low", "Close", "Volume"]].astype(float).tail(max(lookback_days + 2, 20)).copy()
    if len(df) < 3:
        return None

    highs = df["High"].to_numpy()
    lows = df["Low"].to_numpy()

    latest: IslandReversal | None = None

    for i in range(1, len(df) - 1):
        prev_high = float(highs[i - 1])
        lo = float(lows[i])
        if not (lo > prev_high * (1.0 + float(gap_threshold))):
            continue

        gap_up = GapEvent(
            kind="GAP_UP",
            date=_to_date_str(df.index[i]),
            prev_date=_to_date_str(df.index[i - 1]),
            lower=prev_high,
            upper=lo,
            threshold=float(gap_threshold),
        )

        start_j = i + int(min_separation_days)
        end_j = min(len(df) - 1, i + int(max_separation_days))
        if start_j >= len(df):
            continue

        for j in range(start_j, end_j + 1):
            prev_low = float(lows[j - 1])
            hi = float(highs[j])
            if not (hi < prev_low * (1.0 - float(gap_threshold))):
                continue

            gap_down = GapEvent(
                kind="GAP_DOWN",
                date=_to_date_str(df.index[j]),
                prev_date=_to_date_str(df.index[j - 1]),
                lower=hi,
                upper=prev_low,
                threshold=float(gap_threshold),
            )

            # overlap/return into prior gap zone
            if float(gap_down.upper) >= float(gap_up.lower):
                latest = IslandReversal(start_gap_up=gap_up, end_gap_down=gap_down)

    return latest


def volume_spike_defense_price(
    hist: pd.DataFrame,
    vol_avg_window: int = 20,
    spike_mult: float = 2.0,
) -> VolumeSpikeDefense:
    """爆量K棒防守價（簡化版）。

    你指定：成交量均量改 default 20 天。

    判定（更合理的金融定義）：
    - 以「前 N 天均量」作為基準（不含當天），避免自我引用導致門檻不可達。
      vol_avg_today = rolling_mean(Volume, N).shift(1)
    - 爆量日：Volume[t] >= spike_mult * vol_avg_today 且紅K（Close > Open）
    - 防守價：Low[t]

    回傳：最近一次符合條件的爆量日；若沒有，回傳最新一天的 vol_today/vol_avg 以供報告展示。
    """
    if hist is None or hist.empty or not _required_columns(hist):
        return VolumeSpikeDefense(
            is_spike=None,
            defense_price=None,
            date=None,
            vol_today=None,
            vol_avg=None,
        )

    df = hist[["Open", "High", "Low", "Close", "Volume"]].astype(float).copy()
    if len(df) < vol_avg_window + 1:
        return VolumeSpikeDefense(is_spike=None, defense_price=None, date=None, vol_today=None, vol_avg=None)

    vavg_prev = df["Volume"].rolling(window=vol_avg_window, min_periods=vol_avg_window).mean().shift(1)
    latest: VolumeSpikeDefense | None = None

    for i in range(vol_avg_window, len(df)):
        vol_today = float(df["Volume"].iloc[i])
        vol_avg = float(vavg_prev.iloc[i]) if pd.notna(vavg_prev.iloc[i]) else None
        if vol_avg is None or vol_avg == 0:
            continue

        is_red = float(df["Close"].iloc[i]) > float(df["Open"].iloc[i])
        is_spike = (vol_today >= float(spike_mult) * vol_avg) and is_red
        if is_spike:
            latest = VolumeSpikeDefense(
                is_spike=True,
                defense_price=float(df["Low"].iloc[i]),
                date=_to_date_str(df.index[i]),
                vol_today=vol_today,
                vol_avg=vol_avg,
            )

    if latest is None:
        vol_today = float(df["Volume"].iloc[-1])
        vol_avg = float(vavg_prev.iloc[-1]) if pd.notna(vavg_prev.iloc[-1]) else None
        return VolumeSpikeDefense(
            is_spike=False if vol_avg is not None else None,
            defense_price=None,
            date=_to_date_str(df.index[-1]),
            vol_today=vol_today,
            vol_avg=vol_avg,
        )

    return latest
