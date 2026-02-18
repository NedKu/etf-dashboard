from etf_dashboard.rules import choose_win_rate, san_yang_kai_tai, volume_signal


def test_volume_signal_attack():
    v = volume_signal(vol_today=200, vol_avg=100, open_=10, close=11)
    assert v.is_attack is True
    assert v.label == "攻擊量"


def test_san_yang_kai_tai_true():
    assert san_yang_kai_tai(11, 10, 9, 0.5) is True


def test_choose_win_rate_downtrend():
    assert choose_win_rate(p_now=90, ma150=100, vol_ratio=1.2, ma20_slope=-1.0, san_yang=False) == 0.30


def test_choose_win_rate_bull_san_yang():
    assert choose_win_rate(p_now=110, ma150=100, vol_ratio=1.0, ma20_slope=0.2, san_yang=True) == 0.70


def test_choose_win_rate_bull_volume():
    assert choose_win_rate(p_now=110, ma150=100, vol_ratio=1.6, ma20_slope=0.2, san_yang=False) == 0.65


def test_choose_win_rate_no_volume():
    assert choose_win_rate(p_now=110, ma150=100, vol_ratio=0.8, ma20_slope=0.2, san_yang=False) == 0.45


def test_choose_win_rate_missing():
    assert choose_win_rate(p_now=None, ma150=100, vol_ratio=1.0, ma20_slope=0.2, san_yang=False) is None
