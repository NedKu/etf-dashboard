from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from etf_dashboard.charting import prepare_chart_data
from etf_dashboard.cli import build_report
from etf_dashboard.data_yahoo import fetch_snapshot


@dataclass(frozen=True)
class ReportFile:
    path: Path

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def mtime(self) -> float:
        return self.path.stat().st_mtime


def list_reports(report_dir: Path) -> list[ReportFile]:
    if not report_dir.exists():
        return []
    files = sorted(report_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [ReportFile(path=f) for f in files]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> None:
    st.set_page_config(page_title="ETF Dashboard", layout="wide")

    st.title("ETF/Stock Evidence-First Dashboard (Yahoo Finance)")

    with st.sidebar:
        st.header("Generate report")
        ticker = st.text_input("Yahoo ticker", value="VOO", help="例：VOO、2330.TW")
        out_dir = st.text_input("Reports directory", value="reports")
        benchmark = st.text_input("Benchmark", value="^GSPC")
        lookback = st.number_input("Lookback (days)", min_value=200, max_value=2000, value=400, step=50)
        vol_window = st.number_input("Volume avg window", min_value=5, max_value=120, value=20, step=5)

        st.header("Chart")
        chart_mode = st.radio(
            "Date range mode",
            options=["Last N days", "Custom"],
            index=0,
            horizontal=True,
        )

        snap_for_dates = None
        if chart_mode == "Custom":
            try:
                snap_for_dates = fetch_snapshot(ticker.strip() or "VOO", lookback_days=int(lookback))
            except Exception:
                snap_for_dates = None

        if chart_mode == "Custom" and snap_for_dates is not None and not snap_for_dates.history.empty:
            df_idx = pd.to_datetime(snap_for_dates.history.index)
            min_date = df_idx.min().date()
            max_date = df_idx.max().date()
            start_date, end_date = st.date_input(
                "Chart date range",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
            )
        else:
            chart_range = st.slider(
                "Chart range (days)",
                min_value=30,
                max_value=int(lookback),
                value=min(180, int(lookback)),
                step=10,
                help="只影響圖表顯示範圍（不影響報告 lookback 抓取）",
            )
            start_date = None
            end_date = None

        ma_windows = st.multiselect(
            "Moving averages",
            options=[5, 10, 20, 50, 60, 150, 200],
            default=[5, 10, 20, 50, 200],
        )

        stop_loss_pct = st.number_input("Stop-loss %", min_value=0.5, max_value=30.0, value=5.0, step=0.5)
        trailing_stop_pct = st.number_input("Trailing stop % (from P_high)", min_value=0.5, max_value=30.0, value=5.0, step=0.5)
        max_position_pct = st.number_input("Max position % (cap)", min_value=1.0, max_value=50.0, value=20.0, step=1.0)
        laowang_lookback = st.number_input("老王 lookback (days)", min_value=30, max_value=400, value=120, step=10)
        min_rr = st.number_input(
            "Min R/R (target÷risk)",
            min_value=0.0,
            max_value=10.0,
            value=2.5,
            step=0.25,
            help="作為判斷條件：只顯示/標示盈虧比 >= 此值的交易計畫 (R = (target-entry)/(entry-stop))；0 表示不限制",
        )

        run = st.button("Generate")

    report_dir = Path(out_dir)

    # Chart (interactive)
    st.subheader("Chart")
    try:
        snap = fetch_snapshot(ticker.strip() or "VOO", lookback_days=int(lookback))
        chart = prepare_chart_data(
            snap.history,
            ma_windows=[int(x) for x in ma_windows],
            volume_avg_window=int(vol_window),
        )

        # 老王 overlay levels
        from etf_dashboard.laowang import (
            bearish_omens,
            detect_last_gap,
            gap_reclaim_within_3_days,
            massive_volume_levels,
        )

        gap = detect_last_gap(snap.history, gap_threshold=0.0, lookback_days=int(laowang_lookback))
        reclaim = gap_reclaim_within_3_days(gap, snap.history)
        mv = massive_volume_levels(snap.history, lookback_days=int(vol_window))
        omen = bearish_omens(snap.history, vol_avg_window=int(vol_window))

        st.caption(
            "老王："
            f"gap={gap.last_gap.kind if gap.last_gap else 'MISSING'} zone=[{gap.last_gap.lower if gap.last_gap else 'MISSING'}, {gap.last_gap.upper if gap.last_gap else 'MISSING'}] | "
            f"filled_by_close={gap.is_filled_by_close} ({gap.fill_date_by_close}) | "
            f"reclaim_3d={reclaim.is_reclaim} ({reclaim.reclaim_date}) | "
            f"massive_low={mv.low} (Low_broken={mv.low_broken}) massive_high={mv.high} (High_broken={mv.high_broken}) | "
            f"engulf={omen.long_black_engulf}, dist_day={omen.distribution_day}, up_vol_down={omen.price_up_vol_down}"
        )

        df = chart.df
        if start_date is not None and end_date is not None:
            # st.date_input can return a single date if user clears one side
            if isinstance(start_date, date) and isinstance(end_date, date):
                df_show = df.loc[(df.index.date >= start_date) & (df.index.date <= end_date)].copy()
            else:
                df_show = df.tail(int(min(180, len(df)))).copy()
        else:
            df_show = df.tail(int(chart_range)).copy()

        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.02,
            row_heights=[0.72, 0.28],
        )

        fig.add_trace(
            go.Candlestick(
                x=df_show.index,
                open=df_show["Open"],
                high=df_show["High"],
                low=df_show["Low"],
                close=df_show["Close"],
                name="Daily",
            ),
            row=1,
            col=1,
        )

        # 老王: horizontal levels
        if gap.last_gap is not None:
            fig.add_hline(y=float(gap.last_gap.lower), line_width=1, line_dash="dot", line_color="#7f7f7f", annotation_text="Gap lower", row=1, col=1)
            fig.add_hline(y=float(gap.last_gap.upper), line_width=1, line_dash="dot", line_color="#7f7f7f", annotation_text="Gap upper", row=1, col=1)

        # Massive volume levels
        if mv.low is not None:
            fig.add_hline(y=float(mv.low), line_width=1.5, line_dash="dash", line_color="red", annotation_text="Massive vol low", row=1, col=1)
        if mv.high is not None:
            fig.add_hline(y=float(mv.high), line_width=1.5, line_dash="dash", line_color="green", annotation_text="Massive vol high", row=1, col=1)

        for w in [int(x) for x in ma_windows]:
            col = f"MA{w}"
            if col in df_show.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df_show.index,
                        y=df_show[col],
                        mode="lines",
                        name=col,
                        line=dict(width=1.5),
                    ),
                    row=1,
                    col=1,
                )

        fig.add_trace(
            go.Bar(
                x=df_show.index,
                y=df_show["Volume"],
                name="Volume",
                marker=dict(color="rgba(120,120,120,0.6)"),
            ),
            row=2,
            col=1,
        )

        vavg_col = f"VAVG{int(vol_window)}"
        if vavg_col in df_show.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_show.index,
                    y=df_show[vavg_col],
                    mode="lines",
                    name=vavg_col,
                    line=dict(width=1.5, color="orange"),
                ),
                row=2,
                col=1,
            )

        fig.update_layout(
            height=720,
            margin=dict(l=10, r=10, t=30, b=10),
            hovermode="x unified",
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        )
        fig.update_yaxes(title_text="Price", row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)

        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning("Chart unavailable (data fetch or plotting error).")
        st.exception(e)

    if run:
        if not ticker.strip():
            st.error("ticker cannot be empty")
        else:
            with st.spinner("Fetching Yahoo Finance data and generating report..."):
                try:
                    out_path = build_report(
                        ticker=ticker.strip(),
                        benchmark=benchmark.strip() or "^GSPC",
                        out_dir=report_dir,
                        lookback_days=int(lookback),
                        volume_avg_window=int(vol_window),
                        stop_loss_pct=float(stop_loss_pct) / 100.0,
                        min_rr=float(min_rr),
                        max_position_pct=float(max_position_pct) / 100.0,
                        trailing_stop_pct=float(trailing_stop_pct) / 100.0,
                        gap_threshold=0.0,
                        island_min_days=2,
                        island_max_days=10,
                        laowang_lookback_days=int(laowang_lookback),
                        vol_spike_mult=2.0,
                        vol_spike_window=int(vol_window),
                    )
                    st.success(f"Report generated: {out_path}")
                except Exception as e:
                    st.exception(e)

    st.divider()

    st.subheader("Reports")

    files = list_reports(report_dir)
    if not files:
        st.info(f"No reports found in {report_dir.resolve()}")
        return

    options = {f"{f.name}  ({datetime.fromtimestamp(f.mtime).strftime('%Y-%m-%d %H:%M:%S')})": f for f in files}
    selected_label = st.selectbox("Select a report", list(options.keys()))
    selected = options[selected_label]

    c1, c2 = st.columns([3, 1])
    with c2:
        st.download_button(
            label="Download Markdown",
            data=read_text(selected.path),
            file_name=selected.name,
            mime="text/markdown",
        )

    with c1:
        st.markdown(read_text(selected.path))


if __name__ == "__main__":
    main()
