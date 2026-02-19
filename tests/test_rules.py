from etf_dashboard.rules import choose_win_rate, san_yang_kai_tai, volume_signal


def test_volume_signal_attack():
    v = volume_signal(vol_today=200, vol_avg=100, open_=10, close=11)
    assert v.is_attack is True
    assert v.label == "攻擊量"


def test_san_yang_kai_tai_true():
    assert san_yang_kai_tai(11, 10, 9, 0.5) is True


def test_choose_win_rate_risk_off_island() -> None:
    w = choose_win_rate(
        p_now=101,
        ma150=100,
        vol_ratio=1.2,
        ma20_slope=1.0,
        san_yang=True,
        island_reversal=True,
    )
    assert w == 0.20


def test_choose_win_rate_bull_resonance_080() -> None:
    w = choose_win_rate(
        p_now=101,
        ma150=100,
        vol_ratio=1.2,
        ma20_slope=1.0,
        san_yang=True,
        bias60=1.0,
        gap_open=False,
        gap_filled=True,
        island_reversal=False,
        vol_spike_defense_broken=False,
    )
    assert w == 0.80


def test_choose_win_rate_bull_060() -> None:
    w = choose_win_rate(
        p_now=101,
        ma150=100,
        vol_ratio=1.6,
        ma20_slope=0.5,
        san_yang=False,
        bias60=-0.5,
        island_reversal=False,
    )
    assert w == 0.60


def test_choose_win_rate_default_040() -> None:
    w = choose_win_rate(
        p_now=100.5,
        ma150=100,
        vol_ratio=1.1,
        ma20_slope=0.1,
        san_yang=False,
        bias60=-1.0,
        island_reversal=False,
    )
    assert w == 0.40


def test_choose_win_rate_missing() -> None:
    assert choose_win_rate(p_now=None, ma150=100, vol_ratio=1.0, ma20_slope=0.2, san_yang=False) is None
