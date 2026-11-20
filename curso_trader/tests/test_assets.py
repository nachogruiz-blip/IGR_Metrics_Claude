"""Clases de activo: renta variable, FX, materias primas, renta fija, opciones y cripto."""
import math

import numpy as np
import pandas as pd
import pytest

from trader import commodities as cm
from trader import crypto, data, equity as eq, fx, options as op, rates


# ---------------------------------------------------------------- renta variable
def test_beta_and_capm():
    rng = np.random.default_rng(0)
    m = 0.01 * rng.standard_normal(5000)
    a = 0.0002 + 1.3 * m + 0.005 * rng.standard_normal(5000)
    assert eq.beta(a, m) == pytest.approx(1.3, abs=4 * 0.005 / (0.01 * math.sqrt(5000)))
    c = eq.capm(a, m)
    assert c["beta"] == pytest.approx(1.3, abs=0.03) and c["alpha_annual"] == pytest.approx(0.05, abs=4 * 0.005 / math.sqrt(5000) * 252)


def test_pair_tools():
    df = data.synthetic_pair(3000, beta=1.3, half_life=15, seed=4)
    assert eq.hedge_ratio(df["y"], df["x"]) == pytest.approx(1.3, abs=0.05)
    s = eq.spread(df["y"], df["x"], 1.3)
    assert eq.half_life(s) == pytest.approx(15, rel=0.3)
    assert eq.adf_tstat(s) < -3.34
    rw = np.cumsum(np.random.default_rng(1).standard_normal(3000))
    assert eq.adf_tstat(rw) > -2.86
    z = eq.rolling_zscore(s, 60)
    assert set(eq.pair_positions(z).unique()) <= {-1.0, 0.0, 1.0}


def test_dollar_neutral():
    ny, nx = eq.dollar_neutral_shares(100_000, 50, 25, 1.0)
    assert ny * 50 == pytest.approx(nx * 25, rel=0.01)


def test_momentum_and_gaps():
    px = data.synthetic_universe(["A", "B", "C"], 400)
    mom = eq.momentum_12_1(px)
    assert list(mom.index) == sorted(mom.index, key=lambda k: -mom[k])
    g = eq.gap_stats(data.synthetic_ohlc(500), 0.002)
    assert g["n_gaps"] == g["gap_up"] + g["gap_down"]


# ---------------------------------------------------------------- FX
def test_pip_values():
    assert fx.pip_value("EURUSD", 1.08) == pytest.approx(10.0)
    assert fx.pip_value("USDJPY", 150.0) == pytest.approx(1000 / 150)  # cuenta en USD (base)
    assert fx.pip_value("EURGBP", 0.85, account_ccy="USD", quote_to_account=1.27) == pytest.approx(12.7)
    assert fx.lots_for_risk(10_000, 0.01, 20, 10) == pytest.approx(0.5)


def test_cross_and_triangular():
    q = {"EURUSD": 1.10, "USDJPY": 150.0, "GBPUSD": 1.30}
    assert fx.cross_rate(q, "EURJPY") == pytest.approx(165.0)
    assert fx.cross_rate(q, "EURGBP") == pytest.approx(1.10 / 1.30)
    assert fx.triangular_arbitrage(1.10, 150.0, 165.0) == pytest.approx(0.0)


def test_cip_and_carry():
    f = fx.forward_rate(1.10, 0.05, 0.03, 1.0)
    assert f == pytest.approx(1.10 * 1.05 / 1.03)
    # Si el spot acaba en el forward, el carry es exactamente cero.
    assert fx.carry_return(1.10, f, 0.03, 0.05, 1.0) == pytest.approx(0.0, abs=1e-12)
    assert fx.forward_points(1.10, f, "EURUSD") == pytest.approx((f - 1.10) / 1e-4)


def test_sessions():
    assert "Londres" in fx.open_sessions(13) and "Nueva York" in fx.open_sessions(13)
    assert fx.open_sessions(23) == ["Sídney"]


# ---------------------------------------------------------------- materias primas
def test_contract_specs():
    assert cm.CONTRACTS["CL"].tick_value == pytest.approx(10)
    assert cm.CONTRACTS["GC"].tick_value == pytest.approx(10)
    assert cm.CONTRACTS["ZC"].tick_value == pytest.approx(12.5)
    assert cm.futures_position_size("CL", 500_000, 0.01, 75, 73.5) == 3


def test_carry_and_roll_yield():
    f = cm.cost_of_carry_forward(80, 0.05, 0.02, 0.10, 0.5)
    assert cm.implied_convenience_yield(80, f, 0.05, 0.02, 0.5) == pytest.approx(0.10)
    curve = cm.synthetic_curve(80, [0.1, 0.2, 0.3], 0.05, 0.02, 0.0)
    assert cm.curve_shape(curve) == "contango"
    np.testing.assert_allclose(cm.roll_yield_curve(curve, [0.1, 0.2, 0.3]).values, -0.07)
    assert cm.roll_yield(90, 85, 0.1, 0.6) > 0


def test_spreads():
    assert cm.crack_spread_321(80, 2.5, 2.8) == pytest.approx((2 * 105 + 117.6 - 240) / 3)
    assert cm.crush_spread(12.0, 350, 50) == pytest.approx(7.7 + 5.5 - 12)
    assert cm.spark_spread(50, 3, 7) == pytest.approx(29)


def test_back_adjust_preserves_returns():
    old = pd.Series([100.0, 101, 102, np.nan, np.nan])
    new = pd.Series([np.nan, np.nan, 105, 106, 104])
    front = pd.Series([100.0, 101, 105, 106, 104])  # rueda el día 2
    ratio = pd.Series([1.0, 1, 105 / 102, 1, 1])
    adj = cm.ratio_back_adjust(front, ratio)
    held = pd.Series([100.0, 101, 102, np.nan, np.nan])
    assert adj.iloc[2] / adj.iloc[1] == pytest.approx(held.iloc[2] / held.iloc[1])
    assert adj.iloc[-1] == front.iloc[-1]
    del old, new


def test_seasonality_shape():
    s = data.synthetic_ohlc(800)["close"]
    assert len(cm.monthly_seasonality(s)) == 12


# ---------------------------------------------------------------- renta fija
def test_bond_par_and_zero():
    assert rates.bond_price(100, 0.04, 0.04, 10) == pytest.approx(100)
    assert rates.macaulay_duration(100, 0.0, 0.03, 7, 1) == pytest.approx(7)
    p = rates.bond_price(100, 0.05, 0.06, 8)
    assert rates.ytm(p, 100, 0.05, 8) == pytest.approx(0.06)


def test_duration_convexity_fd():
    args = (100, 0.045, 0.05, 10)
    h = 1e-4
    p0, pu, pd_ = rates.bond_price(*args), rates.bond_price(100, 0.045, 0.05 + h, 10), rates.bond_price(100, 0.045, 0.05 - h, 10)
    assert rates.modified_duration(*args) == pytest.approx(-(pu - pd_) / (2 * h) / p0, rel=1e-6)
    assert rates.convexity(*args) == pytest.approx((pu + pd_ - 2 * p0) / h**2 / p0, rel=1e-4)
    assert rates.dv01(*args) == pytest.approx((pd_ - pu) / 2, rel=1e-6)
    dp = rates.price_change_approx(p0, rates.modified_duration(*args), rates.convexity(*args), 0.01)
    assert dp == pytest.approx(rates.bond_price(100, 0.045, 0.06, 10) - p0, rel=0.01)


# ---------------------------------------------------------------- opciones
def test_put_call_parity_and_iv():
    S, K, T, r, q, s = 100, 105, 0.5, 0.03, 0.01, 0.25
    c, p = op.bs_price(S, K, T, r, s, q, "call"), op.bs_price(S, K, T, r, s, q, "put")
    assert c - p == pytest.approx(S * math.exp(-q * T) - K * math.exp(-r * T))
    assert op.implied_vol(float(c), S, K, T, r, q) == pytest.approx(s, abs=1e-8)
    assert op.black76(100, 100, 1, 0.05, 0.2) == pytest.approx(op.black76(100, 100, 1, 0.05, 0.2, "put"))
    # Black-76 = e^{−rT}·Black-Scholes sin tipos sobre F.
    assert op.black76(100, 95, 1, 0.05, 0.2) == pytest.approx(math.exp(-0.05) * op.bs_price(100, 95, 1, 0, 0.2))


def test_greeks_fd():
    S, K, T, r, s = 100, 100, 0.4, 0.02, 0.3
    g = op.greeks(S, K, T, r, s, kind="put")
    h = 1e-3
    f = lambda **kw: float(op.bs_price(**{**dict(S=S, K=K, T=T, r=r, sigma=s, kind="put"), **kw}))  # noqa: E731
    assert g["delta"] == pytest.approx((f(S=S + h) - f(S=S - h)) / (2 * h), rel=1e-5)
    assert g["gamma"] == pytest.approx((f(S=S + h) - 2 * f() + f(S=S - h)) / h**2, rel=1e-3)
    assert g["vega"] == pytest.approx((f(sigma=s + h) - f(sigma=s - h)) / (2 * h) / 100, rel=1e-5)
    assert g["theta"] == pytest.approx(-(f(T=T + h) - f(T=T - h)) / (2 * h) / 365, rel=1e-4)


def test_expected_move_and_straddle():
    assert op.expected_move(100, 0.365, 365) == pytest.approx(36.5)
    S, T, s = 100, 30 / 365, 0.3
    st = float(op.bs_price(S, S, T, 0, s) + op.bs_price(S, S, T, 0, s, kind="put"))
    assert op.straddle_implied_move(S, st) == pytest.approx(math.sqrt(2 / math.pi) * s * math.sqrt(T), rel=0.01)
    assert op.straddle_breakevens(100, 3, 2) == (95, 105)
    assert op.payoff([90, 110], [("call", 100, 1, 2)]).tolist() == [-2, 8]


# ---------------------------------------------------------------- cripto
def test_crypto():
    assert crypto.annualized_funding(0.0001) == pytest.approx(0.1095)
    assert crypto.annualized_basis(100, 101, 36.5) == pytest.approx(0.1)
    assert crypto.liquidation_price(100, 10, 0.0) == pytest.approx(90)
    assert crypto.liquidation_price(100, 10, 0.0, "short") == pytest.approx(110)
