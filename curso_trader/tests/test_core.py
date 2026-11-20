"""Indicadores, riesgo, rendimiento y backtest contra valores cerrados o identidades."""
import math

import numpy as np
import pandas as pd
import pytest

from trader import backtest as bt
from trader import data, indicators as ind, performance as perf, risk


@pytest.fixture(scope="module")
def ohlc():
    return data.synthetic_ohlc(600, seed=3)


def test_synthetic_ohlc_consistent(ohlc):
    assert (ohlc["high"] >= ohlc[["open", "close"]].max(axis=1)).all()
    assert (ohlc["low"] <= ohlc[["open", "close"]].min(axis=1)).all()


def test_load_prices_roundtrip(tmp_path, ohlc):
    p = tmp_path / "x.csv"
    ohlc.rename(columns=str.capitalize).rename_axis("Date").to_csv(p)
    df = data.load_prices(p)
    assert list(df.columns) == list(ohlc.columns)
    np.testing.assert_allclose(df["close"].values, ohlc["close"].values)


def test_rsi_bounds_and_monotone():
    up = pd.Series(np.arange(1, 50, dtype=float))
    assert ind.rsi(up, 14).dropna().eq(100).all()
    s = data.synthetic_ohlc(300, seed=1)["close"]
    r = ind.rsi(s).dropna()
    assert r.between(0, 100).all()


def test_true_range_and_atr(ohlc):
    tr = ind.true_range(ohlc)
    assert (tr >= ohlc["high"] - ohlc["low"] - 1e-12).all()
    const = pd.DataFrame({"high": [11.0] * 30, "low": [9.0] * 30, "close": [10.0] * 30})
    assert ind.atr(const, 14).iloc[-1] == pytest.approx(2.0)


def test_pivots_symmetry():
    p = ind.pivot_points(110, 90, 100)
    assert p["P"] == pytest.approx(100)
    assert p["R1"] - p["P"] == pytest.approx(p["P"] - p["S1"])
    assert p["R2"] == pytest.approx(120) and p["S2"] == pytest.approx(80)


def test_donchian_uses_past_only(ohlc):
    d = ind.donchian(ohlc, 10)
    assert d["upper"].iloc[20] == pytest.approx(ohlc["high"].iloc[10:20].max())


def test_position_size_stop():
    # 100 000 € al 1 % con stop a 2 €: 500 acciones.
    assert risk.position_size_stop(100_000, 0.01, 50, 48) == 500
    # CL: stop 1,50 $ × 1000 $/punto = 1500 $/contrato; riesgo 5000 $ → 3 contratos.
    assert risk.position_size_stop(500_000, 0.01, 75, 73.5, point_value=1000) == 3


def test_kelly_is_argmax_of_growth():
    p, b = 0.55, 1.0
    f = np.linspace(0.001, 0.5, 5000)
    g = risk.growth_rate(f, p, b)
    assert f[np.argmax(g)] == pytest.approx(risk.kelly_fraction(p, b), abs=1e-3)
    assert risk.growth_rate(2 * risk.kelly_fraction(p, b), p, b) < 1e-3  # 2·Kelly ⇒ crecimiento ≈ 0


def test_risk_of_ruin_monotone():
    a = risk.risk_of_ruin_mc(0.5, 1.5, 0.01, 0.3, 300, 4000)
    b = risk.risk_of_ruin_mc(0.5, 1.5, 0.05, 0.3, 300, 4000)
    assert a < b


def test_var_es_gaussian():
    assert risk.var_parametric(0, 1, 0.99) == pytest.approx(2.3263, abs=1e-4)
    assert risk.es_parametric(0, 1, 0.975) == pytest.approx(2.3378, abs=1e-4)
    rng = np.random.default_rng(0)
    x = rng.standard_normal(400_000)
    assert risk.var_historical(x, 0.99) == pytest.approx(2.3263, abs=0.02)
    assert risk.es_historical(x, 0.975) == pytest.approx(2.3378, abs=0.02)


def test_risk_contributions_sum():
    cov = np.array([[0.04, 0.006], [0.006, 0.09]])
    w = np.array([0.6, 0.4])
    rc = risk.risk_contributions(w, cov)
    assert rc.sum() == pytest.approx(risk.portfolio_vol(w, cov))
    w_iv = risk.inverse_vol_weights([0.2, 0.3])
    assert w_iv[0] * 0.2 == pytest.approx(w_iv[1] * 0.3)


def test_drawdown_known():
    assert risk.max_drawdown([100, 120, 90, 130, 65]) == pytest.approx(-0.5)


def test_sharpe_and_cagr():
    r = np.full(252, 0.001)
    assert perf.cagr(r) == pytest.approx(1.001**252 - 1)
    rng = np.random.default_rng(1)
    x = 0.0004 + 0.01 * rng.standard_normal(252 * 40)
    # Error estándar del Sharpe anualizado ≈ √(periodos·(1 + SR²/2)/n) con SR por periodo.
    se = math.sqrt(252 * (1 + 0.5 * 0.04**2) / len(x))
    assert perf.sharpe(x) == pytest.approx(0.04 * math.sqrt(252), abs=4 * se)


def test_psr_properties():
    rng = np.random.default_rng(2)
    good = 0.002 + 0.01 * rng.standard_normal(2000)
    assert perf.probabilistic_sharpe(good) > 0.99
    assert perf.probabilistic_sharpe(-good) < 0.01


def test_expected_max_sharpe_vs_mc():
    rng = np.random.default_rng(3)
    sims = rng.standard_normal((20_000, 100)).max(axis=1)
    assert perf.expected_max_sharpe(100) == pytest.approx(sims.mean(), abs=4 * sims.std() / math.sqrt(20_000) + 0.02)


def test_trade_stats():
    s = perf.trade_stats([2, -1, 3, -1])
    assert s["hit_rate"] == 0.5 and s["payoff"] == 2.5 and s["profit_factor"] == 2.5
    assert s["expectancy"] == pytest.approx(0.75)


def test_backtest_no_lookahead():
    close = pd.Series([100, 110, 99, 99], dtype=float)
    pos = pd.Series([1, 1, 0, 0], dtype=float)  # decidido al cierre
    res = bt.backtest(close, pos, cost_bps=0)
    # Día 1 gana +10 % (posición del día 0); día 2 pierde −10 % (posición del día 1); luego plano.
    np.testing.assert_allclose(res["strategy"].values, [0, 0.10, -0.10, 0], atol=1e-12)


def test_backtest_costs():
    close = pd.Series([100.0] * 5)
    pos = pd.Series([0, 1, -1, -1, 0], dtype=float)
    res = bt.backtest(close, pos, cost_bps=10)
    assert res["strategy"].sum() == pytest.approx(-(1 + 2 + 1) * 10e-4)


def test_strategies_and_trades(ohlc):
    for pos in (bt.sma_crossover(ohlc["close"], 10, 50), bt.donchian_breakout(ohlc, 20, 10),
                bt.rsi_reversion(ohlc["close"])):
        assert set(pos.unique()) <= {-1.0, 0.0, 1.0}
    pos = bt.sma_crossover(ohlc["close"], 10, 50)
    tr = bt.trades(ohlc["close"], pos)
    res = bt.backtest(ohlc["close"], pos, cost_bps=0)
    # El producto de (1+ret) de las operaciones = equity final sin costes.
    assert np.prod(1 + tr["ret"]) == pytest.approx(res["equity"].iloc[-1])


def test_vol_target(ohlc):
    pos = bt.vol_targeted(pd.Series(1.0, index=ohlc.index), ohlc["close"], target=0.10)
    res = bt.backtest(ohlc["close"], pos, 0)
    assert perf.annual_vol(res["strategy"].iloc[30:]) == pytest.approx(0.10, rel=0.25)


def test_walk_forward():
    sp = bt.walk_forward_splits(100, 50, 10)
    assert len(sp) == 5 and all(tr.stop == te.start for tr, te in sp)
