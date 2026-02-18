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
    p_high: float | None
    drawdown_pct: float | None

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
| **最新股價 (P_now)** | {fmt(inp.p_now)} | - |
| **短期均線** | MA5={fmt(inp.ma5)}, MA10={fmt(inp.ma10)} | - |
| **中期均線** | MA20={fmt(inp.ma20)}, MA50={fmt(inp.ma50)} | 生命線守護（MA20）：{'守住' if (inp.p_now is not None and inp.ma20 is not None and inp.p_now >= inp.ma20) else ('跌破' if (inp.p_now is not None and inp.ma20 is not None) else 'MISSING')} |
| **中長期均線** | MA60={fmt(inp.ma60)}, MA150={fmt(inp.ma150)} | 趨勢位階：{inp.trend_regime} |
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
  - f_capped（上限 25% 且不小於 0）= {fmt(inp.kelly_f_capped, 4)}

### 3. 👨‍⚕️ 雙學派綜合診斷
- 量價動能（哲哲）：量能判定 = {inp.vol_label}（倍數 {fmt(inp.vol_ratio, 2)}）
- 趨勢紀律（掃地僧）：三陽開泰 = {inp.san_yang}；長線位階 = {inp.trend_regime}；大盤濾網 = {inp.bench_regime}

### 4. 🚀 最終操作指令 (Final Verdict)
**評級：{inp.final_rating}**

- 建議進場價：{fmt(inp.p_now)}
- 建議止損價：{fmt(inp.stop)}（觸價強制執行）
- **勝率 (W)：** {fmt_pct((inp.kelly_w * 100.0) if inp.kelly_w is not None else None, 2)}
- **盈虧比 (R)：** {fmt(inp.r_ratio, 4)}
- **資金控管 (Kelly)：** 根據勝率 {fmt_pct((inp.kelly_w * 100.0) if inp.kelly_w is not None else None, 2)} 與盈虧比 {fmt(inp.r_ratio, 4)}，建議投入資金比例為 **{fmt_pct((min(0.20, inp.kelly_f_capped) * 100.0) if inp.kelly_f_capped is not None else None, 2)}**（若為負值或為 MISSING 則不建議進場；單一標的不超過 20%）

### 5. 🧾 透明化備註（防幻覺）
{notes}
"""
    return md
