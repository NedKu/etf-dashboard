import pandas as pd

from etf_dashboard.indicators import sma, rsi


def test_sma_basic():
    s = pd.Series([1, 2, 3, 4, 5])
    out = sma(s, 3)
    assert out.isna().sum() == 2
    assert float(out.iloc[-1]) == 4.0


def test_rsi_range():
    s = pd.Series([1, 2, 3, 2, 2, 4, 5, 6, 5, 7, 8, 7, 9, 10, 9, 11, 12])
    out = rsi(s, 14).dropna()
    assert (out >= 0).all()
    assert (out <= 100).all()
