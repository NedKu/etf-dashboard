from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .data_yahoo import (
    fetch_snapshot,
    yahoo_history_url,
    yahoo_quote_url,
)
from .indicators import latest_value, macd, pct, rsi, sma
from .laowang import (
    bearish_omens,
    detect_island_reversal,
    detect_last_gap,
    gap_reclaim_within_3_days,
    massive_volume_levels,
)
from .report_md import ReportInputs, render_report_md
from .rules import choose_win_rate, san_yang_kai_tai, trend_regime, volume_signal


@dataclass(frozen=True)
class Derived:
    p_now: float | None
    open_: float | None
    close: float | None
    ma5: float | None
    ma10: float | None
    ma20: float | None
    ma50: float | None
    ma60: float | None
    ma150: float | None
    ma200: float | None
    bias60: float | None
    ma20_slope: float | None
    v_today: float | None
    v_avg: float | None
    rsi14: float | None
    macd: float | None
    macd_signal: float | None
    macd_hist: float | None

    # Risk controls / patterns
    trailing_stop: float | None
    trailing_stop_hit: bool | None

    # 老王 signals
    gap_kind: str | None
    gap_open: bool | None
    gap_filled: bool | None
    gap_lower: float | None
    gap_upper: float | None

    # 收盤價準則：封閉缺口
    gap_filled_by_close: bool | None
    gap_fill_date_by_close: str | None

    # 假跌破收復
    gap_reclaim_3d: bool | None
    gap_reclaim_date: str | None

    island_reversal: bool | None

    vol_spike: bool | None
    vol_spike_defense: float | None
    vol_spike_resistance: float | None
    vol_spike_defense_broken: bool | None
    vol_spike_resistance_broken: bool | None

    # 凶多吉少
    bearish_long_black_engulf: bool | None
    bearish_price_up_vol_down: bool | None
    bearish_distribution_day: bool | None


def _compute_from_history(
    hist: pd.DataFrame,
    volume_avg_window: int = 20,
    *,
    trailing_stop_pct: float = 0.05,
    gap_threshold: float = 0.0,
    island_min_days: int = 2,
    island_max_days: int = 10,
    laowang_lookback_days: int = 120,
    vol_spike_mult: float = 2.0,
    vol_spike_window: int = 20,
) -> Derived:
    close = hist["Close"].astype(float)
    open_ = hist["Open"].astype(float)

    ma5_s = sma(close, 5)
    ma10_s = sma(close, 10)
    ma20_s = sma(close, 20)
    ma50_s = sma(close, 50)
    ma60_s = sma(close, 60)
    ma150_s = sma(close, 150)
    ma200_s = sma(close, 200)

    bias60_s = (close - ma60_s) / ma60_s * 100.0

    # MA20 slope: today - 5 days ago
    ma20_slope = None
    ma20_clean = ma20_s.dropna()
    if len(ma20_clean) >= 6:
        ma20_slope = float(ma20_clean.iloc[-1] - ma20_clean.iloc[-6])

    v = hist["Volume"].astype(float)
    v_avg_s = v.rolling(window=volume_avg_window, min_periods=volume_avg_window).mean()

    rsi_s = rsi(close, 14)
    macd_df = macd(close, 12, 26, 9)

    p_now = latest_value(close)

    # Trailing stop based on P_high (proxy: 252d High in history "High")
    p_high_hist = None
    if "High" in hist.columns and not hist["High"].dropna().empty:
        last = hist["High"].astype(float).tail(252)
        if not last.dropna().empty:
            p_high_hist = float(last.max())

    trailing_stop = None
    trailing_stop_hit = None
    if p_high_hist is not None:
        trailing_stop = float(p_high_hist) * (1.0 - float(trailing_stop_pct))
        if p_now is not None:
            trailing_stop_hit = float(p_now) < trailing_stop

    # 老王 signals (統一版：嚴格缺口 + 效期 + 收盤封閉)
    gap = detect_last_gap(hist, gap_threshold=float(gap_threshold), lookback_days=int(laowang_lookback_days))
    gap_kind = gap.last_gap.kind if gap.last_gap is not None else None

    gap_open = None
    gap_filled = None
    gap_lower = None
    gap_upper = None

    # Back-compat booleans for existing report/rules wiring
    if gap.last_gap is not None and gap.is_filled_by_close is not None:
        gap_open = not bool(gap.is_filled_by_close)
        gap_filled = bool(gap.is_filled_by_close)
        gap_lower = float(gap.last_gap.lower)
        gap_upper = float(gap.last_gap.upper)

    gap_filled_by_close = gap.is_filled_by_close
    gap_fill_date_by_close = gap.fill_date_by_close

    reclaim = gap_reclaim_within_3_days(gap, hist)
    gap_reclaim_3d = reclaim.is_reclaim
    gap_reclaim_date = reclaim.reclaim_date

    island = detect_island_reversal(
        hist,
        gap_threshold=float(gap_threshold),
        min_separation_days=int(island_min_days),
        max_separation_days=int(island_max_days),
        lookback_days=int(laowang_lookback_days),
    )
    island_reversal = island is not None

    # 爆量防守/壓力 (spec): massive_vol = lookback_days 內最高量
    mv = massive_volume_levels(hist, lookback_days=int(vol_spike_window))
    vol_spike = mv.is_massive
    vol_spike_defense = mv.low
    vol_spike_resistance = mv.high
    vol_spike_defense_broken = mv.low_broken
    vol_spike_resistance_broken = mv.high_broken

    omen = bearish_omens(hist, vol_avg_window=int(vol_spike_window))
    bearish_long_black_engulf = omen.long_black_engulf
    bearish_price_up_vol_down = omen.price_up_vol_down
    bearish_distribution_day = omen.distribution_day

    return Derived(
        p_now=p_now,
        open_=latest_value(open_),
        close=latest_value(close),
        ma5=latest_value(ma5_s),
        ma10=latest_value(ma10_s),
        ma20=latest_value(ma20_s),
        ma50=latest_value(ma50_s),
        ma60=latest_value(ma60_s),
        ma150=latest_value(ma150_s),
        ma200=latest_value(ma200_s),
        bias60=latest_value(bias60_s),
        ma20_slope=ma20_slope,
        v_today=latest_value(v),
        v_avg=latest_value(v_avg_s),
        rsi14=latest_value(rsi_s),
        macd=latest_value(macd_df["macd"]),
        macd_signal=latest_value(macd_df["signal"]),
        macd_hist=latest_value(macd_df["hist"]),
        trailing_stop=trailing_stop,
        trailing_stop_hit=trailing_stop_hit,
        gap_kind=gap_kind,
        gap_open=gap_open,
        gap_filled=gap_filled,
        gap_lower=gap_lower,
        gap_upper=gap_upper,
        gap_filled_by_close=gap_filled_by_close,
        gap_fill_date_by_close=gap_fill_date_by_close,
        gap_reclaim_3d=gap_reclaim_3d,
        gap_reclaim_date=gap_reclaim_date,
        island_reversal=island_reversal,
        vol_spike=vol_spike,
        vol_spike_defense=vol_spike_defense,
        vol_spike_resistance=vol_spike_resistance,
        vol_spike_defense_broken=vol_spike_defense_broken,
        vol_spike_resistance_broken=vol_spike_resistance_broken,
        bearish_long_black_engulf=bearish_long_black_engulf,
        bearish_price_up_vol_down=bearish_price_up_vol_down,
        bearish_distribution_day=bearish_distribution_day,
    )


def _p_high_from_info_or_history(info: dict, hist: pd.DataFrame) -> tuple[float | None, str]:
    # Preferred: Yahoo's 52-week high.
    p_high = info.get("fiftyTwoWeekHigh") if isinstance(info, dict) else None
    if p_high is not None:
        try:
            return float(p_high), "YF_INFO.fiftyTwoWeekHigh"
        except Exception:
            pass

    # Fallback: last 252 trading days high of 'High' column.
    if "High" in hist.columns and not hist["High"].dropna().empty:
        last = hist["High"].astype(float).tail(252)
        if not last.dropna().empty:
            return float(last.max()), "HISTORY_252D_HIGH"

    return None, "MISSING"


def _rule_35_zone(p_now: float | None, p_high: float | None) -> tuple[float | None, float | None, float | None, str]:
    if p_now is None or p_high is None:
        return None, None, None, "MISSING"

    weak = p_high * 0.8
    watch = p_high * 0.7
    gold = p_high * 0.65

    if p_now >= weak:
        zone = "安全區"
    elif p_now >= watch:
        zone = "觀察區"
    elif p_now >= gold:
        zone = "接近抄底區"
    else:
        zone = "跌深區"

    return weak, watch, gold, zone


def _stop_target(
    entry: float | None,
    ma20: float | None,
    p_high: float | None,
    stop_loss_pct: float,
    min_rr: float,
) -> tuple[float | None, float | None, float | None, str, float | None]:
    """Return stop, target, R, target_mode, stop_from_pct.

    Stop-loss policy (explicit, evidence-first):
    - stop_from_pct = entry * (1 - stop_loss_pct)
    - stop = max(MA20, stop_from_pct) if MA20 exists and MA20 < entry else stop_from_pct

    Notes:
    - We use the *higher* (tighter) stop to enforce discipline *when it does not invalidate R*.
    - If MA20 is above entry, using MA20 would make stop >= entry and R/Kelly undefined for long entries.

    Target policy:
    - Prefer P_high as target.
    - If that yields R < min_rr, use MinR target: entry + min_rr*(entry-stop)
    """
    if entry is None:
        return None, None, None, "MISSING", None
    if min_rr < 0:
        raise ValueError("min_rr must be >= 0")

    stop_from_pct = float(entry) * (1.0 - float(stop_loss_pct))

    # If MA20 >= entry, using max(MA20, stop_from_pct) would produce stop>=entry and make R undefined.
    # In that case, ignore MA20 and use stop_from_pct to avoid R=MISSING.
    if ma20 is None:
        stop = stop_from_pct
    else:
        ma20_f = float(ma20)
        stop = stop_from_pct if ma20_f >= float(entry) else max(ma20_f, stop_from_pct)

    if p_high is None:
        return stop, None, None, "MISSING_P_HIGH", stop_from_pct

    target = float(p_high)

    denom = entry - stop
    if denom <= 0:
        return stop, target, None, "INVALID_STOP_GE_ENTRY", stop_from_pct

    r_val = (target - entry) / denom
    # If target <= entry, R becomes <= 0. In this case we still keep the stop value (risk control)
    # but mark R as None so downstream (Kelly/rating) is gated. Report will also include a note.
    if r_val <= 0:
        return stop_from_pct, target, None, "INVALID_TARGET_LE_ENTRY_USE_PCT_STOP", stop_from_pct

    target_mode = "P_HIGH"
    if r_val < float(min_rr):
        target = entry + float(min_rr) * denom
        r_val = float(min_rr)
        target_mode = "MIN_RR"

    return stop, target, float(r_val), target_mode, stop_from_pct


def _final_rating(
    evidence_ok: bool,
    regime: str,
    san_yang: bool | None,
    vol_attack: bool,
    vol_ratio: float | None,
    bench_regime: str,
    kelly_f: float | None,
) -> str:
    if not evidence_ok:
        return "⛔ 資料不足（禁止結論）"

    if kelly_f is not None and kelly_f <= 0:
        return "✋ 觀望"

    if bench_regime != "BULL":
        return "✋ 觀望"

    if regime == "BULL" and san_yang is True and (vol_attack or (vol_ratio is not None and vol_ratio >= 1.2)):
        return "⭐ 強力買進"

    if regime == "BULL":
        return "👀 拉回觀察"

    return "✋ 觀望"


def build_report(
    ticker: str,
    benchmark: str,
    out_dir: Path,
    lookback_days: int,
    volume_avg_window: int,
    stop_loss_pct: float = 0.05,
    min_rr: float = 0.0,
    max_position_pct: float = 0.20,
    *,
    trailing_stop_pct: float = 0.05,
    gap_threshold: float = 0.003,
    island_min_days: int = 2,
    island_max_days: int = 10,
    laowang_lookback_days: int = 120,
    vol_spike_mult: float = 2.0,
    vol_spike_window: int = 20,
) -> Path:
    if not (0.0 < stop_loss_pct < 0.5):
        raise ValueError("stop_loss_pct must be between 0 and 0.5 (e.g., 0.05 for 5%)")
    if not (0.0 < trailing_stop_pct < 0.5):
        raise ValueError("trailing_stop_pct must be between 0 and 0.5 (e.g., 0.05 for 5%)")
    if min_rr < 0:
        raise ValueError("min_rr must be >= 0")
    if not (0.0 < max_position_pct <= 1.0):
        raise ValueError("max_position_pct must be in (0, 1]")

    snap = fetch_snapshot(ticker, lookback_days=lookback_days)
    bench = fetch_snapshot(benchmark, lookback_days=lookback_days)

    d = _compute_from_history(
        snap.history,
        volume_avg_window=volume_avg_window,
        trailing_stop_pct=trailing_stop_pct,
        gap_threshold=gap_threshold,
        island_min_days=island_min_days,
        island_max_days=island_max_days,
        laowang_lookback_days=laowang_lookback_days,
        vol_spike_mult=vol_spike_mult,
        vol_spike_window=vol_spike_window,
    )
    b = _compute_from_history(bench.history, volume_avg_window=volume_avg_window, trailing_stop_pct=trailing_stop_pct)

    p_high, p_high_src = _p_high_from_info_or_history(snap.info, snap.history)

    notes: list[str] = [
        f"P_now/MA/RSI/MACD/均量皆以 Yahoo 日線 history 計算（Close/Volume）。",
        f"P_high 來源：{p_high_src}",
        "BIAS_60 = ((P_now - MA60) / MA60) * 100%",
        f"Trailing stop = P_high × (1 - trailing_stop_pct)；本次 trailing_stop_pct={trailing_stop_pct}",
        "老王：缺口採嚴格定義（Low>前高 / High<前低，不用 gap_threshold）、島狀反轉視窗 2~10 天、爆量=區間最高量。",
        "Kelly 最終倉位受 max_position_pct 上限約束（預設 20%）。",
    ]

    drawdown_pct = None
    if d.p_now is not None and p_high is not None and p_high != 0:
        drawdown_pct = pct(d.p_now, p_high)

    weak, watch, gold, zone = _rule_35_zone(d.p_now, p_high)

    vol = volume_signal(d.v_today, d.v_avg, d.open_, d.close)

    regime = trend_regime(d.p_now, d.ma150)
    bench_regime = trend_regime(b.p_now, b.ma150)

    sy = san_yang_kai_tai(d.ma5, d.ma10, d.ma20, d.ma20_slope)
    sy_str = "MISSING" if sy is None else ("是" if sy else "否")

    stop, target, r_val, target_mode, stop_from_pct = _stop_target(
        d.p_now,
        d.ma20,
        p_high,
        stop_loss_pct=stop_loss_pct,
        min_rr=min_rr,
    )

    if d.p_now is not None and d.ma20 is not None and float(d.ma20) >= float(d.p_now):
        notes.append(
            "注意：MA20 >= entry（P_now），若用 MA20 作止損會導致 stop>=entry 使盈虧比 R 無法計算。"
            "本報告已忽略 MA20 止損、改用 -stop_loss_pct 止損價；請留意此情境下趨勢/風險較特殊。"
        )

    rr_ok = (r_val is not None) and (float(r_val) >= float(min_rr))
    if not rr_ok:
        notes.append(f"盈虧比 R={r_val if r_val is not None else 'MISSING'} < min_rr={min_rr}；依設定不輸出買賣評級。")

    if target_mode == "INVALID_TARGET_LE_ENTRY_USE_PCT_STOP":
        notes.append(
            "注意：計算出來 target <= entry，盈虧比 R 會是 0 或負值；"
            "此時報告將止損價強制採用 -stop_loss_pct 的止損價（entry×(1-stop_loss_pct)），"
            "並禁止輸出買賣評級/凱利倉位。"
        )

    if target_mode == "MIN_RR":
        notes.append(
            f"注意：原本以 P_high 計算之盈虧比 R 小於 Min R/R={min_rr}；"
            "本報告已將預期獲利價 target 調整為由 Min R 推導："
            "target = entry + MinR*(entry-stop)。"
        )

    # Gap direction (by naming convention): contains 'UP'/'DOWN' => UP/DOWN else UNKNOWN
    gap_dir = "UNKNOWN"
    if isinstance(d.gap_kind, str):
        k = d.gap_kind.upper()
        if "UP" in k:
            gap_dir = "UP"
        elif "DOWN" in k:
            gap_dir = "DOWN"

    w = choose_win_rate(
        d.p_now,
        d.ma150,
        d.ma50,
        d.ma200,
        vol.vol_ratio,
        d.ma20_slope,
        sy,
        rsi14=d.rsi14,
        rule_35_zone=zone,
        bias60=d.bias60,
        gap_open=d.gap_open,
        gap_filled=d.gap_filled,
        gap_filled_by_close=d.gap_filled_by_close,
        gap_direction_by_close=gap_dir,
        island_reversal=d.island_reversal,
        vol_spike_defense_broken=d.vol_spike_defense_broken,
        bearish_long_black_engulf=d.bearish_long_black_engulf,
        bearish_distribution_day=d.bearish_distribution_day,
        bearish_price_up_vol_down=d.bearish_price_up_vol_down,
    )
    kelly_f_raw = None
    kelly_f_capped = None
    if None not in (w, d.p_now, stop, target, r_val) and w is not None and stop is not None and target is not None:
        # Kelly f
        f = (w * (r_val + 1.0) - 1.0) / r_val
        kelly_f_raw = float(f)
        kelly_f_capped = max(0.0, min(float(max_position_pct), float(f)))

    # evidence completeness gate
    required = [
        d.p_now,
        d.ma20,
        d.ma60,
        d.ma150,
        d.ma200,
        d.bias60,
        p_high,
        d.v_today,
        d.v_avg,
        d.rsi14,
        d.macd,
        b.p_now,
        b.ma150,
        stop,
        target,
        r_val,
        kelly_f_capped,
        d.trailing_stop,
        d.trailing_stop_hit,
        d.gap_open,
        d.gap_filled,
        d.gap_filled_by_close,
        d.island_reversal,
        d.vol_spike_defense_broken,
        d.bearish_long_black_engulf,
        d.bearish_distribution_day,
        d.bearish_price_up_vol_down,
    ]
    evidence_ok = all(x is not None for x in required)
    if not evidence_ok:
        notes.append("關鍵欄位存在 MISSING（含 R/Kelly 或 stop/target 不可用）；依規則禁止輸出買賣評級。")

    rating = _final_rating(
        evidence_ok=(evidence_ok and rr_ok),
        regime=regime,
        san_yang=sy,
        vol_attack=vol.is_attack,
        vol_ratio=vol.vol_ratio,
        bench_regime=bench_regime,
        kelly_f=kelly_f_capped,
    )

    local_now = datetime.now().astimezone()

    # Re-compute detailed 老王 objects here (report needs dates/levels; Derived keeps booleans/levels only)
    gap = detect_last_gap(snap.history, gap_threshold=float(gap_threshold), lookback_days=int(laowang_lookback_days))
    reclaim = gap_reclaim_within_3_days(gap, snap.history)
    island = detect_island_reversal(
        snap.history,
        gap_threshold=float(gap_threshold),
        min_separation_days=int(island_min_days),
        max_separation_days=int(island_max_days),
        lookback_days=int(laowang_lookback_days),
    )
    mv = massive_volume_levels(snap.history, lookback_days=int(vol_spike_window))

    inp = ReportInputs(
        ticker=ticker,
        name=(snap.info.get("shortName") if isinstance(snap.info, dict) else None),
        report_time_local=local_now.strftime("%Y/%m/%d %H:%M:%S %Z"),
        report_time_utc=snap.asof_utc.strftime("%Y/%m/%d %H:%M:%S UTC"),
        p_now=d.p_now,
        ma5=d.ma5,
        ma10=d.ma10,
        ma20=d.ma20,
        ma50=d.ma50,
        ma60=d.ma60,
        ma150=d.ma150,
        ma200=d.ma200,
        bias60=d.bias60,
        p_high=p_high,
        drawdown_pct=drawdown_pct,
        trailing_stop_pct=trailing_stop_pct,
        trailing_stop=d.trailing_stop,
        trailing_stop_hit=d.trailing_stop_hit,
        gap_kind=d.gap_kind,
        gap_open=d.gap_open,
        gap_filled=d.gap_filled,
        gap_lower=d.gap_lower,
        gap_upper=d.gap_upper,
        gap_last_date=(gap.last_gap.date if gap.last_gap is not None else None),
        gap_prev_date=(gap.last_gap.prev_date if gap.last_gap is not None else None),
        gap_filled_by_close=d.gap_filled_by_close,
        gap_fill_date_by_close=d.gap_fill_date_by_close,
        gap_fill_close_by_close=(gap.fill_close_by_close if gap.fill_close_by_close is not None else None),
        gap_reclaim_3d=d.gap_reclaim_3d,
        gap_reclaim_date=d.gap_reclaim_date,
        gap_reclaim_level=(reclaim.reclaim_level if reclaim.reclaim_level is not None else None),
        island_reversal=d.island_reversal,
        island_gap_up_date=(island.start_gap_up.date if island is not None else None),
        island_gap_down_date=(island.end_gap_down.date if island is not None else None),
        vol_spike=d.vol_spike,
        vol_spike_date=mv.date,
        vol_spike_defense=d.vol_spike_defense,
        vol_spike_resistance=d.vol_spike_resistance,
        vol_spike_defense_broken=d.vol_spike_defense_broken,
        vol_spike_resistance_broken=d.vol_spike_resistance_broken,
        bearish_long_black_engulf=d.bearish_long_black_engulf,
        bearish_price_up_vol_down=d.bearish_price_up_vol_down,
        bearish_distribution_day=d.bearish_distribution_day,
        v_today=d.v_today,
        v_avg=d.v_avg,
        vol_ratio=vol.vol_ratio,
        vol_label=vol.label,
        rsi14=d.rsi14,
        macd=d.macd,
        macd_signal=d.macd_signal,
        macd_hist=d.macd_hist,
        benchmark_ticker=benchmark,
        bench_p_now=b.p_now,
        bench_ma150=b.ma150,
        bench_regime=bench_regime,
        yahoo_quote_url=yahoo_quote_url(ticker),
        yahoo_history_url=yahoo_history_url(ticker),
        benchmark_quote_url=yahoo_quote_url(benchmark),
        benchmark_history_url=yahoo_history_url(benchmark),
        rule_35_weak=weak,
        rule_35_watch=watch,
        rule_35_gold=gold,
        rule_35_zone=zone,
        stop_loss_pct=stop_loss_pct,
        stop_from_pct=stop_from_pct,
        stop=stop,
        target=target,
        r_ratio=r_val,
        kelly_w=w,
        kelly_w_base=None,
        kelly_w_bonus=None,
        kelly_w_penalty=None,
        kelly_w_components=[],
        kelly_f_raw=kelly_f_raw,
        kelly_f_capped=kelly_f_capped,
        san_yang=sy_str,
        trend_regime=regime,
        final_rating=rating,
        notes=notes,
    )

    md = render_report_md(inp)

    out_dir.mkdir(parents=True, exist_ok=True)
    day = local_now.strftime("%Y%m%d")
    out_path = out_dir / f"{ticker}_{day}.md"
    out_path.write_text(md, encoding="utf-8")
    return out_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="etf-dashboard", description="Evidence-first ETF/Stock dashboard report (Yahoo Finance)")
    p.add_argument("ticker", help="Yahoo ticker, e.g. VOO or 2330.TW")
    p.add_argument("--benchmark", default="^GSPC", help="Benchmark Yahoo ticker (default: ^GSPC)")
    p.add_argument("--out", default="reports", help="Output directory for Markdown reports")
    p.add_argument("--lookback", type=int, default=400, help="Lookback days (calendar) for history fetch")
    p.add_argument("--volume-avg-window", type=int, default=20, help="Rolling window for average volume (default: 20)")
    p.add_argument(
        "--stop-loss-pct",
        type=float,
        default=5.0,
        help="Stop-loss percent (e.g. 5 for 5%%). Used as entry*(1 - pct/100), then tightened by MA20.",
    )
    p.add_argument(
        "--min-rr",
        type=float,
        default=0.0,
        help="Minimum reward/risk (R) required to output a rating. 0 disables this gate.",
    )
    p.add_argument(
        "--max-position-pct",
        type=float,
        default=20.0,
        help="Max position percent cap for Kelly output (default: 20).",
    )
    p.add_argument(
        "--trailing-stop-pct",
        type=float,
        default=5.0,
        help="Trailing stop percent based on P_high (e.g. 5 for 5%%).",
    )
    p.add_argument(
        "--gap-threshold",
        type=float,
        default=0.0,
        help="(Deprecated) Gap threshold percent. 老王缺口已改為嚴格缺口，不使用此參數。",
    )
    p.add_argument(
        "--island-min-days",
        type=int,
        default=2,
        help="Island reversal min separation days (default: 2).",
    )
    p.add_argument(
        "--island-max-days",
        type=int,
        default=10,
        help="Island reversal max separation days (default: 10).",
    )
    p.add_argument(
        "--laowang-lookback",
        type=int,
        default=120,
        help="Lookback days for 老王 gap/island detection (default: 120).",
    )
    p.add_argument(
        "--vol-spike-mult",
        type=float,
        default=2.0,
        help="Volume spike multiplier for defense price (default: 2.0).",
    )
    p.add_argument(
        "--vol-spike-window",
        type=int,
        default=20,
        help="Volume average window for spike baseline (default: 20).",
    )

    args = p.parse_args(argv)

    out = build_report(
        ticker=args.ticker,
        benchmark=args.benchmark,
        out_dir=Path(args.out),
        lookback_days=args.lookback,
        volume_avg_window=args.volume_avg_window,
        stop_loss_pct=float(args.stop_loss_pct) / 100.0,
        min_rr=float(args.min_rr),
        max_position_pct=float(args.max_position_pct) / 100.0,
        trailing_stop_pct=float(args.trailing_stop_pct) / 100.0,
        gap_threshold=0.0,
        island_min_days=int(args.island_min_days),
        island_max_days=int(args.island_max_days),
        laowang_lookback_days=int(args.laowang_lookback),
        vol_spike_mult=float(args.vol_spike_mult),
        vol_spike_window=int(args.vol_spike_window),
    )

    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
