from etf_dashboard.rules import san_sheng_wu_nai


def test_san_sheng_wu_nai_true() -> None:
    assert (
        san_sheng_wu_nai(
            p_now=90,
            ma5=100,
            ma10=110,
            ma20=120,
            ma5_slope=-1,
            ma10_slope=-1,
            ma20_slope=-1,
        )
        is True
    )


def test_san_sheng_wu_nai_false_when_price_above() -> None:
    assert (
        san_sheng_wu_nai(
            p_now=105,
            ma5=100,
            ma10=110,
            ma20=120,
            ma5_slope=-1,
            ma10_slope=-1,
            ma20_slope=-1,
        )
        is False
    )


def test_san_sheng_wu_nai_missing() -> None:
    assert (
        san_sheng_wu_nai(
            p_now=None,
            ma5=100,
            ma10=110,
            ma20=120,
            ma5_slope=-1,
            ma10_slope=-1,
            ma20_slope=-1,
        )
        is None
    )
