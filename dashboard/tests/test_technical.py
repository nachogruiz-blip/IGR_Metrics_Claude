"""Indicadores técnicos contra valores cerrados o identidades."""

import numpy as np
import pandas as pd
import pytest

from stockdash import technical as ta

IDX = pd.bdate_range("2024-01-01", periods=300)


def bars(close, spread=1.0):
    close = pd.Series(np.asarray(close, float), index=IDX[: len(close)])
    return pd.DataFrame({"Open": close, "High": close + spread, "Low": close - spread,
                         "Close": close, "Volume": 1e6})


def test_sma_ema_constant():
    s = pd.Series(np.full(50, 7.0))
    assert ta.sma(s, 20).iloc[-1] == pytest.approx(7.0)
    assert ta.ema(s, 20).iloc[-1] == pytest.approx(7.0)
    assert ta.sma(s, 20).iloc[:19].isna().all()


def test_rsi_extremes():
    up = pd.Series(np.arange(1.0, 60.0))
    assert ta.rsi(up).iloc[-1] == pytest.approx(100.0)
    assert ta.rsi(-up).iloc[-1] == pytest.approx(0.0)
    flat = pd.Series(np.full(60, 3.0))
    assert ta.rsi(flat).iloc[-1] == pytest.approx(50.0)


def test_rsi_symmetric_oscillation():
    # +1, −1 alternos: subidas y bajadas medias iguales en el límite → RSI → 50
    x = pd.Series(np.cumsum(np.tile([1.0, -1.0], 200)))
    assert ta.rsi(x).iloc[-1] == pytest.approx(50.0, abs=2.0)


def test_macd_linear_trend_closed_form():
    # En una recta de pendiente a, la EMA de span n va retrasada a·(n−1)/2:
    # MACD → a·((26−1) − (12−1))/2 = 7a y el histograma → 0.
    a = 0.5
    m = ta.macd(pd.Series(100 + a * np.arange(400.0)))
    assert m["macd"].iloc[-1] == pytest.approx(7 * a, rel=1e-6)
    assert m["hist"].iloc[-1] == pytest.approx(0.0, abs=1e-6)


def test_bollinger_pctb_bounds():
    rng = np.random.default_rng(0)
    c = pd.Series(100 + np.cumsum(rng.standard_normal(300)))
    b = ta.bollinger(c)
    inside = b["pctb"].dropna()
    # %B = 0.5 exactamente cuando el precio está en la media
    assert ((b["mid"] - b["lower"]) / (b["upper"] - b["lower"])).dropna().round(12).eq(0.5).all()
    assert inside.between(-1.5, 2.5).all()


def test_atr_constant_range():
    df = bars(np.full(100, 50.0), spread=1.0)  # rango verdadero = 2 cada día
    assert ta.atr(df).iloc[-1] == pytest.approx(2.0)


def test_adx_strong_uptrend():
    df = bars(100 + np.arange(200.0), spread=0.5)
    d = ta.adx(df)
    assert d["plus_di"].iloc[-1] > 30 and d["minus_di"].iloc[-1] == pytest.approx(0.0)
    assert d["adx"].iloc[-1] > 90


def test_obv():
    c = pd.Series([1.0, 2.0, 1.5, 1.5, 3.0])
    v = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
    assert ta.obv(c, v).tolist() == [0.0, 20.0, -10.0, -10.0, 40.0]


def test_realized_vol_recovers_sigma():
    rng = np.random.default_rng(1)
    sigma = 0.3
    r = sigma / np.sqrt(252) * rng.standard_normal(20000)
    c = pd.Series(np.exp(np.cumsum(r)))
    est = ta.realized_vol(c, 20000 - 1).iloc[-1]
    stderr = sigma / np.sqrt(2 * 20000)
    assert abs(est - sigma) < 4 * stderr


def test_snapshot_keys_and_values():
    df = bars(100 * np.exp(0.001 * np.arange(300)))
    s = ta.snapshot(df, bench_close=df["Close"])
    assert s["rel_strength_3m"] == pytest.approx(0.0)
    assert s["ret_1m"] == pytest.approx(np.exp(0.021) - 1)
    assert s["dist_sma200"] > 0 and s["sma50_vs_200"] > 0
    assert s["dd_52w"] < 0 and s["dd_52w"] > -0.02  # máximo intradía = cierre + 1
