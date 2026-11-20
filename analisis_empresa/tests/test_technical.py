import numpy as np
import pandas as pd

from analyst import data, technical as te


def _ohlc(close):
    close = pd.Series(close, index=pd.bdate_range("2024-01-01", periods=len(close)), dtype=float)
    return pd.DataFrame({"Open": close, "High": close * 1.01, "Low": close * 0.99, "Close": close,
                         "Volume": 1e6})


def test_rsi_extremes():
    assert te.rsi(pd.Series(np.arange(1, 60.0))).iloc[-1] == 100
    assert te.rsi(pd.Series(np.full(60, 5.0))).iloc[-1] == 50
    assert te.rsi(pd.Series(np.arange(60, 1.0, -1))).iloc[-1] == 0


def test_last_cross():
    i = pd.RangeIndex(6)
    kind, when = te.last_cross(pd.Series([1, 1, 1, 3, 3, 3.0], i), pd.Series([2.0] * 6, i))
    assert kind == "alcista" and when == 3


def test_levels_find_repeated_turning_points():
    x = np.arange(300)
    close = 100 + 10 * np.sin(2 * np.pi * x / 50)            # techos ≈ 110, suelos ≈ 90
    lv = te.levels(_ohlc(close), lookback=300, window=10)
    assert any(abs(l - 111) < 2 and n >= 4 for l, n in lv)
    assert any(abs(l - 89) < 2 and n >= 4 for l, n in lv)


def test_trend_classification_on_demo():
    up = te.analyze(data.demo("DEMO-COMPRA").prices)
    down = te.analyze(data.demo("DEMO-VENDE").prices)
    assert up.trend == "alcista" and up.pillar.score > 0.3
    assert down.trend == "bajista" and down.pillar.score < -0.3
    assert up.support < up.price
