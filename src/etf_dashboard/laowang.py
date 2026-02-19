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


@dataclass(frozen=True)
class GapStatus:
    """Track the latest *effective* gap within lookback_days.

    Spec alignment:
    - Strict gap definition (no threshold):
      - GAP_UP at t if Low[t] > High[t-1]
      - GAP_DOWN at t if High[t] < Low[t-1]
    - Only the last gap is tracked; it expires after lookback_days.
    - Fill is defined by *close* crossing the relevant edge.
    """

    last_gap: GapEvent | None

    # Effective window
    lookback_days: int | None
    is_expired: bool | None

    # Close-based fill (收盤價準則)
    is_filled_by_close: bool | None
    fill_date_by_close: str | None
    fill_close_by_close: float | None

    # For GAP_UP only: reclaim signal inputs (used by gap_reclaim_within_3_days)
    reclaim_level: float | None  # up_gap_upper = Low[gap_day]


@dataclass(frozen=True)
class IslandReversal:
    start_gap_up: GapEvent
    end_gap_down: GapEvent


@dataclass(frozen=True)
class ReclaimSignal:
    is_reclaim: bool | None
    reclaim_date: str | None
    days_since_fill: int | None
    reclaim_level: float | None
@dataclass(frozen=True)
class MidpointDefense:
    """長紅中軸防守 (support) from the latest strong red candle.

    Spec (confirmed):
    - long red candle = latest candle where:
      - Close > Open (red)
      - body_ratio = (Close-Open)/(High-Low) >= 0.6 (and High>Low)
    - midpoint = (High + Low) / 2
    - broken when Close < midpoint (close-based rule)
    """

    midpoint: float | None
    date: str | None
    is_broken: bool | None




@dataclass(frozen=True)
class BearishOmens:
    long_black_engulf: bool | None
    price_up_vol_down: bool | None
    distribution_day: bool | None


@dataclass(frozen=True)
class MassiveVolumeLevel:
    """爆量K棒防守/壓力 (massive volume level).

    Spec (confirmed):
    - massive_vol: 成交量 = lookback_days 內最高量（不需要倍數門檻）
    - massive_low = Low[爆量日]；massive_high = High[爆量日]
    - Low_broken when Close < massive_low
    - High_broken when Close > massive_high
    """

    is_massive: bool | None
    low: float | None
    high: float | None
    date: str | None

    vol_today: float | None
    vol_max_lookback: float | None

    lookback_days: int | None
    low_broken: bool | None
    high_broken: bool | None


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
    """Detect the latest *effective* strict gap (no threshold) within lookback_days.

    Spec:
    - GAP_UP (support): Low[t] > High[t-1]
      - zone: [up_gap_bottom=High[t-1], up_gap_upper=Low[t]]
      - filled-by-close when Close <= up_gap_bottom
      - reclaim level (for false-break reclaim): up_gap_upper
    - GAP_DOWN (resistance): High[t] < Low[t-1]
      - zone: [down_gap_bottom=High[t], down_gap_top=Low[t-1]]
      - filled-by-close when Close >= down_gap_top

    Expiration:
    - if (latest_date - gap_date) > lookback_days => expired and ignored.

    Note: gap_threshold is ignored (kept for backward compatibility with callers).
    """
    _ = gap_threshold

    if hist is None or hist.empty or not _required_columns(hist):
        return GapStatus(
            last_gap=None,
            lookback_days=int(lookback_days),
            is_expired=None,
            is_filled_by_close=None,
            fill_date_by_close=None,
            fill_close_by_close=None,
            reclaim_level=None,
        )

    df = hist[["Open", "High", "Low", "Close", "Volume"]].astype(float).tail(max(int(lookback_days) + 2, 10)).copy()
    if len(df) < 2:
        return GapStatus(
            last_gap=None,
            lookback_days=int(lookback_days),
            is_expired=None,
            is_filled_by_close=None,
            fill_date_by_close=None,
            fill_close_by_close=None,
            reclaim_level=None,
        )

    df.index = pd.to_datetime(df.index)
    highs = df["High"].to_numpy()
    lows = df["Low"].to_numpy()

    last_gap: GapEvent | None = None
    last_i: int | None = None

    start = max(1, len(df) - int(lookback_days))
    for i in range(start, len(df)):
        prev_high = float(highs[i - 1])
        prev_low = float(lows[i - 1])
        hi = float(highs[i])
        lo = float(lows[i])

        # strict gap_up
        if lo > prev_high:
            last_gap = GapEvent(
                kind="GAP_UP",
                date=_to_date_str(df.index[i]),
                prev_date=_to_date_str(df.index[i - 1]),
                lower=prev_high,  # up_gap_bottom
                upper=lo,  # up_gap_upper
            )
            last_i = i

        # strict gap_down
        elif hi < prev_low:
            last_gap = GapEvent(
                kind="GAP_DOWN",
                date=_to_date_str(df.index[i]),
                prev_date=_to_date_str(df.index[i - 1]),
                lower=hi,  # down_gap_bottom
                upper=prev_low,  # down_gap_top
            )
            last_i = i

    if last_gap is None or last_i is None:
        return GapStatus(
            last_gap=None,
            lookback_days=int(lookback_days),
            is_expired=None,
            is_filled_by_close=None,
            fill_date_by_close=None,
            fill_close_by_close=None,
            reclaim_level=None,
        )

    # expiration
    latest_date = pd.Timestamp(df.index[-1]).date()
    gap_date = pd.Timestamp(df.index[last_i]).date()
    is_expired = (latest_date - gap_date).days > int(lookback_days)
    if is_expired:
        return GapStatus(
            last_gap=None,
            lookback_days=int(lookback_days),
            is_expired=True,
            is_filled_by_close=None,
            fill_date_by_close=None,
            fill_close_by_close=None,
            reclaim_level=None,
        )

    is_filled_by_close = False
    fill_date_by_close: str | None = None
    fill_close_by_close: float | None = None

    if last_gap.kind == "GAP_UP":
        fill_level = float(last_gap.lower)  # up_gap_bottom
        reclaim_level = float(last_gap.upper)  # up_gap_upper
        for j in range(last_i + 1, len(df)):
            c = float(df["Close"].iloc[j])
            if c <= fill_level:
                is_filled_by_close = True
                fill_date_by_close = _to_date_str(df.index[j])
                fill_close_by_close = c
                break
    else:
        fill_level = float(last_gap.upper)  # down_gap_top
        reclaim_level = None
        for j in range(last_i + 1, len(df)):
            c = float(df["Close"].iloc[j])
            if c >= fill_level:
                is_filled_by_close = True
                fill_date_by_close = _to_date_str(df.index[j])
                fill_close_by_close = c
                break

    return GapStatus(
        last_gap=last_gap,
        lookback_days=int(lookback_days),
        is_expired=False,
        is_filled_by_close=is_filled_by_close,
        fill_date_by_close=fill_date_by_close,
        fill_close_by_close=fill_close_by_close,
        reclaim_level=reclaim_level,
    )


def detect_island_reversal(
    hist: pd.DataFrame,
    gap_threshold: float = 0.003,
    min_separation_days: int = 2,
    max_separation_days: int = 10,
    lookback_days: int = 120,
) -> IslandReversal | None:
    """Detect simplified island reversal using strict gaps.

    Spec intent:
    - After an upward gap, a downward gap appears shortly after (island), forming a sell/stop warning.

    Rules (strict, no threshold):
    - GAP_UP at t if Low[t] > High[t-1]
    - GAP_DOWN at s if High[s] < Low[s-1]

    Note: gap_threshold is ignored (kept for backward compatibility with callers).
    """
    _ = gap_threshold

    if hist is None or hist.empty or not _required_columns(hist):
        return None

    df = hist[["Open", "High", "Low", "Close", "Volume"]].astype(float).tail(max(int(lookback_days) + 2, 20)).copy()
    if len(df) < 3:
        return None

    df.index = pd.to_datetime(df.index)
    highs = df["High"].to_numpy()
    lows = df["Low"].to_numpy()

    latest: IslandReversal | None = None

    for i in range(1, len(df) - 1):
        prev_high = float(highs[i - 1])
        lo = float(lows[i])
        if not (lo > prev_high):
            continue

        gap_up = GapEvent(
            kind="GAP_UP",
            date=_to_date_str(df.index[i]),
            prev_date=_to_date_str(df.index[i - 1]),
            lower=prev_high,
            upper=lo,
        )

        start_j = i + int(min_separation_days)
        end_j = min(len(df) - 1, i + int(max_separation_days))
        if start_j >= len(df):
            continue

        for j in range(start_j, end_j + 1):
            prev_low = float(lows[j - 1])
            hi = float(highs[j])
            if not (hi < prev_low):
                continue

            gap_down = GapEvent(
                kind="GAP_DOWN",
                date=_to_date_str(df.index[j]),
                prev_date=_to_date_str(df.index[j - 1]),
                lower=hi,
                upper=prev_low,
            )

            # overlap/return into prior gap zone
            if float(gap_down.upper) >= float(gap_up.lower):
                latest = IslandReversal(start_gap_up=gap_up, end_gap_down=gap_down)

    return latest


def gap_reclaim_within_3_days(gap: GapStatus, hist: pd.DataFrame) -> ReclaimSignal:
    """假跌破收復 (buy): after a GAP_UP is filled-by-close, within 3 trading days close reclaims gap upper edge."""
    if gap.last_gap is None or gap.is_filled_by_close is None:
        return ReclaimSignal(is_reclaim=None, reclaim_date=None, days_since_fill=None, reclaim_level=None)

    if hist is None or hist.empty or not _required_columns(hist):
        return ReclaimSignal(is_reclaim=None, reclaim_date=None, days_since_fill=None, reclaim_level=None)

    if gap.is_filled_by_close is not True:
        return ReclaimSignal(is_reclaim=False, reclaim_date=None, days_since_fill=None, reclaim_level=None)

    if gap.fill_date_by_close is None:
        return ReclaimSignal(is_reclaim=None, reclaim_date=None, days_since_fill=None, reclaim_level=None)

    if gap.last_gap.kind != "GAP_UP":
        return ReclaimSignal(is_reclaim=False, reclaim_date=None, days_since_fill=None, reclaim_level=None)

    reclaim_level = float(gap.last_gap.upper)

    df = hist[["Close"]].astype(float).copy()
    df.index = pd.to_datetime(df.index)

    fill_date_iso = pd.Timestamp(gap.fill_date_by_close).date().isoformat()
    fill_pos = None
    for i, idx in enumerate(df.index):
        if pd.Timestamp(idx).date().isoformat() == fill_date_iso:
            fill_pos = i
            break

    if fill_pos is None:
        return ReclaimSignal(is_reclaim=None, reclaim_date=None, days_since_fill=None, reclaim_level=reclaim_level)

    for d in range(1, 4):
        j = fill_pos + d
        if j >= len(df):
            break
        if float(df["Close"].iloc[j]) >= reclaim_level:
            return ReclaimSignal(
                is_reclaim=True,
                reclaim_date=_to_date_str(df.index[j]),
                days_since_fill=d,
                reclaim_level=reclaim_level,
            )

    return ReclaimSignal(is_reclaim=False, reclaim_date=None, days_since_fill=None, reclaim_level=reclaim_level)
def midpoint_defense(hist: pd.DataFrame, *, body_ratio_min: float = 0.6) -> MidpointDefense:
    """Compute midpoint defense level from the latest strong red candle."""
    if hist is None or hist.empty or not _required_columns(hist):
        return MidpointDefense(midpoint=None, date=None, is_broken=None)

    df = hist[["Open", "High", "Low", "Close"]].astype(float).copy()
    df.index = pd.to_datetime(df.index)

    hit_i: int | None = None
    for i in range(len(df) - 1, -1, -1):
        o = float(df["Open"].iloc[i])
        h = float(df["High"].iloc[i])
        l = float(df["Low"].iloc[i])
        c = float(df["Close"].iloc[i])

        rng = h - l
        if rng <= 0:
            continue
        if not (c > o):
            continue

        body_ratio = (c - o) / rng
        if body_ratio >= float(body_ratio_min):
            hit_i = i
            break

    if hit_i is None:
        return MidpointDefense(midpoint=None, date=None, is_broken=None)

    h = float(df["High"].iloc[hit_i])
    l = float(df["Low"].iloc[hit_i])
    midpoint = (h + l) / 2.0

    c_latest = float(df["Close"].iloc[-1])
    is_broken = c_latest < midpoint

    return MidpointDefense(midpoint=midpoint, date=_to_date_str(df.index[hit_i]), is_broken=is_broken)




def bearish_omens(hist: pd.DataFrame, vol_avg_window: int = 20) -> BearishOmens:
    """凶多吉少 detectors (minimal deterministic set)."""
    if hist is None or hist.empty or not _required_columns(hist):
        return BearishOmens(long_black_engulf=None, price_up_vol_down=None, distribution_day=None)

    df = hist[["Open", "High", "Low", "Close", "Volume"]].astype(float).copy()
    if len(df) < 2:
        return BearishOmens(long_black_engulf=None, price_up_vol_down=None, distribution_day=None)

    o0, h0, l0, c0 = (float(df[x].iloc[-1]) for x in ("Open", "High", "Low", "Close"))
    o1, c1 = (float(df[x].iloc[-2]) for x in ("Open", "Close"))

    rng0 = h0 - l0
    body0 = o0 - c0
    long_black = (c0 < o0) and (rng0 > 0) and ((body0 / rng0) >= 0.6)
    engulf = (c0 < o1) and (o0 > c1)
    long_black_engulf = bool(long_black and engulf)

    price_up_vol_down = bool((c0 > c1) and (float(df["Volume"].iloc[-1]) < float(df["Volume"].iloc[-2])))

    vavg = df["Volume"].rolling(window=int(vol_avg_window), min_periods=int(vol_avg_window)).mean().shift(1)
    vavg_latest = float(vavg.iloc[-1]) if pd.notna(vavg.iloc[-1]) else None
    distribution_day = bool((c0 < c1) and (vavg_latest is not None) and (float(df["Volume"].iloc[-1]) >= 1.2 * vavg_latest))

    return BearishOmens(
        long_black_engulf=long_black_engulf,
        price_up_vol_down=price_up_vol_down,
        distribution_day=distribution_day,
    )


def massive_volume_levels(
    hist: pd.DataFrame,
    lookback_days: int = 20,
) -> MassiveVolumeLevel:
    """爆量K棒防守/壓力：lookback_days 內最高量。

    - massive_vol: Volume[i] == max(Volume over past lookback_days, inclusive)
    - Low_broken: Close < massive_low
    - High_broken: Close > massive_high
    """
    if hist is None or hist.empty or not _required_columns(hist):
        return MassiveVolumeLevel(
            is_massive=None,
            low=None,
            high=None,
            date=None,
            vol_today=None,
            vol_max_lookback=None,
            lookback_days=int(lookback_days),
            low_broken=None,
            high_broken=None,
        )

    df = hist[["High", "Low", "Close", "Volume"]].astype(float).copy()
    df.index = pd.to_datetime(df.index)

    n = int(lookback_days)
    if len(df) < n:
        return MassiveVolumeLevel(
            is_massive=None,
            low=None,
            high=None,
            date=None,
            vol_today=float(df["Volume"].iloc[-1]) if len(df) else None,
            vol_max_lookback=None,
            lookback_days=n,
            low_broken=None,
            high_broken=None,
        )

    vmax = df["Volume"].rolling(window=n, min_periods=n).max()

    latest_hit_i: int | None = None
    for i in range(n - 1, len(df)):
        vol_today = float(df["Volume"].iloc[i])
        vol_max = float(vmax.iloc[i]) if pd.notna(vmax.iloc[i]) else None
        if vol_max is None:
            continue
        if vol_today == vol_max:
            latest_hit_i = i

    if latest_hit_i is None:
        return MassiveVolumeLevel(
            is_massive=False,
            low=None,
            high=None,
            date=_to_date_str(df.index[-1]),
            vol_today=float(df["Volume"].iloc[-1]),
            vol_max_lookback=float(vmax.iloc[-1]) if pd.notna(vmax.iloc[-1]) else None,
            lookback_days=n,
            low_broken=False,
            high_broken=False,
        )

    low = float(df["Low"].iloc[latest_hit_i])
    high = float(df["High"].iloc[latest_hit_i])
    c_latest = float(df["Close"].iloc[-1])

    return MassiveVolumeLevel(
        is_massive=True,
        low=low,
        high=high,
        date=_to_date_str(df.index[latest_hit_i]),
        vol_today=float(df["Volume"].iloc[latest_hit_i]),
        vol_max_lookback=float(vmax.iloc[latest_hit_i]) if pd.notna(vmax.iloc[latest_hit_i]) else None,
        lookback_days=n,
        low_broken=(c_latest < low),
        high_broken=(c_latest > high),
    )


# Back-compat wrapper name (deprecated but kept)

def volume_spike_defense_price(
    hist: pd.DataFrame,
    vol_avg_window: int = 20,
    spike_mult: float = 2.0,
) -> MassiveVolumeLevel:
    _ = (spike_mult,)
    return massive_volume_levels(hist, lookback_days=int(vol_avg_window))
