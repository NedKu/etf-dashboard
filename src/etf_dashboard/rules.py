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
    ma50: float | None,
    ma200: float | None,
    vol_ratio: float | None,
    ma20_slope: float | None,
    san_yang: bool | None,
    *,
    rsi14: float | None = None,
    rule_35_zone: str | None = None,
    bias60: float | None = None,
    gap_open: bool | None = None,
    gap_filled: bool | None = None,
    gap_filled_by_close: bool | None = None,
    gap_direction_by_close: str | None = None,  # 'UP' | 'DOWN' | 'UNKNOWN'
    island_reversal: bool | None = None,
    vol_spike_defense_broken: bool | None = None,
    bearish_long_black_engulf: bool | None = None,
    bearish_distribution_day: bool | None = None,
    bearish_price_up_vol_down: bool | None = None,
) -> float | None:
    """Base+Bonus+Penalty win-rate W used in Kelly.

    Your updated spec:
    - Step 1 Base W
      - Bull: Close > MA150 AND MA50 > MA200 => base=0.60
      - Bear: Close < MA150 OR MA50 <= MA200 => base=0.30

    - Step 2 Bonus
      - 三方共振 +0.10: 三陽開泰
      - 價值回歸 +0.30: rule_35_zone == 'GOLD' and RSI<30
      - 多頭動能 +0.10: vol_ratio>1 and bias60<10
      - 收盤封閉向下跳空的缺口 +0.10: gap_filled_by_close and gap_direction_by_close=='DOWN'

    - Step 3 Penalty (no longer veto)
      - 島狀反轉 -0.10
      - 收盤封閉向上跳空的缺口 -0.10: gap_filled_by_close and gap_direction_by_close=='UP'
      - 爆量防守跌破 -0.10
      - 凶多吉少 -0.20: engulf or distribution_day

    - Step 4 Clamp: W in [0.15, 0.85]

    Evidence-first:
    - If core inputs are missing, return None.
    """

    if None in (p_now, ma150, ma50, ma200, vol_ratio, ma20_slope, san_yang):
        return None

    bull = (p_now > ma150) and (ma50 > ma200)
    bear = (p_now <= ma150) or (ma50 <= ma200)

    # By definition above, mixed signals still count as bear base.
    base_w = 0.60 if bull else 0.30 if bear else 0.30

    w = base_w

    # Bonus: 三方共振
    if san_yang is True:
        w += 0.10

    # Bonus: 價值回歸
    if (rule_35_zone == "GOLD") and (rsi14 is not None) and (rsi14 < 30):
        w += 0.30

    # Bonus: 多頭動能
    # Only applies when the base regime is bull.
    if bull and (bias60 is not None) and (vol_ratio > 1.0) and (bias60 < 10):
        w += 0.10

    # Gap-related bonus/penalty
    if gap_filled_by_close is True:
        if gap_direction_by_close == "DOWN":
            w += 0.10
        elif gap_direction_by_close == "UP":
            w -= 0.10

    # Penalty: island reversal
    if island_reversal is True:
        w -= 0.10

    # Penalty: massive volume defense broken
    if vol_spike_defense_broken is True:
        w -= 0.10

    # Penalty: bearish omens
    any_bearish_omen = (bearish_long_black_engulf is True) or (bearish_distribution_day is True)
    if any_bearish_omen:
        w -= 0.20

    # Conservative legacy intraday open gap remains risk-off signal.
    # Kept as a small penalty (not veto) to match the "not one-vote veto" philosophy.
    open_gap = (gap_open is True) and (gap_filled is False)
    if open_gap:
        w -= 0.10

    # Clamp + stabilize float rounding
    w = float(round(w, 4))

    if w < 0.15:
        return 0.15
    if w > 0.85:
        return 0.85
    return w


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
