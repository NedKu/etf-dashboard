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
) -> float | None:
    """Heuristic win-rate W used in Kelly.

    Evidence-first: if any required inputs are missing, return None.

    Rough mapping (tunable):
    - Bear trend and falling MA20: 0.30
    - Bull trend + 三陽開泰 + at least average volume: 0.70
    - Bull trend + strong volume expansion: 0.65
    - Otherwise: 0.45
    """
    if None in (p_now, ma150, vol_ratio, ma20_slope, san_yang):
        return None

    if (p_now < ma150) and (ma20_slope < 0):
        return 0.30

    # Bull + 三陽開泰 (trend alignment) + not "dry" volume
    if (p_now > ma150) and (san_yang is True) and (vol_ratio >= 1.0):
        return 0.70

    # "順勢帶量"
    if (p_now > ma150) and (vol_ratio >= 1.5):
        return 0.65

    # "逆勢或無量"
    if (p_now <= ma150) or (vol_ratio < 1.0):
        return 0.45

    return 0.45


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
