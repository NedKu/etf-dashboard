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
    island_reversal: bool | None = None,
    vol_spike_defense_broken: bool | None = None,
) -> float | None:
    """Step-ladder win-rate W (0.8/0.6/0.4/0.2) used in Kelly.

    Evidence-first:
    - If the core trend/volume fields are missing, return None.

    Ladder (simplified, tunable):
    - 0.80: multi-signal bullish resonance
      (BULL trend + 三陽開泰 + vol_ratio>=1.0 + bias60>=0 + NO island reversal + (gap not open))
    - 0.60: bullish
      (BULL trend + (三陽開泰 or vol_ratio>=1.5) + NO island reversal)
    - 0.40: mixed / neutral
      (default when not strong bull, but not hard bear)
    - 0.20: bearish / risk-off
      (island reversal OR open gap-down OR defense broken OR (BEAR trend and ma20_slope<0))

    Notes:
    - gap_open/gap_filled refer to the *latest gap* status (open means not filled).
    - vol_spike_defense_broken means price < defense_price.
    """
    if None in (p_now, ma150, vol_ratio, ma20_slope, san_yang):
        return None

    bull = p_now > ma150
    bear = p_now <= ma150

    open_gap = (gap_open is True) and (gap_filled is False)

    # Hard risk-off conditions
    if (island_reversal is True) or (vol_spike_defense_broken is True) or (bear and ma20_slope < 0):
        return 0.20

    # If latest gap is an open GAP_DOWN, treat as risk-off (caller should map this into gap_open/gap_filled)
    if open_gap and (gap_open is True):
        # still allow caller to differentiate up/down elsewhere; conservative default
        return 0.20

    bias_ok = (bias60 is not None) and (bias60 >= 0)
    no_island = island_reversal is not True
    not_open_gap = not open_gap

    if bull and (san_yang is True) and (vol_ratio >= 1.0) and bias_ok and no_island and not_open_gap:
        return 0.80

    if bull and no_island and ((san_yang is True) or (vol_ratio >= 1.5) or bias_ok):
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
