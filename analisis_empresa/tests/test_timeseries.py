import numpy as np
import pandas as pd
from scipy import stats

from analyst import timeseries as ts


def _simulate_garch(n, omega, alpha, beta, seed=0):
    rng = np.random.default_rng(seed)
    z = rng.standard_normal(n)
    eps, s2 = np.empty(n), omega / (1 - alpha - beta)
    for t in range(n):
        eps[t] = np.sqrt(s2) * z[t]
        s2 = omega + alpha * eps[t] ** 2 + beta * s2
    return eps


def test_garch_filter_matches_explicit_recursion():
    eps = np.random.default_rng(1).standard_normal(300) * 0.01
    o, a, b, s0 = 2e-6, 0.07, 0.9, 1e-4
    out = ts.garch_filter(eps, o, a, b, s0)
    ref = [s0]
    for e in eps:
        ref.append(o + a * e ** 2 + b * ref[-1])
    np.testing.assert_allclose(out, ref, rtol=1e-12)


def test_garch_recovers_parameters():
    eps = _simulate_garch(6000, 2e-6, 0.08, 0.90, seed=3)
    g = ts.fit_garch(eps)
    assert abs(g.alpha - 0.08) < 0.03
    assert abs(g.beta - 0.90) < 0.04
    assert abs(g.long_run_vol - np.sqrt(252 * 2e-6 / 0.02)) < 0.05


def test_garch_forecast_converges_to_long_run():
    g = ts.fit_garch(_simulate_garch(3000, 2e-6, 0.1, 0.85, seed=5))
    assert abs(g.forecast_vol(50_000) - g.long_run_vol) < 0.01 * g.long_run_vol
    assert np.isclose(g.forecast_vol(1), np.sqrt(g.sigma2[-1] * 252))


def test_iid_returns_look_random():
    r = np.random.default_rng(7).standard_normal(3000) * 0.01
    assert ts.ljung_box(r)[1] > 0.01
    vr, z = ts.variance_ratio(r, 5)
    assert abs(vr - 1) < 0.1 and abs(z) < 3
    h = ts.hurst(pd.Series(np.exp(np.cumsum(r))))
    assert 0.4 < h < 0.6


def test_ljung_box_detects_ar1():
    rng = np.random.default_rng(2)
    e = rng.standard_normal(2000)
    x = np.empty_like(e)
    x[0] = e[0]
    for t in range(1, len(e)):
        x[t] = 0.3 * x[t - 1] + e[t]
    assert ts.ljung_box(x)[1] < 1e-6


def test_normal_var_matches_quantile():
    r = np.random.default_rng(11).normal(0.0005, 0.02, 20_000)
    v = ts.var_cvar(r, 0.95)
    exact = -(0.0005 + stats.norm.ppf(0.05) * 0.02)
    # error estándar del cuantil muestral: √(q(1−q)/n)/f(x_q)
    se = np.sqrt(0.05 * 0.95 / r.size) / stats.norm.pdf(stats.norm.ppf(0.05, 0, 0.02), 0, 0.02)
    assert abs(v["hist_var"] - exact) < 4 * se
    assert abs(v["normal_var"] - exact) < 4 * se
    assert abs(v["cf_var"] - exact) < 4 * se          # sin asimetría ni curtosis ≈ normal
    assert v["hist_cvar"] > v["hist_var"]
    assert np.isclose(v["normal_cvar"], -(r.mean() - r.std(ddof=1) * stats.norm.pdf(1.645) / 0.05), rtol=1e-3)


def test_drawdown():
    p = pd.Series([100, 120, 90, 130, 117.0])
    dd = ts.drawdown(p)
    assert dd.iloc[2] == 90 / 120 - 1 and dd.iloc[3] == 0 and np.isclose(dd.iloc[4], -0.1)
    assert (dd <= 0).all()


def test_beta_recovered_from_weekly_returns():
    rng = np.random.default_rng(4)
    idx = pd.bdate_range("2020-01-01", periods=1500)
    rb = pd.Series(rng.normal(0, 0.01, 1500), idx)
    r = 1.4 * rb + pd.Series(rng.normal(0, 0.01, 1500), idx)
    out = ts.beta_alpha(r, rb)
    # error estándar de β ≈ σ_e/(σ_m √n) con n ≈ 300 semanas
    se = 1 / np.sqrt(300)
    assert abs(out["beta"] - 1.4) < 4 * se


def test_analyze_on_demo_has_consistent_stats():
    from analyst import data

    cd = data.demo("DEMO-COMPRA")
    out = ts.analyze(cd.prices["Close"], cd.bench, cd.risk_free)
    s = out.stats
    assert 0 < s["vol_annual"] < 1 and s["max_drawdown"] <= s["current_drawdown"] <= 0
    assert 0 <= s["vol21_percentile"] <= 1
    assert out.cone.loc["3 meses", "p05"] < out.cone.loc["1 mes", "p05"] < cd.price < out.cone.loc["1 mes", "p95"]
    assert -1 <= out.pillar.score <= 1
