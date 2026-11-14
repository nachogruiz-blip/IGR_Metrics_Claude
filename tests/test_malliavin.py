"""Tests de identidades teóricas: si alguno falla, la implementación contradice la teoría."""

import numpy as np
import pytest

from malliavin import bs, chaos, clark_ocone, density, derivative, greeks, skorokhod
from malliavin.brownian import TimeGrid, brownian_increments, gbm_from_brownian, paths_from_increments, rng

S0, K, T, R, SIG = 100.0, 100.0, 1.0, 0.05, 0.2


def within(est, ref, k=4.0, abs_tol=0.0):
    return abs(est.value - ref) <= k * est.stderr + abs_tol


# --- Caos -----------------------------------------------------------------

def test_chaos_exponential_exact():
    a = chaos.chaos_coefficients(lambda w: np.exp(SIG * w - 0.5 * SIG**2 * T), T, 8)
    np.testing.assert_allclose(a, chaos.exponential_martingale_coefficients(SIG, T, 8), atol=1e-12)


def test_chaos_energy_equals_variance():
    a = chaos.chaos_coefficients(lambda w: np.maximum(w, 0.0), T, 40)
    var = 0.5 * T - T / (2 * np.pi)  # Var(W_T^+)
    assert abs(chaos.chaos_energy(a)[1:].sum() - var) < 2e-3


# --- Derivada -------------------------------------------------------------

@pytest.fixture
def setup_paths():
    grid = TimeGrid(T, 50)
    dW = brownian_increments(grid, 200, rng(0))
    return grid, dW, paths_from_increments(dW)


def test_discrete_derivative_cubic(setup_paths):
    grid, dW, W = setup_paths
    D = derivative.discrete_malliavin_derivative(lambda w: w[:, -1] ** 3, dW)
    np.testing.assert_allclose(D, derivative.analytic_terminal_power(W, grid, 3), rtol=1e-6, atol=1e-6)


def test_discrete_derivative_time_integral(setup_paths):
    grid, dW, W = setup_paths
    F = lambda w: w[:, :-1].sum(axis=1) * grid.dt  # Riemann izquierda
    D = derivative.discrete_malliavin_derivative(F, dW)
    np.testing.assert_allclose(D, derivative.analytic_time_integral(W, grid) - grid.dt, atol=1e-8)


def test_discrete_derivative_max(setup_paths):
    grid, dW, W = setup_paths
    D = derivative.discrete_malliavin_derivative(lambda w: w.max(axis=1), dW, eps=1e-9)
    np.testing.assert_allclose(D, derivative.analytic_running_max(W, grid), atol=1e-6)


# --- Integración por partes ----------------------------------------------

def test_skorokhod_nonadapted_ibp():
    grid = TimeGrid(T, 20)
    dW = brownian_increments(grid, 400_000, rng(1))
    W = paths_from_increments(dW)
    WT = W[:, -1]
    h = np.ones(grid.n_steps)
    delta_u = skorokhod.skorokhod_product(WT, np.ones_like(dW), h, dW, grid.dt)
    np.testing.assert_allclose(delta_u, WT**2 - T, atol=1e-10)
    # F = W_T^2: <DF, u> = 2 W_T * W_T * T
    lhs, rhs = skorokhod.integration_by_parts_check(WT**2, 2 * WT[:, None] * np.ones_like(dW), WT[:, None] * np.ones_like(dW), delta_u, grid.dt)
    assert abs(lhs.value - rhs.value) < 4 * (lhs.stderr + rhs.stderr)
    assert abs(lhs.value - 2 * T**2) < 4 * lhs.stderr


# --- Clark–Ocone ----------------------------------------------------------

def test_clark_ocone_quadrature_matches_closed_form(setup_paths):
    grid, dW, W = setup_paths
    q = clark_ocone.integrand_terminal_functional(lambda x: 3 * x**2, W, grid)
    np.testing.assert_allclose(q, clark_ocone.integrand_cubic(W, grid), rtol=1e-10)


def test_clark_ocone_call_replication():
    grid = TimeGrid(T, 2000)
    dW = brownian_increments(grid, 200, rng(2))
    W = paths_from_increments(dW)
    S = gbm_from_brownian(W, grid, S0, R, SIG)
    phi = clark_ocone.integrand_call(S, grid, K, R, SIG)
    M = clark_ocone.reconstruct(bs.call_price(S0, K, T, R, SIG), phi, dW)
    target = np.exp(-R * T) * np.maximum(S[:, -1] - K, 0)
    assert np.sqrt(np.mean((M[:, -1] - target) ** 2)) < 0.4


# --- Griegas --------------------------------------------------------------

@pytest.mark.parametrize("kind", ["call", "digital"])
def test_malliavin_greeks_unbiased(kind):
    WT = rng(3).standard_normal(1_000_000) * np.sqrt(T)
    pay = greeks.call_payoff(K) if kind == "call" else greeks.digital_payoff(K)
    ref = (bs.call_greeks if kind == "call" else bs.digital_greeks)(S0, K, T, R, SIG)
    est = greeks.greeks_malliavin(pay, WT, S0, T, R, SIG)
    for g in ("delta", "gamma", "vega", "rho"):
        assert within(est[g], ref[g]), (g, est[g], ref[g])


def test_asian_delta_malliavin_vs_fd():
    grid = TimeGrid(T, 50)
    pay = greeks.call_payoff(K)
    m = greeks.asian_delta_malliavin(pay, S0, T, R, SIG, grid, 200_000, seed=4)
    fd = greeks.asian_delta_fd(pay, S0, T, R, SIG, grid, 200_000, seed=5)
    assert abs(m.value - fd.value) < 4 * np.hypot(m.stderr, fd.stderr)


# --- Densidad -------------------------------------------------------------

def test_density_matches_lognormal():
    gen = rng(6)
    WT = gen.standard_normal(500_000) * np.sqrt(T)
    ST = S0 * np.exp((R - 0.5 * SIG**2) * T + SIG * WT)
    x = np.array([80.0, 100.0, 120.0])
    p, se = density.gbm_terminal_density(x, WT, ST, SIG, T)
    assert np.all(np.abs(p - bs.lognormal_pdf(x, S0, T, R, SIG)) < 4 * se)


# --- Capítulos 12–14 del PDF ---------------------------------------------

from malliavin import conditional
from malliavin.brownian import TimeGrid as _TG, brownian_paths


def test_localized_delta_unbiased_and_lower_variance():
    WT = rng(7).standard_normal(400_000) * np.sqrt(T)
    dig = greeks.digital_payoff(K)
    reg, regp = greeks.sigmoid_regularization(K)
    loc = greeks.localized_delta(dig, reg, regp, WT, S0, T, R, SIG)
    plain = greeks.greeks_malliavin(dig, WT, S0, T, R, SIG)["delta"]
    assert within(loc, bs.digital_greeks(S0, K, T, R, SIG)["delta"])
    assert loc.stderr < 0.8 * plain.stderr


def test_bel_reduces_to_bs_weight_for_gbm():
    grid = _TG(T, 20)
    dig = greeks.digital_payoff(K)
    est = greeks.bel_delta(dig, lambda x: R * x, lambda x: R + 0 * x, lambda x: SIG * x, lambda x: SIG + 0 * x,
                           S0, T, R, grid, 300_000, seed=8)
    assert within(est, bs.digital_greeks(S0, K, T, R, SIG)["delta"], abs_tol=1e-4)  # sesgo de Euler


def test_conditional_expectation_bs():
    grid = _TG(1.0, 2)
    W = brownian_paths(grid, 40_000, rng(9))
    S = gbm_from_brownian(W, grid, S0, R, SIG)
    H = conditional.bs_conditional_weight(S[:, 1], W[:, 1], W[:, 2], 0.5, 1.0, SIG)
    x = np.array([90.0, 100.0, 110.0])
    est = conditional.conditional_expectation(S[:, 2], S[:, 1], H, x)
    np.testing.assert_allclose(est, x * np.exp(R * 0.5), rtol=0.01)


def test_bermudan_put_lower_estimator_matches_binomial():
    ref = conditional.bermudan_put_binomial(S0, K, T, R, SIG, 5)
    est = conditional.bermudan_put_malliavin(S0, K, T, R, SIG, 5, 1500, seed=10)
    euro = bs.call_price(S0, K, T, R, SIG) - S0 + K * np.exp(-R * T)
    # La regla de ejercicio aprendida es casi óptima: la cota inferior está cerca del árbol
    # (sesgo de suboptimalidad ≤ 1 %) y por encima de la europea.
    assert est.low <= ref + 4 * est.low_stderr
    assert est.low >= 0.99 * ref - 4 * est.low_stderr
    assert est.low > euro
    assert abs(est.high - ref) / ref < 0.08


def test_conditional_expectation_never_returns_garbage():
    """En las colas el estimador devuelve NaN o un valor razonable, nunca valores absurdos."""
    grid = _TG(1.0, 2)
    W = brownian_paths(grid, 2000, rng(12))
    S = gbm_from_brownian(W, grid, S0, R, SIG)
    H = conditional.bs_conditional_weight(S[:, 1], W[:, 1], W[:, 2], 0.5, 1.0, SIG)
    x = np.geomspace(20.0, 400.0, 40)
    exact = x * np.exp(R * 0.5)
    for loc in (False, True):
        est, se = conditional.conditional_expectation(S[:, 2], S[:, 1], H, x, localize=loc, return_stderr=True)
        ok = np.isnan(est) | (np.abs(est - exact) <= 4 * se)
        assert ok.all(), (loc, x[~ok], est[~ok], exact[~ok])
        assert np.isnan(est[0])  # x = 20: sin muestras cerca, no se extrapola
        assert np.isfinite(est[(x > 85) & (x < 120)]).all()


def test_cev_absorption_keeps_estimators_finite():
    grid = _TG(T, 50)
    s0 = 1.5  # volatilidad CEV alta: muchas trayectorias tocan 0
    b, db = (lambda x: R * x), (lambda x: R + 0 * x)
    sg = lambda x: s0 * np.maximum(x, 0) ** 0.5
    dsg = lambda x: 0.5 * s0 * np.maximum(x, 1e-300) ** -0.5
    dW = brownian_increments(grid, 20_000, rng(13))
    X, Y = greeks.diffusion_with_tangent(b, db, sg, dsg, 1.0, grid, dW)
    assert np.all(np.isfinite(X)) and np.all(np.isfinite(Y)) and np.all(X >= 0)
    assert (X[:, -1] == 0).mean() > 0.1
    # Una trayectoria absorbida se queda en 0.
    hit = np.argmax(X == 0, axis=1)
    rows = np.flatnonzero((X == 0).any(axis=1))[:50]
    assert all(np.all(X[i, hit[i]:] == 0) for i in rows)


def test_directional_derivative_matches_inner_product(setup_paths):
    grid, dW, W = setup_paths
    h = lambda t: np.cos(3 * t)
    F = lambda w: w[:, -1] ** 3
    lhs = derivative.directional_derivative(F, W, grid, h)
    D = derivative.analytic_terminal_power(W, grid, 3)
    rhs = (D * h(grid.t[:-1])).sum(axis=1) * grid.dt
    np.testing.assert_allclose(lhs, rhs, rtol=1e-6, atol=1e-8)


def test_clark_ocone_digital_replication():
    grid = _TG(T, 4000)
    dW = brownian_increments(grid, 300, rng(11))
    S = gbm_from_brownian(paths_from_increments(dW), grid, S0, R, SIG)
    M = clark_ocone.reconstruct(bs.digital_price(S0, K, T, R, SIG), clark_ocone.integrand_digital(S, grid, K, R, SIG), dW)
    target = np.exp(-R * T) * (S[:, -1] > K)
    # la cobertura de una digital falla cerca del strike en el vencimiento: se mide la mediana
    assert np.median(np.abs(M[:, -1] - target)) < 0.05


# --- Volatilidad estocástica (PDF §14.3–14.4) ------------------------------

from malliavin import stochvol


def test_rbergomi_exact_simulation_moments():
    H, eta, xi0 = 0.1, 1.9, 0.04
    p = stochvol.rough_bergomi_paths(1.0, 50, 100_000, H, eta, xi0, rng(20))
    # E[σ_t²] = ξ₀ y corr(W_1, Ŵ^H_1) = √(2H)/(H+½)
    np.testing.assert_allclose(p.var[:, [10, 50]].mean(axis=0), xi0, rtol=0.03)
    Wh1 = (np.log(p.var[:, -1] / xi0) + 0.5 * eta**2) / eta
    assert abs(np.corrcoef(p.W[:, -1], Wh1)[0, 1] - np.sqrt(2 * H) / (H + 0.5)) < 0.01
    assert abs(Wh1.var() - 1.0) < 0.02  # Var Ŵ^H_1 = 1


def test_alos_decomposition_identity():
    """PDF Teorema 14.5: precio = término de Hull–White + corrección por correlación."""
    H, eta, xi0, rho = 0.3, 1.0, 0.04, -0.7
    p = stochvol.rough_bergomi_paths(1.0, 100, 60_000, H, eta, xi0, rng(21))
    for K in (100.0, 110.0):
        d = stochvol.alos_decomposition_rbergomi(p, 100.0, K, 0.0, rho, rng(22))
        se = np.sqrt(d.price_se**2 + d.hull_white_se**2 + d.correction_se**2)
        assert abs(d.price - d.hull_white) > 10 * se  # Hull–White solo no basta con ρ ≠ 0
        assert abs(d.price - d.alos) < 4 * se + 0.01 * d.price  # tolerancia: discretización


def test_heston_short_time_skew():
    v0, nu, rho = 0.04, 0.5, -0.7
    p = stochvol.heston_paths(0.01, 100, 300_000, v0, 1.5, 0.04, nu, rng(23))
    limit = stochvol.heston_skew_limit(v0, nu, rho)
    assert abs(stochvol.atm_skew(p, 100.0, 0.0, rho) / limit - 1) < 0.08


def test_rbergomi_skew_power_law():
    """PDF Teorema 14.6(b): skew ATM ∝ T^{H−1/2}."""
    H, eta, xi0, rho = 0.1, 1.9, 0.04, -0.9
    Ts = (0.005, 0.5)
    sk = [stochvol.atm_skew(stochvol.rough_bergomi_paths(T, 100, 100_000, H, eta, xi0, rng(24)), 100.0, 0.0, rho)
          for T in Ts]
    slope = np.log(sk[0] / sk[1]) / np.log(Ts[1] / Ts[0])
    assert abs(slope - (0.5 - H)) < 0.06
