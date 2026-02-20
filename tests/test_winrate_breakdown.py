from etf_dashboard.rules import (
    WinRateComponentStatus,
    choose_win_rate_breakdown,
)


def test_winrate_breakdown_bull_base_only() -> None:
    bd = choose_win_rate_breakdown(
        p_now=110,
        ma150=100,
        ma50=210,
        ma200=200,
        vol_ratio=0.9,
        ma20_slope=1.0,
        san_yang=False,
        rule_35_zone=None,
        rsi14=None,
        bias60=None,
        gap_open=None,
        gap_filled=None,
        gap_filled_by_close=None,
        gap_direction_by_close=None,
        island_reversal=None,
        vol_spike_defense_broken=None,
        bearish_long_black_engulf=None,
        bearish_distribution_day=None,
        bearish_price_up_vol_down=None,
    )

    assert bd.base == 0.60
    assert bd.bonus_total == 0.0
    assert bd.penalty_total == 0.0
    assert bd.w_clamped == 0.60
    # Some rules should be skipped due to missing inputs
    assert any(c.status == WinRateComponentStatus.SKIPPED_MISSING for c in bd.components)


def test_winrate_breakdown_bear_with_bonus_and_penalty() -> None:
    bd = choose_win_rate_breakdown(
        p_now=90,
        ma150=100,
        ma50=190,
        ma200=200,
        vol_ratio=2.0,
        ma20_slope=-1.0,
        san_yang=True,
        rule_35_zone="GOLD",
        rsi14=20,
        bias60=5,
        gap_open=True,
        gap_filled=False,
        gap_filled_by_close=True,
        gap_direction_by_close="UP",
        island_reversal=True,
        vol_spike_defense_broken=True,
        bearish_long_black_engulf=True,
        bearish_distribution_day=False,
        bearish_price_up_vol_down=False,
    )

    assert bd.base == 0.30
    assert bd.bonus_total == 0.30  # +0.10 san_yang +0.20 value
    assert bd.penalty_total == -0.60  # -0.10 gap up close -0.10 island -0.10 defense -0.20 bearish -0.10 open gap
    assert bd.w_raw == 0.00
    assert bd.w_clamped == 0.15  # clamped


def test_winrate_breakdown_missing_base_means_missing_w() -> None:
    bd = choose_win_rate_breakdown(
        p_now=None,
        ma150=100,
        ma50=210,
        ma200=200,
        vol_ratio=1.0,
        ma20_slope=1.0,
        san_yang=True,
    )

    assert bd.base is None
    assert bd.w_raw is None
    assert bd.w_clamped is None
    assert any(c.status == WinRateComponentStatus.SKIPPED_MISSING for c in bd.components)
