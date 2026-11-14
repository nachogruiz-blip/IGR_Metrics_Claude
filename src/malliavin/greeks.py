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
