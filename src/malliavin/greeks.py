r"""Griegas por cálculo de Malliavin (Fournié, Lasry, Lebuchoux, Lions, Touzi 1999).

Modelo: S_T = S_0 exp((r - σ²/2)T + σ W_T) bajo Q. Para un pago Φ (sólo medible,
p.ej. digital) la integración por partes traslada la derivada del pago a un peso:

    ∂_θ E[e^{-rT} Φ(S_T)] = E[e^{-rT} Φ(S_T) π_θ],

con pesos (no dependen de Φ):

    π_Δ = W_T / (S_0 σ T)
    π_V = W_T²/(σT) - W_T - 1/σ
    π_Γ = π_V / (S_0² σ T)
    π_ρ = W_T/σ - T

Opción asiática A = (1/T)∫_0^T S_t dt  (derivación en docs/guia_libreria.md):

    π_Δ^{asiática} = (1/S_0) [ 2(S_T - S_0)/(σ² T A) - 2r/σ² + 1 ].

Se comparan con diferencias finitas (con números aleatorios comunes) y con el
método pathwise, que requiere Φ diferenciable.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from .brownian import TimeGrid, brownian_paths, gbm_from_brownian, rng
from .skorokhod import MCEstimate, mc

Payoff = Callable[[np.ndarray], np.ndarray]


def call_payoff(K: float) -> Payoff:
    return lambda s: np.maximum(s - K, 0.0)


def digital_payoff(K: float) -> Payoff:
    return lambda s: (s > K).astype(float)


def malliavin_weights(WT: np.ndarray, S0: float, T: float, r: float, sigma: float) -> dict[str, np.ndarray]:
    """Pesos de Malliavin para GBM (ver docstring del módulo)."""
    pv = WT**2 / (sigma * T) - WT - 1.0 / sigma
    return {
        "delta": WT / (S0 * sigma * T),
        "vega": pv,
        "gamma": pv / (S0**2 * sigma * T),
        "rho": WT / sigma - T,
    }


def greeks_malliavin(
    payoff: Payoff, WT: np.ndarray, S0: float, T: float, r: float, sigma: float
) -> dict[str, MCEstimate]:
    """Griegas europeas con pesos de Malliavin a partir de muestras de W_T."""
    ST = S0 * np.exp((r - 0.5 * sigma**2) * T + sigma * WT)
    disc_pay = np.exp(-r * T) * payoff(ST)
    return {k: mc(disc_pay * w) for k, w in malliavin_weights(WT, S0, T, r, sigma).items()}


def _price_samples(payoff, WT, S0, T, r, sigma):
    ST = S0 * np.exp((r - 0.5 * sigma**2) * T + sigma * WT)
    return np.exp(-r * T) * payoff(ST)


def greeks_finite_difference(
    payoff: Payoff, WT: np.ndarray, S0: float, T: float, r: float, sigma: float, h: float = 1e-2
) -> dict[str, MCEstimate]:
    """Diferencias centradas con números aleatorios comunes. h es relativo para S0 y σ."""
    P = lambda s0=S0, rr=r, sg=sigma: _price_samples(payoff, WT, s0, T, rr, sg)
    hs, hv, hr = h * S0, h * sigma, h * max(abs(r), 1e-2)
    up, mid, dn = P(S0 + hs), P(), P(S0 - hs)
    return {
        "delta": mc((up - dn) / (2 * hs)),
        "gamma": mc((up - 2 * mid + dn) / hs**2),
        "vega": mc((P(sg=sigma + hv) - P(sg=sigma - hv)) / (2 * hv)),
        "rho": mc((P(rr=r + hr) - P(rr=r - hr)) / (2 * hr)),
    }


def greeks_pathwise_call(WT: np.ndarray, S0: float, K: float, T: float, r: float, sigma: float) -> dict[str, MCEstimate]:
    """Método pathwise (derivada dentro de la esperanza) para la call: requiere Φ Lipschitz."""
    ST = S0 * np.exp((r - 0.5 * sigma**2) * T + sigma * WT)
    disc = np.exp(-r * T)
    itm = (ST > K).astype(float)
    return {
        "delta": mc(disc * itm * ST / S0),
        "vega": mc(disc * itm * ST * (WT - sigma * T)),
        "rho": mc(disc * (itm * ST * T - T * np.maximum(ST - K, 0.0))),
    }


# --- Asiática --------------------------------------------------------------

def _asian_average(S: np.ndarray) -> np.ndarray:
    """(1/T)∫S dt por la regla del trapecio en malla uniforme."""
    return 0.5 * (S[:, :-1] + S[:, 1:]).mean(axis=1)


def asian_delta_malliavin(
    payoff: Payoff, S0: float, T: float, r: float, sigma: float, grid: TimeGrid, n_paths: int, seed: int | None = None
) -> MCEstimate:
    W = brownian_paths(grid, n_paths, rng(seed))
    S = gbm_from_brownian(W, grid, S0, r, sigma)
    A = _asian_average(S)
    weight = (2 * (S[:, -1] - S0) / (sigma**2 * T * A) - 2 * r / sigma**2 + 1) / S0
    return mc(np.exp(-r * T) * payoff(A) * weight)


def asian_delta_fd(
    payoff: Payoff, S0: float, T: float, r: float, sigma: float, grid: TimeGrid, n_paths: int,
    seed: int | None = None, h: float = 1e-2,
) -> MCEstimate:
    W = brownian_paths(grid, n_paths, rng(seed))
    hs = h * S0
    A_up = _asian_average(gbm_from_brownian(W, grid, S0 + hs, r, sigma))
    A_dn = _asian_average(gbm_from_brownian(W, grid, S0 - hs, r, sigma))
    return mc(np.exp(-r * T) * (payoff(A_up) - payoff(A_dn)) / (2 * hs))


# --- Localización (PDF §12.6–12.7) -----------------------------------------

def sigmoid_regularization(K: float, width: float = 5.0) -> tuple[Payoff, Payoff]:
    """Φ_reg(S) = (1 + e^{-(S-K)/width})^{-1} y su derivada (PDF §12.7, width = 5)."""
    def reg(s):
        return 1.0 / (1.0 + np.exp(-(s - K) / width))

    def reg_prime(s):
        g = reg(s)
        return g * (1.0 - g) / width

    return reg, reg_prime


def localized_delta(
    payoff: Payoff, payoff_reg: Payoff, payoff_reg_prime: Payoff,
    WT: np.ndarray, S0: float, T: float, r: float, sigma: float,
) -> MCEstimate:
    """Δ = E[e^{-rT} Φ'_reg(S_T) S_T/S_0] + E[e^{-rT} Φ_sing(S_T) π_Δ],  Φ_sing = Φ − Φ_reg.

    Parte regular por el método pathwise, parte singular con el peso de Malliavin
    (Fournié et al. 1999, 2001; PDF §12.6).
    """
    ST = S0 * np.exp((r - 0.5 * sigma**2) * T + sigma * WT)
    disc = np.exp(-r * T)
    pathwise = payoff_reg_prime(ST) * ST / S0
    weight = (payoff(ST) - payoff_reg(ST)) * WT / (S0 * sigma * T)
    return mc(disc * (pathwise + weight))


# --- Bismut–Elworthy–Li (PDF §12.4) ----------------------------------------

def diffusion_with_tangent(
    b: Callable, db: Callable, sig: Callable, dsig: Callable,
    x0: float, grid: TimeGrid, dW: np.ndarray, absorb_at_zero: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Euler para dX = b(X)dt + σ(X)dW y su proceso tangente Y = ∂X/∂x0:

        dY = b'(X) Y dt + σ'(X) Y dW,   Y_0 = 1.

    Devuelve (X, Y) con forma (n_paths, n_steps+1). Con ``absorb_at_zero`` (por defecto) una
    trayectoria que cruza 0 queda absorbida (X = 0, Y = 0): es la convención para precios de
    activos (CEV, etc.) y evita evaluar σ'(x) en x ≤ 0, donde puede explotar.
    """
    n_paths, n_steps = dW.shape
    X = np.empty((n_paths, n_steps + 1))
    Y = np.empty_like(X)
    X[:, 0], Y[:, 0] = x0, 1.0
    dt = grid.dt
    alive = np.ones(n_paths, dtype=bool)
    for k in range(n_steps):  # bucle temporal (vectorizado en trayectorias)
        x, y = X[:, k], Y[:, k]
        xs = np.where(alive, x, 1.0)  # evita evaluar los coeficientes en 0 (p.ej. σ' de CEV)
        X[:, k + 1] = np.where(alive, x + b(xs) * dt + sig(xs) * dW[:, k], 0.0)
        Y[:, k + 1] = np.where(alive, y + db(xs) * y * dt + dsig(xs) * y * dW[:, k], 0.0)
        if absorb_at_zero:
            hit = alive & (X[:, k + 1] <= 0.0)
            X[hit, k + 1] = 0.0
            Y[hit, k + 1] = 0.0
            alive &= ~hit
    return X, Y


def bel_weight(X: np.ndarray, Y: np.ndarray, sig: Callable, dW: np.ndarray, T: float) -> np.ndarray:
    """Peso de Bismut–Elworthy–Li: (1/T) ∫_0^T σ^{-1}(X_t) Y_t dW_t (integral de Itô)."""
    return np.sum(Y[:, :-1] / sig(X[:, :-1]) * dW, axis=1) / T


def bel_delta(
    payoff: Payoff, b: Callable, db: Callable, sig: Callable, dsig: Callable,
    x0: float, T: float, r: float, grid: TimeGrid, n_paths: int, seed: int | None = None,
) -> MCEstimate:
    """∂_{x0} e^{-rT} E[Φ(X_T)] = e^{-rT} E[Φ(X_T) (1/T)∫ σ^{-1}(X_t) Y_t dW_t]  (Teorema 12.3 del PDF)."""
    from .brownian import brownian_increments

    dW = brownian_increments(grid, n_paths, rng(seed))
    X, Y = diffusion_with_tangent(b, db, sig, dsig, x0, grid, dW)
    return mc(np.exp(-r * T) * payoff(X[:, -1]) * bel_weight(X, Y, sig, dW, T))


def euler_fd_delta(
    payoff: Payoff, b: Callable, sig: Callable, x0: float, T: float, r: float,
    grid: TimeGrid, n_paths: int, seed: int | None = None, h: float = 1e-2,
) -> MCEstimate:
    """Diferencias finitas centradas con números aleatorios comunes sobre el esquema de Euler."""
    from .brownian import brownian_increments

    dW = brownian_increments(grid, n_paths, rng(seed))
    one = lambda v: v * 0.0 + 1.0  # derivadas irrelevantes para X
    up, _ = diffusion_with_tangent(b, one, sig, one, x0 * (1 + h), grid, dW)
    dn, _ = diffusion_with_tangent(b, one, sig, one, x0 * (1 - h), grid, dW)
    return mc(np.exp(-r * T) * (payoff(up[:, -1]) - payoff(dn[:, -1])) / (2 * h * x0))
