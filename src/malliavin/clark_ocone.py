r"""Fórmula de Clark–Ocone y cobertura.

Para F ∈ D^{1,2}, F_T-medible:

    F = E[F] + ∫_0^T E[D_t F | F_t] dW_t.

En finanzas (medida neutral al riesgo, pago descontado F = e^{-rT}Φ(S_T)),
el integrando φ_t = E[D_t F | F_t] determina la cartera replicante:
el número de acciones es  Δ_t = φ_t / (σ e^{-rt} S_t).
"""

from __future__ import annotations

from math import pi, sqrt
from typing import Callable

import numpy as np
from numpy.polynomial import hermite_e as He

from . import bs
from .brownian import TimeGrid


def integrand_terminal_functional(
    f_prime: Callable[[np.ndarray], np.ndarray], W: np.ndarray, grid: TimeGrid, n_quad: int = 64
) -> np.ndarray:
    """Para F = f(W_T): E[D_t F | F_t] = E[f'(W_t + √(T-t) Z)], Z ~ N(0,1).

    Se calcula por cuadratura de Gauss–Hermite. Forma de salida (n_paths, n_steps).
    """
    x, w = He.hermegauss(n_quad)
    w = w / sqrt(2 * pi)
    Wt = W[:, :-1, None]
    tau = (grid.T - grid.t[:-1])[None, :, None]
    return np.sum(w * f_prime(Wt + np.sqrt(tau) * x), axis=-1)


def integrand_cubic(W: np.ndarray, grid: TimeGrid) -> np.ndarray:
    """F = W_T³: E[D_t F | F_t] = 3(W_t² + T - t) (fórmula cerrada)."""
    return 3.0 * (W[:, :-1] ** 2 + grid.T - grid.t[:-1])


def integrand_call(S: np.ndarray, grid: TimeGrid, K: float, r: float, sigma: float) -> np.ndarray:
    """F = e^{-rT}(S_T - K)^+: E[D_t F | F_t] = σ e^{-rt} S_t N(d_1(t))."""
    t = grid.t[:-1]
    St = S[:, :-1]
    return sigma * np.exp(-r * t) * St * bs.call_delta_t(St, K, grid.T - t, r, sigma)


def reconstruct(EF: float, integrand: np.ndarray, dW: np.ndarray) -> np.ndarray:
    """Trayectoria M_t = E[F] + ∫_0^t φ_s dW_s, forma (n_paths, n_steps+1)."""
    M = np.empty((dW.shape[0], dW.shape[1] + 1))
    M[:, 0] = EF
    M[:, 1:] = EF + np.cumsum(integrand * dW, axis=1)
    return M
