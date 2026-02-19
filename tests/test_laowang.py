import pandas as pd

from etf_dashboard.laowang import (
    detect_island_reversal,
    detect_last_gap,
    volume_spike_defense_price,
)


def _df(rows):
    idx = pd.date_range("2024-01-01", periods=len(rows), freq="D")
    return pd.DataFrame(rows, index=idx)


def test_detect_last_gap_up_and_fill():
    # day0 high=10
    # day1 low=10.6 -> gap up (threshold 0.3%)
    # IMPORTANT: avoid also triggering a later gap-down (which would become the "last gap").
    # day2 must NOT satisfy: High[t] < Low[t-1]*(1-0.003)
    hist = _df(
        [
            {"Open": 9.5, "High": 10.0, "Low": 9.0, "Close": 9.8, "Volume": 100},
            {"Open": 10.6, "High": 11.0, "Low": 10.6, "Close": 10.9, "Volume": 110},
            {"Open": 10.8, "High": 10.7, "Low": 9.9, "Close": 10.2, "Volume": 120},
        ]
    )

    st = detect_last_gap(hist, gap_threshold=0.003, lookback_days=10)
    assert st.last_gap is not None
    assert st.last_gap.kind == "GAP_UP"
    assert st.is_filled is True
    assert st.fill_date is not None


def test_detect_island_reversal_simple():
    # gap up at day1 then gap down at day4 within 2..10 days and returns into zone
    hist = _df(
        [
            {"Open": 9.5, "High": 10.0, "Low": 9.0, "Close": 9.8, "Volume": 100},
            {"Open": 10.8, "High": 11.2, "Low": 10.8, "Close": 11.0, "Volume": 110},  # gap up (low 10.8 > prev high 10)
            {"Open": 11.0, "High": 11.3, "Low": 10.9, "Close": 11.1, "Volume": 105},
            {"Open": 10.9, "High": 11.0, "Low": 10.7, "Close": 10.8, "Volume": 108},
            {"Open": 9.6, "High": 9.7, "Low": 9.3, "Close": 9.4, "Volume": 120},  # gap down (high 9.7 < prev low 10.7)
        ]
    )

    island = detect_island_reversal(hist, gap_threshold=0.003, min_separation_days=2, max_separation_days=10, lookback_days=30)
    assert island is not None
    assert island.start_gap_up.kind == "GAP_UP"
    assert island.end_gap_down.kind == "GAP_DOWN"


def test_volume_spike_defense_price_red_spike():
    hist = _df(
        [
            {"Open": 9.5, "High": 10.0, "Low": 9.0, "Close": 9.8, "Volume": 100},
            {"Open": 9.8, "High": 10.1, "Low": 9.7, "Close": 10.0, "Volume": 100},
            # Using vavg_prev = rolling_mean(window=N).shift(1) (exclude current day).
            # For day2 with N=2, vavg_prev = mean(day0, day1) = 100.
            # So Volume 250 satisfies >= 2.0*100.
            {"Open": 10.0, "High": 10.4, "Low": 9.9, "Close": 10.3, "Volume": 250},  # spike + red
        ]
    )

    # For deterministic unit tests, use a small window.
    s = volume_spike_defense_price(hist, vol_avg_window=2, spike_mult=2.0)
    assert s.is_spike is True
    assert s.defense_price == 9.9
    assert s.date is not None
