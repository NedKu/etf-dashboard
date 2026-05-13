from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from stock_per_pbr_trend.analysis import (
    BreakoutConfig,
    add_per_pbr_columns,
    analyze_volume_breakout,
    calculate_price_confidence_intervals,
    calculate_ratio_confidence_intervals,
)
from stock_per_pbr_trend.charting import create_ci_chart, create_price_chart, create_ratio_chart


@dataclass(frozen=True)
class ExportResult:
    ticker: str
    summary: dict[str, str]
    html_sections: list[str]


def _safe_latest(series: pd.Series) -> float | None:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return None
    return float(s.iloc[-1])


def export_per_pbr_report_sections_html(
    ticker: str,
    *,
    breakout_config: BreakoutConfig = BreakoutConfig(),
    mas: list[int] | None = None,
    price_tail_days: int = 252 * 5,
    ci_window_weeks: int = 182,
    ci_tail_weeks: int = 52 * 5,
    include_plotlyjs: bool = False,
) -> ExportResult:
    """Build Plotly HTML snippets (no Streamlit) for PER/PBR + price/CI charts.

    Returns HTML snippets meant to be inserted into a larger HTML document.

    Note: This depends on Yahoo Finance (`yfinance`).
    """

    mas = sorted({int(x) for x in (mas or [5, 10, 20, 50, 150, 200])})

    result = analyze_volume_breakout(ticker, config=breakout_config)
    if result is None:
        return ExportResult(
            ticker=ticker,
            summary={"status": "NO_BREAKOUT"},
            html_sections=[
                f"<section><h2>PER/PBR Trend</h2><p>No significant volume breakout found for {ticker}; skip charts.</p></section>"
            ],
        )

    df = result.data.copy()

    # Price charts
    df_weekly = calculate_price_confidence_intervals(df, window_size_weeks=int(ci_window_weeks))

    df_plot = df.copy()
    df_plot["MA_3.5Y"] = df_plot["Close"].rolling(window=182, min_periods=182).mean()
    for ma in mas:
        df_plot[f"MA{ma}"] = df_plot["Close"].rolling(window=ma, min_periods=ma).mean()

    plot_columns = ["Open", "High", "Low", "Close", "Volume", "MA_3.5Y", "MA_Volume_3M"] + [
        f"MA{ma}" for ma in mas
    ]
    df_plot = df_plot[plot_columns].tail(int(price_tail_days))

    ci_quantiles = [0.975, 0.875, 0.125, 0.025, 0.002, 0.999]
    ci_columns = ["Close", "regression"] + [f"CI_{q}" for q in ci_quantiles]
    df_weekly_plot = df_weekly[ci_columns].tail(int(ci_tail_weeks))

    fig_price = create_price_chart(
        ticker=result.ticker,
        df_plot=df_plot,
        mas=mas,
        recent_volumes=result.recent_volumes,
    )
    fig_ci = create_ci_chart(result.ticker, df_weekly_plot)

    # PER/PBR
    df_with_ratios = add_per_pbr_columns(result.ticker, df)
    per = None
    pbr = None
    fig_per = None
    fig_pbr = None

    if ("PER" in df_with_ratios.columns) and ("PBR" in df_with_ratios.columns):
        weekly = df_with_ratios.resample("W").last().copy()
        weekly["PER"] = weekly["PER"].ffill()
        weekly["PBR"] = weekly["PBR"].ffill()

        per = _safe_latest(weekly["PER"])
        pbr = _safe_latest(weekly["PBR"])

        if weekly["PER"].notna().any() and weekly["PBR"].notna().any():
            weekly = calculate_ratio_confidence_intervals(weekly, window_size_weeks=int(ci_window_weeks))
            fig_per = create_ratio_chart(result.ticker, "PER", weekly)
            fig_pbr = create_ratio_chart(result.ticker, "PBR", weekly)

    summary: dict[str, str] = {
        "status": "OK",
        "ticker": result.ticker,
        "recent_high": f"{result.recent_high:.2f}",
        "recent_low": f"{result.recent_low:.2f}",
        "avg_volume_3m": f"{result.avg_volume_3m:,.0f}",
    }
    if per is not None:
        summary["PER"] = f"{per:.2f}"
    if pbr is not None:
        summary["PBR"] = f"{pbr:.2f}"

    def _fig_html(fig) -> str:
        return fig.to_html(full_html=False, include_plotlyjs=include_plotlyjs)

    parts: list[str] = [
        "<section>",
        f"<h2>PER/PBR Trend (Plotly) — {result.ticker}</h2>",
        "<ul>",
        f"<li>Recent High (lookback): {result.recent_high:.2f}</li>",
        f"<li>Recent Low (lookback): {result.recent_low:.2f}</li>",
        f"<li>3M Avg Volume: {result.avg_volume_3m:,.0f}</li>",
        f"<li>PER (snapshot-derived): {('%.2f' % per) if per is not None else 'N/A'}</li>",
        f"<li>PBR (snapshot-derived): {('%.2f' % pbr) if pbr is not None else 'N/A'}</li>",
        "</ul>",
        "</section>",
        "<section>",
        f"<h3>Price + Volume</h3>",
        _fig_html(fig_price),
        "</section>",
        "<section>",
        f"<h3>Price Confidence Bands (Weekly)</h3>",
        _fig_html(fig_ci),
        "</section>",
    ]

    if fig_per is not None and fig_pbr is not None:
        parts.extend(
            [
                "<section>",
                "<h3>PER Statistical Bands</h3>",
                _fig_html(fig_per),
                "</section>",
                "<section>",
                "<h3>PBR Statistical Bands</h3>",
                _fig_html(fig_pbr),
                "</section>",
            ]
        )
    else:
        parts.append(
            "<section><p><strong>Note:</strong> PER/PBR are derived from Yahoo Finance snapshot fundamentals "
            "(trailingEps, bookValue) and may be unavailable for some tickers.</p></section>"
        )

    return ExportResult(ticker=ticker, summary=summary, html_sections=parts)
