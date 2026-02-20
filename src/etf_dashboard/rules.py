from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


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


def san_sheng_wu_nai(
    p_now: float | None,
    ma5: float | None,
    ma10: float | None,
    ma20: float | None,
    ma5_slope: float | None,
    ma10_slope: float | None,
    ma20_slope: float | None,
) -> bool | None:
    """三聲無奈 (bearish):

    Spec (per user):
    - MA5/MA10/MA20 slopes are all down
    - Bearish alignment: MA20 > MA10 > MA5
    - Price below all three MAs

    Missing policy: if any required input is None => return None.
    """

    if None in (p_now, ma5, ma10, ma20, ma5_slope, ma10_slope, ma20_slope):
        return None

    slopes_down = (ma5_slope < 0) and (ma10_slope < 0) and (ma20_slope < 0)
    bearish_align = (ma20 > ma10 > ma5)
    price_below = (p_now < ma5) and (p_now < ma10) and (p_now < ma20)

    return bool(slopes_down and bearish_align and price_below)


def trend_regime(p_now: float | None, ma150: float | None) -> str:
    if p_now is None or ma150 is None:
        return "MISSING"
    return "BULL" if p_now > ma150 else "BEAR"


class WinRateComponentStatus(str, Enum):
    APPLIED = "APPLIED"
    NOT_APPLIED = "NOT_APPLIED"
    SKIPPED_MISSING = "SKIPPED_MISSING"


class WinRateComponentKind(str, Enum):
    BASE = "BASE"
    BONUS = "BONUS"
    PENALTY = "PENALTY"


@dataclass(frozen=True)
class WinRateComponent:
    kind: WinRateComponentKind
    name: str
    delta: float
    status: WinRateComponentStatus
    missing_fields: tuple[str, ...] = ()
    note: str | None = None


@dataclass(frozen=True)
class WinRateBreakdown:
    base: float | None
    bonus_total: float
    penalty_total: float
    w_raw: float | None
    w_clamped: float | None
    clamp_min: float = 0.15
    clamp_max: float = 0.85
    components: tuple[WinRateComponent, ...] = ()


def _missing(*pairs: tuple[str, object | None]) -> tuple[str, ...]:
    return tuple(name for name, val in pairs if val is None)


def choose_win_rate_breakdown(
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
    island_reversal_bearish: bool | None = None,
    island_reversal_bullish: bool | None = None,
    vol_spike_defense_broken: bool | None = None,
    bearish_long_black_engulf: bool | None = None,
    bearish_distribution_day: bool | None = None,
    bearish_price_up_vol_down: bool | None = None,
    san_sheng_wu_nai: bool | None = None,
    clamp_min: float = 0.15,
    clamp_max: float = 0.85,
) -> WinRateBreakdown:
    """Explainable Base+Bonus+Penalty win-rate W used in Kelly.

    Policy (per user confirmation):
    - Base must be computable; if base inputs missing => W=MISSING.
    - Each bonus/penalty rule with missing inputs is treated as 0 impact,
      but we record it as SKIPPED_MISSING with missing field names.
    - Final W is clamped to [clamp_min, clamp_max].
    """

    components: list[WinRateComponent] = []

    base_missing = _missing(("p_now", p_now), ("ma150", ma150), ("ma50", ma50), ("ma200", ma200))
    if base_missing:
        components.append(
            WinRateComponent(
                kind=WinRateComponentKind.BASE,
                name="趨勢多空(Base)",
                delta=0.0,
                status=WinRateComponentStatus.SKIPPED_MISSING,
                missing_fields=base_missing,
                note="Base 無法判斷，W=MISSING",
            )
        )
        return WinRateBreakdown(
            base=None,
            bonus_total=0.0,
            penalty_total=0.0,
            w_raw=None,
            w_clamped=None,
            clamp_min=clamp_min,
            clamp_max=clamp_max,
            components=tuple(components),
        )

    assert p_now is not None and ma150 is not None and ma50 is not None and ma200 is not None

    bull = (p_now > ma150) and (ma50 > ma200)
    base_w = 0.60 if bull else 0.30
    components.append(
        WinRateComponent(
            kind=WinRateComponentKind.BASE,
            name="趨勢多空(Base)",
            delta=base_w,
            status=WinRateComponentStatus.APPLIED,
            note="Bull: P_now>MA150 且 MA50>MA200" if bull else "Bear: 其餘情況",
        )
    )

    bonus_total = 0.0
    penalty_total = 0.0

    def add_rule(
        *,
        kind: WinRateComponentKind,
        name: str,
        delta_if_true: float,
        cond: bool | None,
        missing_fields: tuple[str, ...] = (),
        note: str | None = None,
    ) -> None:
        nonlocal bonus_total, penalty_total

        if missing_fields:
            components.append(
                WinRateComponent(
                    kind=kind,
                    name=name,
                    delta=0.0,
                    status=WinRateComponentStatus.SKIPPED_MISSING,
                    missing_fields=missing_fields,
                    note=note,
                )
            )
            return

        applied = (cond is True)
        if applied:
            components.append(
                WinRateComponent(
                    kind=kind,
                    name=name,
                    delta=delta_if_true,
                    status=WinRateComponentStatus.APPLIED,
                    note=note,
                )
            )
            if kind == WinRateComponentKind.BONUS:
                bonus_total += float(delta_if_true)
            elif kind == WinRateComponentKind.PENALTY:
                penalty_total += float(delta_if_true)
            return

        components.append(
            WinRateComponent(
                kind=kind,
                name=name,
                delta=0.0,
                status=WinRateComponentStatus.NOT_APPLIED,
                note=note,
            )
        )

    # Bonus: 三方共振 +0.10
    add_rule(
        kind=WinRateComponentKind.BONUS,
        name="三方共振(三陽開泰)",
        delta_if_true=0.10,
        cond=(san_yang is True),
        missing_fields=_missing(("san_yang", san_yang)),
    )

    # Bonus: 價值回歸 +0.20 (GOLD + RSI<30)
    add_rule(
        kind=WinRateComponentKind.BONUS,
        name="價值回歸(35法則GOLD + RSI<30)",
        delta_if_true=0.20,
        cond=(rule_35_zone == "GOLD") and (rsi14 is not None) and (rsi14 < 30),
        missing_fields=_missing(("rule_35_zone", rule_35_zone), ("rsi14", rsi14)),
    )

    # Bonus: 多頭動能 +0.10 (bull & vol_ratio>1 & bias60<10)
    # vol_ratio is a base-required input in old signature, but still treat as missing-aware here.
    add_rule(
        kind=WinRateComponentKind.BONUS,
        name="多頭動能(bull + 放量 + BIAS60<10)",
        delta_if_true=0.10,
        cond=bull and (vol_ratio is not None) and (vol_ratio > 1.0) and (bias60 is not None) and (bias60 < 10),
        missing_fields=_missing(("vol_ratio", vol_ratio), ("bias60", bias60)),
        note="僅在 Bull base 生效" if bull else "Bear base 不加分",
    )

    # Gap close direction: +0.10 if DOWN, -0.10 if UP
    add_rule(
        kind=WinRateComponentKind.BONUS,
        name="缺口收盤封閉(向下跳空)",
        delta_if_true=0.10,
        cond=(gap_filled_by_close is True) and (gap_direction_by_close == "DOWN"),
        missing_fields=_missing(("gap_filled_by_close", gap_filled_by_close), ("gap_direction_by_close", gap_direction_by_close)),
    )
    add_rule(
        kind=WinRateComponentKind.PENALTY,
        name="缺口收盤封閉(向上跳空)",
        delta_if_true=-0.10,
        cond=(gap_filled_by_close is True) and (gap_direction_by_close == "UP"),
        missing_fields=_missing(("gap_filled_by_close", gap_filled_by_close), ("gap_direction_by_close", gap_direction_by_close)),
    )

    # Penalty: bearish island reversal -0.10 (頂部島狀反轉)
    add_rule(
        kind=WinRateComponentKind.PENALTY,
        name="頂部島狀反轉",
        delta_if_true=-0.10,
        cond=(island_reversal_bearish is True),
        missing_fields=_missing(("island_reversal_bearish", island_reversal_bearish)),
    )

    # Bonus: bullish island reversal +0.10 (底部島狀反轉)
    add_rule(
        kind=WinRateComponentKind.BONUS,
        name="底部島狀反轉",
        delta_if_true=0.10,
        cond=(island_reversal_bullish is True),
        missing_fields=_missing(("island_reversal_bullish", island_reversal_bullish)),
    )

    # Penalty: massive volume defense broken -0.10
    add_rule(
        kind=WinRateComponentKind.PENALTY,
        name="爆量防守跌破",
        delta_if_true=-0.10,
        cond=(vol_spike_defense_broken is True),
        missing_fields=_missing(("vol_spike_defense_broken", vol_spike_defense_broken)),
    )

    # Penalty: 凶多吉少 -0.10 (一記重錘破三線)
    # Spec (per user): long black K + Close below MA5/10/20.
    add_rule(
        kind=WinRateComponentKind.PENALTY,
        name="凶多吉少(長黑破三線)",
        delta_if_true=-0.10,
        cond=(bearish_long_black_engulf is True),
        missing_fields=_missing(("bearish_long_black_engulf", bearish_long_black_engulf)),
        note="定義：長黑K且收盤價同時跌破 MA5/MA10/MA20",
    )

    # Penalty: 三聲無奈 -0.10
    add_rule(
        kind=WinRateComponentKind.PENALTY,
        name="三聲無奈",
        delta_if_true=-0.10,
        cond=(san_sheng_wu_nai is True),
        missing_fields=_missing(("san_sheng_wu_nai", san_sheng_wu_nai)),
    )

    # Penalty: open gap not filled -0.10
    add_rule(
        kind=WinRateComponentKind.PENALTY,
        name="開盤缺口未封閉(保守風險)",
        delta_if_true=-0.10,
        cond=(gap_open is True) and (gap_filled is False),
        missing_fields=_missing(("gap_open", gap_open), ("gap_filled", gap_filled)),
    )

    w_raw = float(round(base_w + bonus_total + penalty_total, 4))
    w_clamped = w_raw
    if w_clamped < clamp_min:
        w_clamped = clamp_min
    if w_clamped > clamp_max:
        w_clamped = clamp_max

    return WinRateBreakdown(
        base=base_w,
        bonus_total=float(round(bonus_total, 4)),
        penalty_total=float(round(penalty_total, 4)),
        w_raw=w_raw,
        w_clamped=float(round(w_clamped, 4)),
        clamp_min=clamp_min,
        clamp_max=clamp_max,
        components=tuple(components),
    )


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
    # Backward-compat: legacy signature only provided a single island_reversal boolean.
    # Treat it as bearish (penalty) to preserve prior behavior.
    return choose_win_rate_breakdown(
        p_now,
        ma150,
        ma50,
        ma200,
        vol_ratio,
        ma20_slope,
        san_yang,
        rsi14=rsi14,
        rule_35_zone=rule_35_zone,
        bias60=bias60,
        gap_open=gap_open,
        gap_filled=gap_filled,
        gap_filled_by_close=gap_filled_by_close,
        gap_direction_by_close=gap_direction_by_close,
        island_reversal_bearish=island_reversal,
        island_reversal_bullish=None,
        vol_spike_defense_broken=vol_spike_defense_broken,
        bearish_long_black_engulf=bearish_long_black_engulf,
        bearish_distribution_day=bearish_distribution_day,
        bearish_price_up_vol_down=bearish_price_up_vol_down,
    ).w_clamped


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
