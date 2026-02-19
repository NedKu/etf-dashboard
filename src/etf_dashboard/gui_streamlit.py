from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import streamlit as st

from etf_dashboard.cli import build_report


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
        stop_loss_pct = st.number_input("Stop-loss %", min_value=0.5, max_value=30.0, value=5.0, step=0.5)
        trailing_stop_pct = st.number_input("Trailing stop % (from P_high)", min_value=0.5, max_value=30.0, value=5.0, step=0.5)
        max_position_pct = st.number_input("Max position % (cap)", min_value=1.0, max_value=50.0, value=20.0, step=1.0)
        gap_threshold = st.number_input("Gap threshold %", min_value=0.1, max_value=5.0, value=0.3, step=0.1)
        island_min_days = st.number_input("Island min days", min_value=1, max_value=10, value=2, step=1)
        island_max_days = st.number_input("Island max days", min_value=2, max_value=30, value=10, step=1)
        laowang_lookback = st.number_input("老王 lookback (days)", min_value=30, max_value=400, value=120, step=10)
        vol_spike_mult = st.number_input("Volume spike mult", min_value=1.0, max_value=10.0, value=2.0, step=0.25)
        vol_spike_window = st.number_input("Volume spike window (days)", min_value=20, max_value=260, value=20, step=10)
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
                        gap_threshold=float(gap_threshold) / 100.0,
                        island_min_days=int(island_min_days),
                        island_max_days=int(island_max_days),
                        laowang_lookback_days=int(laowang_lookback),
                        vol_spike_mult=float(vol_spike_mult),
                        vol_spike_window=int(vol_spike_window),
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
