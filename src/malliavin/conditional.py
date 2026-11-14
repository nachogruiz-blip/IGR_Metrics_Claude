r"""Esperanzas condicionales por integración por partes y opciones bermudas (PDF cap. 14).

Teorema 14.1 del PDF: si ⟨DF,u⟩ = 1 y ⟨DG,u⟩ = 0,

    E[Φ(G) | F = x] = E[Φ(G) 1_{F>x} δ(u)] / E[1_{F>x} δ(u)].

Ejemplo 14.2 (Black–Scholes, 0 < s < t, F = S_s, G = S_t):

    δ(u) = (1/(σ S_s)) [ (t W_s − s W_t) / (s(t−s)) + σ ].

Localización (Bouchard–Ekeland–Touzi): para ψ(z) = (η/2) e^{−η|z|} con primitiva Ψ,

    E[Φ(G) δ_x(F)] = E[Φ(G) ψ(F−x)] + E[Φ(G) (1_{F>x} − Ψ(F−x)) δ(u)],

con η² = E[Φ(G)² δ(u)²] / E[Φ(G)²] (minimiza la varianza integrada).
"""

from __future__ import annotations

import numpy as np

from .brownian import TimeGrid, brownian_paths, gbm_from_brownian, rng


def bs_conditional_weight(Ss: np.ndarray, Ws: np.ndarray, Wt: np.ndarray, s: float, t: float, sigma: float) -> np.ndarray:
    """δ(u) del Ejemplo 14.2 del PDF."""
    return ((t * Ws - s * Wt) / (s * (t - s)) + sigma) / (sigma * Ss)


def _laplace_cdf(z: np.ndarray, eta: float) -> np.ndarray:
    return np.where(z < 0, 0.5 * np.exp(eta * np.minimum(z, 0)), 1 - 0.5 * np.exp(-eta * np.maximum(z, 0)))


def optimal_eta(phi: np.ndarray, H: np.ndarray) -> float:
    """η² = E[Φ² δ(u)²] / E[Φ²]."""
    return float(np.sqrt(np.mean(phi**2 * H**2) / max(np.mean(phi**2), 1e-300)))


def dirac_expectation(
    phi: np.ndarray, F: np.ndarray, H: np.ndarray, x: np.ndarray,
    eta: float | None = None, chunk: int = 512,
) -> np.ndarray:
    """Estima E[Φ(G) δ_x(F)] en cada punto de x (localizado si eta no es None).

    Coste O(len(x)·N), por bloques para acotar memoria.
    """
    x = np.asarray(x, dtype=float)
    out = np.empty(x.size)
    for i in range(0, x.size, chunk):
        z = F[None, :] - x[i : i + chunk, None]
        if eta is None:
            out[i : i + chunk] = np.mean(phi * (z > 0) * H, axis=1)
        else:
            psi = 0.5 * eta * np.exp(-eta * np.abs(z))
            out[i : i + chunk] = np.mean(phi * psi + phi * ((z > 0) - _laplace_cdf(z, eta)) * H, axis=1)
    return out


def conditional_expectation(
    phi: np.ndarray, F: np.ndarray, H: np.ndarray, x: np.ndarray, localize: bool = True
) -> np.ndarray:
    """E[Φ(G) | F = x] como cociente de esperanzas no condicionales (Teorema 14.1)."""
    num_eta = optimal_eta(phi, H) if localize else None
    den_eta = optimal_eta(np.ones_like(H), H) if localize else None
    num = dirac_expectation(phi, F, H, x, num_eta)
    den = dirac_expectation(np.ones_like(H), F, H, x, den_eta)
    return num / den


def bermudan_put_malliavin(
    S0: float, K: float, T: float, r: float, sigma: float, n_exercise: int,
    n_paths: int, seed: int | None = None,
) -> float:
    """Put bermuda por programación dinámica con esperanzas condicionales de Malliavin (PDF §14.2).

    V_{t_n} = Φ(S_{t_n}),  V_{t_k} = max{Φ(S_{t_k}), e^{−rΔt} E[V_{t_{k+1}} | S_{t_k}]}.
    En t_0 = 0 la esperanza condicional es una media simple.
    """
    grid = TimeGrid(T, n_exercise)
    W = brownian_paths(grid, n_paths, rng(seed))
    S = gbm_from_brownian(W, grid, S0, r, sigma)
    payoff = lambda s: np.maximum(K - s, 0.0)
    disc = np.exp(-r * grid.dt)
    V = payoff(S[:, -1])
    for k in range(n_exercise - 1, 0, -1):
        s_, t_ = grid.t[k], grid.t[k + 1]
        H = bs_conditional_weight(S[:, k], W[:, k], W[:, k + 1], s_, t_, sigma)
        cont = disc * conditional_expectation(V, S[:, k], H, S[:, k])
        V = np.maximum(payoff(S[:, k]), np.maximum(cont, 0.0))
    return float(max(disc * V.mean(), payoff(np.array([S0]))[0]))


def bermudan_put_binomial(
    S0: float, K: float, T: float, r: float, sigma: float, n_exercise: int, steps_per_date: int = 200
) -> float:
    """Referencia: árbol CRR con ejercicio sólo en las fechas t_k = kT/n_exercise."""
    n = n_exercise * steps_per_date
    dt = T / n
    u = np.exp(sigma * np.sqrt(dt))
    d = 1 / u
    p = (np.exp(r * dt) - d) / (u - d)
    disc = np.exp(-r * dt)
    j = np.arange(n + 1)
    V = np.maximum(K - S0 * u**j * d ** (n - j), 0.0)
    for i in range(n - 1, -1, -1):
        V = disc * (p * V[1:] + (1 - p) * V[:-1])
        if i % steps_per_date == 0 and i > 0:
            j = np.arange(i + 1)
            V = np.maximum(V, K - S0 * u**j * d ** (i - j))
    return float(V[0])
