from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


def fmt(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "MISSING"
    return f"{x:.{digits}f}"


def fmt_int(x: float | None) -> str:
    if x is None:
        return "MISSING"
    return f"{int(x):,}"


def fmt_pct(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "MISSING"
    return f"{x:.{digits}f}%"


def fmt_ratio(x: float | None, digits: int = 4) -> str:
    if x is None:
        return "MISSING"
    return f"{x:.{digits}f}"


@dataclass(frozen=True)
class ReportInputs:
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

    # 長紅中軸防守
    midpoint_defense: float | None
    midpoint_defense_broken: bool | None
    midpoint_defense_date: str | None

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
    kelly_f_raw: float | None
    kelly_f_capped: float | None

    # Diagnostics
    san_yang: str
    trend_regime: str
    final_rating: str

    # Transparency
    notes: list[str]


def render_report_md(inp: ReportInputs) -> str:
    notes = "\n".join([f"- {n}" for n in inp.notes]) if inp.notes else "- (none)"

    md = f"""## 🩺 {inp.name or inp.ticker}（{inp.ticker}）雙核實戰診斷書

**報告時間（Local）：** {inp.report_time_local}  \
**報告時間（UTC）：** {inp.report_time_utc}

### 0. 🔗 資料來源（僅限 Yahoo Finance）
- 標的頁：{inp.yahoo_quote_url}
- 歷史資料頁：{inp.yahoo_history_url}
- 大盤基準（{inp.benchmark_ticker}）：{inp.benchmark_quote_url}
- 大盤歷史：{inp.benchmark_history_url}

### 1. 🔍 原始數據驗證表 (Evidence Check)
> 結論前請先核對本表；若任一關鍵數值為 MISSING，系統將禁止輸出最終操作評級。

| 數據項目 | 系統抓取數值 | 狀態/計算結果 |
| :--- | :--- | :--- |
| **最新股價 (P_now)** | {fmt(inp.p_now)} | 60日乖離率 BIAS_60 = ((P_now - MA60) / MA60) × 100% = {fmt(inp.bias60, 2)}% |
| **移動停利 (Trailing stop)** | P_high×(1-{fmt_ratio(inp.trailing_stop_pct, 4)}) = {fmt(inp.trailing_stop)} | {'⚠️ 已跌破（建議出清/不開新倉）' if inp.trailing_stop_hit is True else ('守住' if inp.trailing_stop_hit is False else 'MISSING')} |
| **老王：缺口(收盤)/收復/島狀/防守** | gap={inp.gap_kind or 'MISSING'}, zone=[{fmt(inp.gap_lower)},{fmt(inp.gap_upper)}] | filled_by_close={inp.gap_filled_by_close} ({inp.gap_fill_date_by_close or 'MISSING'}), reclaim_3d={inp.gap_reclaim_3d} ({inp.gap_reclaim_date or 'MISSING'}) |
| **老王：爆量/中軸/凶多吉少** | massive_low={fmt(inp.vol_spike_defense)} (Low_broken={inp.vol_spike_defense_broken}), massive_high={fmt(inp.vol_spike_resistance)} (High_broken={inp.vol_spike_resistance_broken}) | midpoint={fmt(inp.midpoint_defense)} (broken={inp.midpoint_defense_broken}, date={inp.midpoint_defense_date or 'MISSING'}) |
| **短期均線** | MA5={fmt(inp.ma5)}, MA10={fmt(inp.ma10)} | - |
| **中期均線** | MA20={fmt(inp.ma20)}, MA50={fmt(inp.ma50)} | 生命線守護（MA20）：{'守住' if (inp.p_now is not None and inp.ma20 is not None and inp.p_now >= inp.ma20) else ('跌破' if (inp.p_now is not None and inp.ma20 is not None) else 'MISSING')} |
| **長期均線** | MA60={fmt(inp.ma60)}, MA150={fmt(inp.ma150)}, MA200={fmt(inp.ma200)} | 趨勢位階：{inp.trend_regime} |
| **波段最高價 (P_high)** | {fmt(inp.p_high)} | 目前回檔幅度：{fmt_pct(inp.drawdown_pct)} |
| **成交量能 (V)** | 今日={fmt_int(inp.v_today)} / 均量={fmt_int(inp.v_avg)} | 量能倍數：{fmt(inp.vol_ratio, 2)} 倍（{inp.vol_label}） |
| **技術指標** | RSI14={fmt(inp.rsi14)}, MACD={fmt(inp.macd)} | 動能：signal={fmt(inp.macd_signal)}, hist={fmt(inp.macd_hist)} |
| **大盤濾網** | {inp.benchmark_ticker} P_now={fmt(inp.bench_p_now)} / MA150={fmt(inp.bench_ma150)} | {inp.bench_regime} |

### 2. 🧮 關鍵價位計算明細 (Calculation)

#### 2.1 哲哲 35 法則運算（逐步代入）
- 轉弱防線 (0.8)：P_high × 0.8 = {fmt(inp.p_high)} × 0.8 = {fmt(inp.rule_35_weak)}
- 觀察買點 (0.7)：P_high × 0.7 = {fmt(inp.p_high)} × 0.7 = {fmt(inp.rule_35_watch)}
- 黃金抄底 (0.65)：P_high × 0.65 = {fmt(inp.p_high)} × 0.65 = {fmt(inp.rule_35_gold)}
- 判定：目前股價位於 **{inp.rule_35_zone}**

#### 2.1.1 60 日乖離率（BIAS_60）逐步代入
- BIAS_60 = ((P_now - MA60) / MA60) × 100%
- = (({fmt(inp.p_now)} - {fmt(inp.ma60)}) / {fmt(inp.ma60)}) × 100%
- = {fmt(inp.bias60, 2)}%

#### 2.1.2 5% 移動停利（Trailing stop）逐步代入
- Trailing stop = P_high × (1 - trailing_stop_pct)
- = {fmt(inp.p_high)} × (1 - {fmt_ratio(inp.trailing_stop_pct, 4)})
- = {fmt(inp.trailing_stop)}
- 判斷：Close(P_now) {fmt(inp.p_now)} {'<=' if inp.trailing_stop_hit is True else '>' if inp.trailing_stop_hit is False else '?'} Trailing stop {fmt(inp.trailing_stop)}

#### 2.4 老王（缺口 / 封閉 / 假跌破收復 / 島狀反轉 / 爆量防守 / 中軸 / 凶多吉少）

**規則說明**
- 缺口判定（嚴格缺口，不使用 gap_threshold）
  - gap_up：Low[t] > High[t-1]
  - gap_down：High[t] < Low[t-1]
- 封閉判定（收盤價準則）
  - gap_up 封閉：之後任一天 Close ≤ High[t-1]（= up_gap_bottom）
  - gap_down 封閉：之後任一天 Close ≥ Low[t-1]（= down_gap_top）
- 假跌破收復（買點）
  - 條件：GAP_UP 已被「收盤價」封閉後，3 個交易日內 Close ≥ gap 上緣（= Low[gap_day]）
- 島狀反轉（逃命）
  - 高檔跳空向上後，短天期內再出現跳空向下（視窗由 island_min_days~island_max_days 控制）
- 爆量防守/壓力
  - massive_vol：成交量 = lookback_days 內最高量
  - 防守價 massive_low = Low[爆量日]；壓力價 massive_high = High[爆量日]
  - 跌破防守價（Close < massive_low）視為風險升級（Low_broken=True）
  - 跌破壓力價（Close > massive_high）視為機會（High_broken=True）
- 長紅中軸防守
  - 長紅棒：最近一根紅K且實體/全長 ≥ 0.6
  - 中軸 = (High + Low) / 2；跌破以 Close < 中軸
- 凶多吉少（簡化偵測）
  - 高檔長黑吞噬 / 出貨日 / 價漲量縮

**本次偵測結果（含數值/日期）**
- 最新缺口：{inp.gap_kind or 'MISSING'}（gap_date={inp.gap_last_date or 'MISSING'}；prev_date={inp.gap_prev_date or 'MISSING'}；gap_zone=[{fmt(inp.gap_lower)}, {fmt(inp.gap_upper)}]）
- 收盤封閉缺口：{inp.gap_filled_by_close}（fill_date={inp.gap_fill_date_by_close or 'MISSING'}；fill_close={fmt(inp.gap_fill_close_by_close)}）
- 假跌破收復(3日)：{inp.gap_reclaim_3d}（reclaim_date={inp.gap_reclaim_date or 'MISSING'}；reclaim_level={fmt(inp.gap_reclaim_level)}）
- 島狀反轉：{inp.island_reversal}（gap_up_date={inp.island_gap_up_date or 'MISSING'}；gap_down_date={inp.island_gap_down_date or 'MISSING'}）
- 爆量防守/壓力：
  - massive_date={inp.vol_spike_date or 'MISSING'}
  - massive_low={fmt(inp.vol_spike_defense)}（Low_broken={inp.vol_spike_defense_broken}）
  - massive_high={fmt(inp.vol_spike_resistance)}（High_broken={inp.vol_spike_resistance_broken}）
- 長紅中軸：midpoint={fmt(inp.midpoint_defense)}（broken={inp.midpoint_defense_broken}；midpoint_date={inp.midpoint_defense_date or 'MISSING'}）
- 凶多吉少：engulf={inp.bearish_long_black_engulf}, dist_day={inp.bearish_distribution_day}, up_vol_down={inp.bearish_price_up_vol_down}

#### 2.2 掃地僧風控運算（止損/目標/盈虧比）
- 止損參數：stop_loss_pct = {fmt_pct(inp.stop_loss_pct * 100.0, 2)}
- -{fmt_pct(inp.stop_loss_pct * 100.0, 2)} 止損價：entry × (1 - stop_loss_pct) = {fmt(inp.p_now)} × (1 - {fmt_ratio(inp.stop_loss_pct, 4)}) = {fmt(inp.stop_from_pct)}
- MA20 止損價：{fmt(inp.ma20)}
- 嚴格止損價（取較緊者 = max(MA20, -pct)）：{fmt(inp.stop)}
- 預期獲利價：{fmt(inp.target)}
- 盈虧比 R：R = (target - entry) / (entry - stop)
  - 分子：({fmt(inp.target)} - {fmt(inp.p_now)})
  - 分母：({fmt(inp.p_now)} - {fmt(inp.stop)})
  - R = {fmt(inp.r_ratio, 4)}

#### 2.3 凱利公式（Kelly Criterion）逐步代入
- 勝率 W（規則推導）：W = {fmt(inp.kelly_w, 2)}
- 凱利倉位：f = (W × (R+1) - 1) / R
  - f = ({fmt(inp.kelly_w, 4)} × ({fmt(inp.r_ratio, 4)} + 1) - 1) / {fmt(inp.r_ratio, 4)}
  - f_raw = {fmt(inp.kelly_f_raw, 4)}
  - f_capped（上限 20% 且不小於 0）= {fmt_pct((inp.kelly_f_capped * 100.0) if inp.kelly_f_capped is not None else None, 2)}

### 3. 👨‍⚕️ 雙學派綜合診斷
- 量價動能（哲哲）：量能判定 = {inp.vol_label}（倍數 {fmt(inp.vol_ratio, 2)}）
- 趨勢紀律（掃地僧）：三陽開泰 = {inp.san_yang}；長線位階 = {inp.trend_regime}；大盤濾網 = {inp.bench_regime}

### 4. 🚀 最終操作指令 (Final Verdict)
**評級：{inp.final_rating}**

- 建議進場價：{fmt(inp.p_now)}
- 建議止損價：{fmt(inp.stop)}（觸價強制執行）
- 5% 移動停利價：{fmt(inp.trailing_stop)}（若 Close 跌破則出清）
- **勝率 (W)：** {fmt_pct((inp.kelly_w * 100.0) if inp.kelly_w is not None else None, 2)}
- **盈虧比 (R)：** {fmt(inp.r_ratio, 4)}
- **資金控管 (Kelly)：** 根據勝率 {fmt_pct((inp.kelly_w * 100.0) if inp.kelly_w is not None else None, 2)} 與盈虧比 {fmt(inp.r_ratio, 4)}，建議投入資金比例為 **{fmt_pct((inp.kelly_f_capped * 100.0) if inp.kelly_f_capped is not None else None, 2)}**（若為負值或為 MISSING 則不建議進場；單一標的不超過 20%）

- 老王風險旗標：
  - 島狀反轉：{inp.island_reversal}
  - 缺口：{inp.gap_kind or 'MISSING'}（open={inp.gap_open}, filled={inp.gap_filled}）
  - 爆量防守/壓力：low={fmt(inp.vol_spike_defense)}（Low_broken={inp.vol_spike_defense_broken}）, high={fmt(inp.vol_spike_resistance)}（High_broken={inp.vol_spike_resistance_broken}）
  - 長紅中軸：midpoint={fmt(inp.midpoint_defense)}（broken={inp.midpoint_defense_broken}）

### 5. 🧾 透明化備註（防幻覺）
{notes}
"""
    return md
