from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VolumeSignal:
    vol_ratio: float | None
    is_attack: bool
    is_distribution: bool
    label: str


def volume_signal(vol_today: float | None, vol_avg: float | None, open_: float | None, close: float | None) -> VolumeSignal:
    if vol_today is None or vol_avg is None or vol_avg == 0:
        return VolumeSignal(vol_ratio=None, is_attack=False, is_distribution=False, label="MISSING")

    ratio = float(vol_today) / float(vol_avg)

    is_red = (open_ is not None and close is not None and close > open_)
    is_black = (open_ is not None and close is not None and close < open_)

    attack = ratio > 1.5 and is_red
    distribution = ratio > 2.5 and is_black

    if attack:
        label = "攻擊量"
    elif distribution:
        label = "出貨量"
    elif ratio >= 1.0:
        label = "放量"
    else:
        label = "量縮"

    return VolumeSignal(vol_ratio=ratio, is_attack=attack, is_distribution=distribution, label=label)


def san_yang_kai_tai(ma5: float | None, ma10: float | None, ma20: float | None, ma20_slope: float | None) -> bool | None:
    if None in (ma5, ma10, ma20, ma20_slope):
        return None
    return (ma5 > ma10 > ma20) and (ma20_slope > 0)


def trend_regime(p_now: float | None, ma150: float | None) -> str:
    if p_now is None or ma150 is None:
        return "MISSING"
    return "BULL" if p_now > ma150 else "BEAR"


def choose_win_rate(
    p_now: float | None,
    ma150: float | None,
    vol_ratio: float | None,
    ma20_slope: float | None,
    san_yang: bool | None,
    *,
    bias60: float | None = None,
    gap_open: bool | None = None,
    gap_filled: bool | None = None,
    gap_filled_by_close: bool | None = None,
    island_reversal: bool | None = None,
    vol_spike_defense_broken: bool | None = None,
    bearish_long_black_engulf: bool | None = None,
    bearish_distribution_day: bool | None = None,
    bearish_price_up_vol_down: bool | None = None,
) -> float | None:
    """Step-ladder win-rate W (0.8/0.6/0.4/0.2) used in Kelly.

    Evidence-first:
    - If the core trend/volume fields are missing, return None.

    Full-spec alignment (closest deterministic mapping to your spec):
    - 0.80 (三方共振): bull trend + 三陽開泰 + vol_ratio>1.5 + bias60<10 + (latest gap not filled-by-close)
      Note: N字突破 is not explicitly detected yet; we use「攻擊量」as a proxy for now.
    - 0.60 (偏多): bull trend + (三陽開泰 or vol_ratio>=1.5 or bias60<15) + no hard risk flags
    - 0.40 (分歧): default when not strong bull, but no hard risk flags
    - 0.20 (轉空): any hard risk flag true
      - island_reversal
      - gap_filled_by_close
      - vol_spike_defense_broken
      - bearish omens (engulf / distribution_day)
      - bear trend + ma20_slope<0

    Notes:
    - gap_open/gap_filled are legacy intraday gap status.
    - gap_filled_by_close is the 收盤價準則 status.
    """
    if None in (p_now, ma150, vol_ratio, ma20_slope, san_yang):
        return None

    bull = p_now > ma150
    bear = p_now <= ma150

    open_gap = (gap_open is True) and (gap_filled is False)

    any_bearish_omen = (bearish_long_black_engulf is True) or (bearish_distribution_day is True)

    # Hard risk-off conditions (W=0.2)
    if (
        (island_reversal is True)
        or (gap_filled_by_close is True)
        or (vol_spike_defense_broken is True)
        or any_bearish_omen
        or (bear and ma20_slope < 0)
    ):
        return 0.20

    # Conservative: open gap treated as risk-off until we classify up/down in the caller
    if open_gap:
        return 0.20

    bias_safe = (bias60 is not None) and (bias60 < 10)
    bias_ok = (bias60 is not None) and (bias60 < 15)

    if bull and (san_yang is True) and (vol_ratio > 1.5) and bias_safe and (gap_filled_by_close is not True):
        return 0.80

    if bull and ((san_yang is True) or (vol_ratio >= 1.5) or bias_ok):
        return 0.60

    return 0.40


@dataclass(frozen=True)
class KellyPlan:
    w: float
    entry: float
    stop: float
    target: float
    r: float
    f_raw: float
    f_capped: float
    target_mode: str  # 'P_HIGH' or 'R2'


def kelly(entry: float, stop: float, target: float, w: float, cap: float = 0.25) -> KellyPlan:
    if entry <= stop:
        raise ValueError("entry must be > stop")
    if target <= entry:
        raise ValueError("target must be > entry")

    r = (target - entry) / (entry - stop)
    f = (w * (r + 1.0) - 1.0) / r
    f_capped = max(0.0, min(float(cap), float(f)))
    return KellyPlan(w=w, entry=entry, stop=stop, target=target, r=r, f_raw=f, f_capped=f_capped, target_mode="")
