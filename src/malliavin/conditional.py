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

from dataclasses import dataclass

import numpy as np

from . import bs
from .brownian import TimeGrid, brownian_paths, gbm_from_brownian, rng


def bs_conditional_weight(Ss: np.ndarray, Ws: np.ndarray, Wt: np.ndarray, s: float, t: float, sigma: float) -> np.ndarray:
    """δ(u) del Ejemplo 14.2 del PDF."""
    return ((t * Ws - s * Wt) / (s * (t - s)) + sigma) / (sigma * Ss)


def _laplace_cdf(z: np.ndarray, eta: float) -> np.ndarray:
    return np.where(z < 0, 0.5 * np.exp(eta * np.minimum(z, 0)), 1 - 0.5 * np.exp(-eta * np.maximum(z, 0)))


def optimal_eta(phi: np.ndarray, H: np.ndarray) -> float:
    """η² = E[Φ² δ(u)²] / E[Φ²]."""
    return float(np.sqrt(np.mean(phi**2 * H**2) / max(np.mean(phi**2), 1e-300)))


def _dirac_terms(phi, F, H, z, eta):
    """Sumandos de la estimación de E[Φ(G) δ_x(F)] (sin promediar), z = F − x."""
    if eta is None:
        return phi * (z > 0) * H
    psi = 0.5 * eta * np.exp(-eta * np.abs(z))
    return phi * psi + phi * ((z > 0) - _laplace_cdf(z, eta)) * H


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
        out[i : i + chunk] = _dirac_terms(phi, F, H, z, eta).mean(axis=1)
    return out


def conditional_expectation(
    phi: np.ndarray, F: np.ndarray, H: np.ndarray, x: np.ndarray, localize: bool = True,
    max_rel_stderr: float = 0.25, min_samples: int = 100, return_stderr: bool = False,
    chunk: int = 512,
):
    """E[Φ(G) | F = x] como cociente de esperanzas no condicionales (Teorema 14.1 del PDF).

    El error estándar del cociente R = ā / b̄ se estima por el método delta,
    se(R) = std(a_i − R b_i) / (√N |b̄|). Donde el denominador (≈ densidad p_F(x)) no es
    positivo o el error relativo supera ``max_rel_stderr`` (típico en las colas de F, o con
    pocas muestras sin localizar) se devuelve ``NaN`` en lugar de un valor poco fiable. Sin
    localizar, el estimador solo usa las muestras con F > x, así que además se exigen al menos
    ``min_samples`` muestras a cada lado de x (con pocas, el propio error estándar no es fiable).
    """
    x = np.asarray(x, dtype=float)
    num_eta = optimal_eta(phi, H) if localize else None
    den_eta = optimal_eta(np.ones_like(H), H) if localize else None
    one = np.ones_like(H)
    est = np.full(x.size, np.nan)
    se = np.full(x.size, np.nan)
    n = F.size
    for i in range(0, x.size, chunk):
        z = F[None, :] - x[i : i + chunk, None]
        a = _dirac_terms(phi, F, H, z, num_eta)
        b = _dirac_terms(one, F, H, z, den_eta)
        am, bm = a.mean(axis=1), b.mean(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = am / bm
            s = (a - ratio[:, None] * b).std(axis=1) / (np.sqrt(n) * np.abs(bm))
        est[i : i + chunk], se[i : i + chunk] = ratio, s
    bad = ~(np.isfinite(est) & np.isfinite(se)) | (se > max_rel_stderr * np.abs(est))
    if not localize:
        above = n - np.searchsorted(np.sort(F), x, side="right")
        bad |= np.minimum(above, n - above) < min_samples
    est[bad], se[bad] = np.nan, np.nan
    return (est, se) if return_stderr else est


@dataclass(frozen=True)
class BermudanEstimate:
    """Precio de una bermuda por Monte Carlo con dos estimadores.

    high: valor por programación dinámica sobre las propias trayectorias de entrenamiento
          (máximo de estimaciones ruidosas: sesgado al alza en la práctica).
    low:  valor de la regla de ejercicio aprendida, aplicada a trayectorias nuevas e
          independientes (cota inferior insesgada del precio, salvo error MC).
    """

    high: float
    low: float
    low_stderr: float


def bermudan_put_malliavin(
    S0: float, K: float, T: float, r: float, sigma: float, n_exercise: int,
    n_paths: int, seed: int | None = None, n_paths_eval: int | None = None,
) -> BermudanEstimate:
    """Put bermuda con esperanzas condicionales de Malliavin (PDF §14.2).

    Programación dinámica: V_{t_n} = Φ(S_{t_n}),
    V_{t_k} = max{Φ(S_{t_k}), e^{−rΔt} E[V_{t_{k+1}} | S_{t_k}]}, con la esperanza condicional
    estimada por el Teorema 14.1 sobre ``n_paths`` trayectorias de entrenamiento. La misma
    estimación define una regla de ejercicio que se evalúa sobre ``n_paths_eval`` trayectorias
    independientes (por defecto 4·n_paths) para obtener la cota inferior, con la put europea
    como variable de control (ver ``BermudanEstimate``).
    """
    gen = rng(seed)
    grid = TimeGrid(T, n_exercise)
    payoff = lambda s: np.maximum(K - s, 0.0)
    disc = np.exp(-r * grid.dt)

    # --- Entrenamiento: estimador por valores (high) y datos de la regla de ejercicio
    W = brownian_paths(grid, n_paths, gen)
    S = gbm_from_brownian(W, grid, S0, r, sigma)
    V = payoff(S[:, -1])
    training = {}
    for k in range(n_exercise - 1, 0, -1):
        H = bs_conditional_weight(S[:, k], W[:, k], W[:, k + 1], grid.t[k], grid.t[k + 1], sigma)
        training[k] = (V.copy(), S[:, k].copy(), H)
        cont = disc * conditional_expectation(V, S[:, k], H, S[:, k])
        cont = np.where(np.isnan(cont), 0.0, np.maximum(cont, 0.0))
        V = np.maximum(payoff(S[:, k]), cont)
    high = float(max(disc * V.mean(), payoff(np.array([S0]))[0]))

    # --- Evaluación: regla de ejercicio aplicada a trayectorias nuevas (low)
    m = n_paths_eval or 4 * n_paths
    Wb = brownian_paths(grid, m, gen)
    Sb = gbm_from_brownian(Wb, grid, S0, r, sigma)
    cash = np.zeros(m)
    alive = np.ones(m, dtype=bool)
    for k in range(1, n_exercise):
        Vk1, Sk, Hk = training[k]
        idx = np.flatnonzero(alive & (payoff(Sb[:, k]) > 0))
        if idx.size:
            cont = disc * conditional_expectation(Vk1, Sk, Hk, Sb[idx, k])
            ex = idx[~np.isnan(cont) & (payoff(Sb[idx, k]) >= cont)]
            cash[ex] = np.exp(-r * grid.t[k]) * payoff(Sb[ex, k])
            alive[ex] = False
    cash[alive] = np.exp(-r * T) * payoff(Sb[alive, -1])
    # Variable de control: la put europea, de precio conocido y muy correlada con el flujo.
    euro = np.exp(-r * T) * payoff(Sb[:, -1])
    euro_price = bs.call_price(S0, K, T, r, sigma) - S0 + K * np.exp(-r * T)
    beta = np.cov(cash, euro)[0, 1] / euro.var(ddof=1)
    adj = cash - beta * (euro - euro_price)
    low = float(max(adj.mean(), payoff(np.array([S0]))[0]))
    return BermudanEstimate(high=high, low=low, low_stderr=float(adj.std(ddof=1) / np.sqrt(m)))


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
