from __future__ import annotations

from dataclasses import dataclass
from typing import Final

MISSING: Final[str] = "MISSING"


def _fmt_num(x: float | None, *, digits: int) -> str:
    """Format a float with fixed decimals.

    Returns a sentinel string when value is missing.

    Error handling:
        - Raises TypeError for non-numeric, non-None values. This catches upstream
          bugs early (e.g. accidentally passing strings).
    """

    if x is None:
        return MISSING
    if not isinstance(x, (int, float)):
        raise TypeError(f"Expected number or None, got {type(x).__name__}")
    return f"{x:.{digits}f}"


def fmt(x: float | None, digits: int = 2) -> str:
    return _fmt_num(x, digits=digits)


def fmt_ratio(x: float | None, digits: int = 4) -> str:
    return _fmt_num(x, digits=digits)


def fmt_int(x: float | None) -> str:
    if x is None:
        return MISSING
    if not isinstance(x, (int, float)):
        raise TypeError(f"Expected number or None, got {type(x).__name__}")
    return f"{int(x):,}"


def fmt_pct(x: float | None, digits: int = 2) -> str:
    if x is None:
        return MISSING
    if not isinstance(x, (int, float)):
        raise TypeError(f"Expected number or None, got {type(x).__name__}")
    return f"{x:.{digits}f}%"


def _fmt_bool(x: bool | None) -> str:
    """Stable bool formatting for markdown tables.

    Uses Chinese "是/否" to be unambiguous in the report.
    """

    if x is None:
        return MISSING
    return "是" if x else "否"


def _fmt_text(x: str | None) -> str:
    if x is None or x == "":
        return MISSING
    return x


def _status_trailing_stop(hit: bool | None) -> str:
    if hit is True:
        return "⚠️ 已跌破（建議出清/不開新倉）"
    if hit is False:
        return "守住"
    return MISSING


def _status_ma_guard(p_now: float | None, ma20: float | None) -> str:
    if p_now is None or ma20 is None:
        return MISSING
    return "守住" if p_now >= ma20 else "跌破"


def _cmp_symbol_trailing_stop(hit: bool | None) -> str:
    if hit is True:
        return "<="
    if hit is False:
        return ">"
    return "?"


@dataclass(frozen=True, slots=True)
class ReportInputs:
    """All fields required to render the markdown report.

    The renderer is intentionally “dumb”: it expects inputs to be precomputed.
    """

    ticker: str
    name: str | None
    report_time_local: str
    report_time_utc: str

    # Evidence
    p_now: float | None
    ma5: float | None
    ma10: float | None
    ma20: float | None
    ma50: float | None
    ma60: float | None
    ma150: float | None
    ma200: float | None
    bias60: float | None
    p_high: float | None
    drawdown_pct: float | None

    # Risk controls
    trailing_stop_pct: float
    trailing_stop: float | None
    trailing_stop_hit: bool | None

    # 老王 evidence
    gap_kind: str | None
    gap_open: bool | None
    gap_filled: bool | None
    gap_lower: float | None
    gap_upper: float | None

    # 缺口事件日期（用於報告呈現）
    gap_last_date: str | None
    gap_prev_date: str | None

    # 收盤價準則：封閉缺口
    gap_filled_by_close: bool | None
    gap_fill_date_by_close: str | None
    gap_fill_close_by_close: float | None

    # 假跌破收復
    gap_reclaim_3d: bool | None
    gap_reclaim_date: str | None
    gap_reclaim_level: float | None

    island_reversal: bool | None
    island_gap_up_date: str | None
    island_gap_down_date: str | None

    # 爆量（規格）：lookback_days 內最高量（massive_vol），同時提供防守/壓力與突破狀態
    vol_spike: bool | None
    vol_spike_date: str | None
    vol_spike_defense: float | None  # massive_low
    vol_spike_resistance: float | None  # massive_high
    vol_spike_defense_broken: bool | None  # Low_broken
    vol_spike_resistance_broken: bool | None  # High_broken

    bearish_long_black_engulf: bool | None
    bearish_price_up_vol_down: bool | None
    bearish_distribution_day: bool | None

    v_today: float | None
    v_avg: float | None
    vol_ratio: float | None
    vol_label: str

    rsi14: float | None
    macd: float | None
    macd_signal: float | None
    macd_hist: float | None

    benchmark_ticker: str
    bench_p_now: float | None
    bench_ma150: float | None
    bench_regime: str

    yahoo_quote_url: str
    yahoo_history_url: str
    benchmark_quote_url: str
    benchmark_history_url: str

    # Calculations
    rule_35_weak: float | None
    rule_35_watch: float | None
    rule_35_gold: float | None
    rule_35_zone: str

    stop_loss_pct: float
    stop_from_pct: float | None

    stop: float | None
    target: float | None
    r_ratio: float | None

    kelly_w: float | None
    kelly_w_base: float | None
    kelly_w_bonus: float | None
    kelly_w_penalty: float | None
    kelly_w_components: list[str]

    kelly_f_raw: float | None
    kelly_f_capped: float | None

    # Diagnostics
    san_yang: str
    trend_regime: str
    final_rating: str

    # Transparency
    notes: list[str]

def _render_notes(notes: list[str]) -> str:
    if not notes:
        return "- (none)"
    # Avoid intermediate list; keep output deterministic.
    return "\n".join(f"- {n}" for n in notes)


def _render_list(items: list[str]) -> str:
    if not items:
        return "- (none)"
    return "\n".join(f"  - {x}" for x in items)



def render_report_md(inp: ReportInputs) -> str:
    """Render the markdown report."""

    notes_md = _render_notes(inp.notes)

    # Precompute frequently used formatted fields for readability and small perf win.
    p_now = fmt(inp.p_now)
    p_high = fmt(inp.p_high)
    ma20 = fmt(inp.ma20)
    ma60 = fmt(inp.ma60)

    bias60_pct = fmt(inp.bias60, 2)

    trailing_stop = fmt(inp.trailing_stop)
    trailing_stop_pct = fmt_ratio(inp.trailing_stop_pct, 4)
    trailing_stop_status = _status_trailing_stop(inp.trailing_stop_hit)
    trailing_stop_cmp = _cmp_symbol_trailing_stop(inp.trailing_stop_hit)

    ma_guard_status = _status_ma_guard(inp.p_now, inp.ma20)

    kelly_w_pct = fmt_pct((inp.kelly_w * 100.0) if inp.kelly_w is not None else None, 2)
    kelly_f_capped_pct = fmt_pct((inp.kelly_f_capped * 100.0) if inp.kelly_f_capped is not None else None, 2)

    md = f"""## 🩺 {inp.name or inp.ticker}（{inp.ticker}）雙核實戰診斷書

**報告時間（Local）：** {inp.report_time_local}  \
**報告時間（UTC）：** {inp.report_time_utc}

### 0. 🔗 資料來源（僅限 Yahoo Finance）
- 標的頁：{inp.yahoo_quote_url}
- 歷史資料頁：{inp.yahoo_history_url}
- 大盤基準（{inp.benchmark_ticker}）：{inp.benchmark_quote_url}
- 大盤歷史：{inp.benchmark_history_url}

### 1. 🔍 原始數據驗證表 (Evidence Check)
> 結論前請先核對本表；若任一關鍵數值為 {MISSING}，系統將禁止輸出最終操作評級。

| 數據項目 | 系統抓取數值 | 狀態/計算結果 |
| :--- | :--- | :--- |
| **最新股價 (P_now)** | {p_now} | 60日乖離率 BIAS_60 = ((P_now - MA60) / MA60) × 100% = {bias60_pct}% |
| **移動停利 (Trailing stop)** | P_high×(1-{trailing_stop_pct}) = {trailing_stop} | {trailing_stop_status} |
| **老王：缺口(收盤)/收復/島狀/防守** | gap={_fmt_text(inp.gap_kind)}, zone=[{fmt(inp.gap_lower)},{fmt(inp.gap_upper)}] | filled_by_close={_fmt_bool(inp.gap_filled_by_close)} ({_fmt_text(inp.gap_fill_date_by_close)}), reclaim_3d={_fmt_bool(inp.gap_reclaim_3d)} ({_fmt_text(inp.gap_reclaim_date)}) |
| **老王：爆量/凶多吉少/三陽開泰** | massive_low={fmt(inp.vol_spike_defense)} (Low_broken={_fmt_bool(inp.vol_spike_defense_broken)}), massive_high={fmt(inp.vol_spike_resistance)} (High_broken={_fmt_bool(inp.vol_spike_resistance_broken)}) | 凶多吉少={_fmt_bool(inp.bearish_long_black_engulf)},三陽開泰={inp.san_yang} |
| **短期均線** | MA5={fmt(inp.ma5)}, MA10={fmt(inp.ma10)} | - |
| **中期均線** | MA20={ma20}, MA50={fmt(inp.ma50)} | 生命線守護（MA20）：{ma_guard_status} |
| **長期均線** | MA60={ma60}, MA150={fmt(inp.ma150)}, MA200={fmt(inp.ma200)} | 趨勢位階：{inp.trend_regime} |
| **波段最高價 (P_high)** | {p_high} | 目前回檔幅度：{fmt_pct(inp.drawdown_pct)} |
| **成交量能 (V)** | 今日={fmt_int(inp.v_today)} / 均量={fmt_int(inp.v_avg)} | 量能倍數：{fmt(inp.vol_ratio, 2)} 倍（{inp.vol_label}） |
| **技術指標** | RSI14={fmt(inp.rsi14)}, MACD={fmt(inp.macd)} | 動能：signal={fmt(inp.macd_signal)}, hist={fmt(inp.macd_hist)} |
| **大盤濾網** | {inp.benchmark_ticker} P_now={fmt(inp.bench_p_now)} / MA150={fmt(inp.bench_ma150)} | {inp.bench_regime} |

### 2. 🧮 關鍵價位計算明細 (Calculation)

#### 2.1 哲哲 35 法則運算（逐步代入）
- 轉弱防線 (0.8)：P_high × 0.8 = {p_high} × 0.8 = {fmt(inp.rule_35_weak)}
- 觀察買點 (0.7)：P_high × 0.7 = {p_high} × 0.7 = {fmt(inp.rule_35_watch)}
- 黃金抄底 (0.65)：P_high × 0.65 = {p_high} × 0.65 = {fmt(inp.rule_35_gold)}
- 判定：目前股價位於 **{inp.rule_35_zone}**

#### 2.1.1 60 日乖離率（BIAS_60）逐步代入
- BIAS_60 = ((P_now - MA60) / MA60) × 100%
- = (({p_now} - {ma60}) / {ma60}) × 100%
- = {bias60_pct}%

#### 2.1.2 5% 移動停利（Trailing stop）逐步代入
- Trailing stop = P_high × (1 - trailing_stop_pct)
- = {p_high} × (1 - {trailing_stop_pct})
- = {trailing_stop}
- 判斷：Close(P_now) {p_now} {trailing_stop_cmp} Trailing stop {trailing_stop}

#### 2.2 掃地僧風控運算（止損/目標/盈虧比）
- 止損參數：stop_loss_pct = {fmt_pct(inp.stop_loss_pct * 100.0, 2)}
- -{fmt_pct(inp.stop_loss_pct * 100.0, 2)} 止損價：entry × (1 - stop_loss_pct) = {p_now} × (1 - {fmt_ratio(inp.stop_loss_pct, 4)}) = {fmt(inp.stop_from_pct)}
- MA20 止損價：{ma20}
- 嚴格止損價（取較緊者 = max(MA20, -pct)）：{fmt(inp.stop)}
- 預期獲利價：{fmt(inp.target)}
- 盈虧比 R：R = (target - entry) / (entry - stop)
  - 分子：({fmt(inp.target)} - {p_now})
  - 分母：({p_now} - {fmt(inp.stop)})
  - R = {fmt(inp.r_ratio, 4)}

#### 2.3 老王（缺口/爆量/三陽開泰）
**本次偵測結果（含數值/日期）**
- 最新缺口：{_fmt_text(inp.gap_kind)}（gap_date={_fmt_text(inp.gap_last_date)}；prev_date={_fmt_text(inp.gap_prev_date)}；gap_zone=[{fmt(inp.gap_lower)}, {fmt(inp.gap_upper)}]）
- 收盤封閉缺口：{_fmt_bool(inp.gap_filled_by_close)}（fill_date={_fmt_text(inp.gap_fill_date_by_close)}；fill_close={fmt(inp.gap_fill_close_by_close)}）
- 假跌破收復(3日)：{_fmt_bool(inp.gap_reclaim_3d)}（reclaim_date={_fmt_text(inp.gap_reclaim_date)}；reclaim_level={fmt(inp.gap_reclaim_level)}）
- 島狀反轉：{_fmt_bool(inp.island_reversal)}（gap_up_date={_fmt_text(inp.island_gap_up_date)}；gap_down_date={_fmt_text(inp.island_gap_down_date)}）
- 爆量防守/壓力：
  - massive_date={_fmt_text(inp.vol_spike_date)}
  - massive_low={fmt(inp.vol_spike_defense)}（Low_broken={_fmt_bool(inp.vol_spike_defense_broken)}）
  - massive_high={fmt(inp.vol_spike_resistance)}（High_broken={_fmt_bool(inp.vol_spike_resistance_broken)}）
- 凶多吉少：engulf={_fmt_bool(inp.bearish_long_black_engulf)}, dist_day={_fmt_bool(inp.bearish_distribution_day)}, up_vol_down={_fmt_bool(inp.bearish_price_up_vol_down)}

#### 2.4 凱利公式（Kelly Criterion）逐步代入
- 勝率 W（規則推導）：
  - 基礎 Base = {fmt(inp.kelly_w_base, 2)}
  - 加分 Bonus = {fmt(inp.kelly_w_bonus, 2)}
  - 扣分 Penalty = {fmt(inp.kelly_w_penalty, 2)}
  - 明細：
{_render_list(inp.kelly_w_components)}
  - 最終（含上下限 0.15~0.85）W = {fmt(inp.kelly_w, 2)}
- 凱利倉位：f = (W × (R+1) - 1) / R
  - f = ({fmt(inp.kelly_w, 4)} × ({fmt(inp.r_ratio, 4)} + 1) - 1) / {fmt(inp.r_ratio, 4)}
  - f_raw = {fmt(inp.kelly_f_raw, 4)}
  - f_capped（上限 20% 且不小於 0）= {kelly_f_capped_pct}

### 3. 👨‍⚕️ 綜合診斷
- 量價動能（哲哲）：量能判定 = {inp.vol_label}（倍數 {fmt(inp.vol_ratio, 2)}）;60 日乖離率 = {bias60_pct}%;MACD 動能柱 = {fmt(inp.macd_hist)}
- 趨勢紀律（掃地僧）：長線位階 = {inp.trend_regime}；大盤濾網 = {inp.bench_regime}
- 線型結構（老王）：凶多吉少 = {_fmt_bool(inp.bearish_long_black_engulf)}；三陽開泰 = {inp.san_yang}
  ；島狀反轉：{_fmt_bool(inp.island_reversal)}；缺口：{_fmt_text(inp.gap_kind)}（open={_fmt_bool(inp.gap_open)}, filled={_fmt_bool(inp.gap_filled)}）
  ；爆量防守/壓力：low={fmt(inp.vol_spike_defense)}（Low_broken={_fmt_bool(inp.vol_spike_defense_broken)}）, high={fmt(inp.vol_spike_resistance)}（High_broken={_fmt_bool(inp.vol_spike_resistance_broken)}）

### 4. 🚀 最終操作指令 (Final Verdict)
**評級：{inp.final_rating}**

- 建議進場價：{p_now}
- 建議止損價：{fmt(inp.stop)}（觸價強制執行）
- 5% 移動停利價：{trailing_stop}（若 Close 跌破則出清）
- **勝率 (W)：** {kelly_w_pct}
- **盈虧比 (R)：** {fmt(inp.r_ratio, 4)}
- **資金控管 (Kelly)：** 根據勝率 {kelly_w_pct} 與盈虧比 {fmt(inp.r_ratio, 4)}，建議投入資金比例為 **{kelly_f_capped_pct}**（若為負值或為 {MISSING} 則不建議進場；單一標的不超過 20%）

### 5. 🧾 透明化備註（防幻覺）
{notes_md}
"""
    return md
