import pandas as pd

from etf_dashboard.laowang import (
    bearish_omens,
    detect_island_reversal,
    detect_island_reversal_bullish,
    detect_last_gap,
    gap_reclaim_within_3_days,
    massive_volume_levels,
)


def _df(rows):
    idx = pd.date_range("2024-01-01", periods=len(rows), freq="D")
    return pd.DataFrame(rows, index=idx)


def test_detect_last_gap_up_and_fill_by_close():
    # day0 high=10
    # day1 low=10.6 -> strict gap up (Low>prev High)
    # day2 closes <= 10 -> filled by close
    hist = _df(
        [
            {"Open": 9.5, "High": 10.0, "Low": 9.0, "Close": 9.8, "Volume": 100},
            {"Open": 10.6, "High": 11.0, "Low": 10.6, "Close": 10.9, "Volume": 110},
            {"Open": 10.2, "High": 10.7, "Low": 9.9, "Close": 9.95, "Volume": 120},
        ]
    )

    st = detect_last_gap(hist, gap_threshold=0.0, lookback_days=10)
    assert st.last_gap is not None
    assert st.last_gap.kind == "GAP_UP"
    assert st.is_filled_by_close is True
    assert st.fill_date_by_close is not None


def test_gap_filled_by_close_and_reclaim_3d():
    # day0 high=10
    # day1 gap up (low 10.6 > prev high 10)
    # day2 closes <= 10 -> filled by close
    # day3 closes >= gap upper (10.6) within 3 days -> reclaim buy
    # IMPORTANT: day2 must not accidentally create a strict gap-down vs day1.
    hist = _df(
        [
            {"Open": 9.5, "High": 10.0, "Low": 9.0, "Close": 9.8, "Volume": 100},
            {"Open": 10.6, "High": 11.0, "Low": 10.6, "Close": 10.9, "Volume": 110},
            {"Open": 10.2, "High": 10.7, "Low": 9.9, "Close": 9.95, "Volume": 120},  # fill by close
            {"Open": 10.5, "High": 10.8, "Low": 10.4, "Close": 10.7, "Volume": 130},  # reclaim
        ]
    )

    gap = detect_last_gap(hist, gap_threshold=0.0, lookback_days=20)
    assert gap.last_gap is not None
    assert gap.last_gap.kind == "GAP_UP"
    assert gap.is_filled_by_close is True
    assert gap.fill_date_by_close is not None

    rec = gap_reclaim_within_3_days(gap, hist)
    assert rec.is_reclaim is True
    assert rec.reclaim_date is not None


def test_bearish_omens_long_black_engulf():
    # New spec: long black K + close below MA5/10/20 requires >= 20 rows.
    rows = 21

    close_prev = [100.0] * (rows - 1)
    close_last = 90.0
    close = close_prev + [close_last]

    # Make last candle a long black.
    open_ = [100.0] * (rows - 1) + [120.0]
    high = [101.0] * (rows - 1) + [121.0]
    low = [99.0] * (rows - 1) + [80.0]
    vol = [100.0] * rows

    hist = pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": vol,
        },
        index=pd.date_range("2024-01-01", periods=rows, freq="D"),
    )

    o = bearish_omens(hist, vol_avg_window=20)
    assert o.long_black_engulf is True


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

    island = detect_island_reversal(hist, gap_threshold=0.0, min_separation_days=2, max_separation_days=10, lookback_days=30)
    assert island is not None
    assert island.start_gap_up.kind == "GAP_UP"
    assert island.end_gap_down.kind == "GAP_DOWN"


def test_detect_island_reversal_bullish_simple():
    # gap down at day1 then gap up at day4 within 2..10 days and returns into zone
    hist = _df(
        [
            {"Open": 10.0, "High": 10.5, "Low": 9.9, "Close": 10.1, "Volume": 100},
            {"Open": 9.0, "High": 9.1, "Low": 8.8, "Close": 8.9, "Volume": 110},  # gap down (high 9.1 < prev low 9.9)
            {"Open": 8.9, "High": 9.0, "Low": 8.7, "Close": 8.8, "Volume": 105},
            {"Open": 8.8, "High": 9.2, "Low": 8.8, "Close": 9.1, "Volume": 108},
            {"Open": 9.8, "High": 10.2, "Low": 9.7, "Close": 10.0, "Volume": 120},  # gap up (low 9.7 > prev high 9.2)
        ]
    )

    island = detect_island_reversal_bullish(hist, gap_threshold=0.0, min_separation_days=2, max_separation_days=10, lookback_days=30)
    assert island is not None
    assert island.end_gap_down.kind == "GAP_DOWN"
    assert island.start_gap_up.kind == "GAP_UP"


def test_massive_volume_levels_peak_only_and_break_flags():
    hist = _df(
        [
            {"Open": 9.5, "High": 10.0, "Low": 9.0, "Close": 9.8, "Volume": 100},
            {"Open": 9.8, "High": 10.1, "Low": 9.7, "Close": 10.0, "Volume": 100},
            # lookback=2 => vmax at day2 = 250
            {"Open": 10.0, "High": 10.4, "Low": 9.9, "Close": 10.5, "Volume": 250},
        ]
    )

    s = massive_volume_levels(hist, lookback_days=2)
    assert s.is_massive is True
    assert s.low == 9.9
    assert s.high == 10.4
    assert s.date is not None
    assert s.low_broken is False
    assert s.high_broken is True
