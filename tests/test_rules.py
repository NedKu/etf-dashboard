from etf_dashboard.rules import choose_win_rate, san_yang_kai_tai, volume_signal


def test_volume_signal_attack():
    v = volume_signal(vol_today=200, vol_avg=100, open_=10, close=11)
    assert v.is_attack is True
    assert v.label == "攻擊量"


def test_san_yang_kai_tai_true():
    assert san_yang_kai_tai(11, 10, 9, 0.5) is True


def test_choose_win_rate_penalty_island() -> None:
    # Legacy choose_win_rate() signature: island_reversal is treated as bearish (頂部島狀反轉) penalty.
    # Bull base (0.6) + san_yang bonus (0.1) + momentum bonus (0.1 default in this test context?) - island penalty (0.1)
    # Here bias60 is missing, so momentum bonus is skipped => 0.6 + 0.1 - 0.1 = 0.6
    w = choose_win_rate(
        p_now=101,
        ma150=100,
        ma50=201,
        ma200=200,
        vol_ratio=1.2,
        ma20_slope=1.0,
        san_yang=True,
        island_reversal=True,
    )
    assert w == 0.60


def test_choose_win_rate_bull_base_plus_san_yang_and_momentum() -> None:
    # Bull base=0.6 + 三陽+0.1 + 多頭動能+0.1 (vol_ratio>1 and bias60<10) => 0.8
    w = choose_win_rate(
        p_now=101,
        ma150=100,
        ma50=201,
        ma200=200,
        vol_ratio=1.6,
        ma20_slope=1.0,
        san_yang=True,
        bias60=1.0,
        gap_open=False,
        gap_filled=True,
        gap_filled_by_close=False,
        island_reversal=False,
        vol_spike_defense_broken=False,
        bearish_long_black_engulf=False,
        bearish_distribution_day=False,
        bearish_price_up_vol_down=False,
    )
    assert w == 0.80


def test_choose_win_rate_bear_base_030_for_mixed_signals() -> None:
    # Per spec: Close>MA150 but MA50<=MA200 is treated as bear base.
    w = choose_win_rate(
        p_now=101,
        ma150=100,
        ma50=199,
        ma200=200,
        vol_ratio=1.1,
        ma20_slope=0.5,
        san_yang=False,
        bias60=-0.5,
        island_reversal=False,
    )
    assert w == 0.30


def test_choose_win_rate_value_reversion_bonus() -> None:
    # Bear base=0.3 + GOLD+RSI<30 bonus=0.2 => 0.5
    w = choose_win_rate(
        p_now=99.5,
        ma150=100,
        ma50=199,
        ma200=200,
        vol_ratio=0.9,
        ma20_slope=0.1,
        san_yang=False,
        rsi14=29.0,
        rule_35_zone="GOLD",
    )
    assert w == 0.50


def test_choose_win_rate_clamped_low() -> None:
    # Force very low: bear base 0.3 - 0.1 (omen) -0.1 (island) -0.1 (vol defense) -0.1 (open gap)
    # => -0.1 -> clamped to 0.15
    w = choose_win_rate(
        p_now=99.0,
        ma150=100.0,
        ma50=199.0,
        ma200=200.0,
        vol_ratio=0.8,
        ma20_slope=-0.1,
        san_yang=False,
        gap_open=True,
        gap_filled=False,
        island_reversal=True,
        vol_spike_defense_broken=True,
        bearish_long_black_engulf=True,
    )
    assert w == 0.15


def test_choose_win_rate_missing() -> None:
    assert choose_win_rate(p_now=None, ma150=100, ma50=50, ma200=100, vol_ratio=1.0, ma20_slope=0.2, san_yang=False) is None
