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
