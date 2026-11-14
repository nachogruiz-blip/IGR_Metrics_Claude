r"""Estimación de densidades por integración por partes (Nualart, cap. 2).

Si F ∈ D^{1,2} y u = DF / ||DF||² ∈ dom δ, entonces F tiene densidad

    p_F(x) = E[ 1_{F > x} δ(DF / ||DF||²) ].

Para F = S_T (GBM): DF = σ S_T 1_{[0,T]},  ||DF||² = σ² S_T² T, y

    δ(DF/||DF||²) = (1/S_T) (W_T/(σT) + 1).

Ventaja: sin núcleo ni ancho de banda (estimador insesgado punto a punto).
"""

from __future__ import annotations

import numpy as np


def malliavin_density_from_weights(F: np.ndarray, H: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """p(x) ≈ mean(1_{F>x} H) evaluada en todos los x en O((N+M) log N).

    Devuelve (densidad, error estándar).
    """
    order = np.argsort(F)
    Fs, Hs = F[order], H[order]
    tail = np.concatenate([np.cumsum(Hs[::-1])[::-1], [0.0]])
    tail2 = np.concatenate([np.cumsum((Hs**2)[::-1])[::-1], [0.0]])
    idx = np.searchsorted(Fs, x, side="right")
    N = F.size
    m = tail[idx] / N
    var = tail2[idx] / N - m**2
    return m, np.sqrt(np.maximum(var, 0.0) / N)


def gbm_terminal_density(x: np.ndarray, WT: np.ndarray, ST: np.ndarray, sigma: float, T: float):
    """Densidad de S_T vía peso de Malliavin."""
    H = (WT / (sigma * T) + 1.0) / ST
    return malliavin_density_from_weights(ST, H, np.asarray(x, dtype=float))


def gaussian_kde(samples: np.ndarray, x: np.ndarray, bandwidth: float | None = None) -> np.ndarray:
    """KDE gaussiano simple (regla de Silverman) para comparar."""
    n = samples.size
    bw = bandwidth or 1.06 * samples.std() * n ** (-1 / 5)
    z = (x[:, None] - samples[None, :]) / bw
    return np.exp(-0.5 * z**2).sum(axis=1) / (n * bw * np.sqrt(2 * np.pi))
