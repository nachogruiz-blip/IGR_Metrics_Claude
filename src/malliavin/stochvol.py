r"""Volatilidad estocástica: descomposición de Alòs y skew en tiempo corto (PDF cap. 14, §14.3–14.4).

Modelo para el log-precio bajo la medida de riesgo neutro (PDF §14.3):

    dX_t = (r − σ_t²/2) dt + σ_t (ρ dW_t + √(1−ρ²) dB_t),

con σ adaptada a la filtración de W. Se implementan dos modelos de volatilidad:

* **Rough Bergomi** (PDF Ejemplo 14.7, Bayer–Friz–Gatheral 2016):
  σ_t² = ξ₀ exp(η Ŵ^H_t − η² t^{2H}/2),  Ŵ^H_t = ∫₀ᵗ √(2H) (t−s)^{H−1/2} dW_s,
  simulado de forma **exacta en la malla** por Cholesky de la ley conjunta de (W, Ŵ^H).
  Su derivada de Malliavin es explícita: D^W_s σ_r² = η σ_r² √(2H) (r−s)^{H−1/2}, s < r.
* **Heston**: dv = κ(θ−v) dt + ν √v dW, σ = √v (Euler con truncamiento total).

Precios por el estimador condicional (Romano–Touzi): dado F^W_T, X_T es gaussiana, y

    E[(S_T − K)⁺ | F^W_T] = BS(S₀ e^{ρ∫σdW − ρ²∫σ²/2}, K, T, r, √((1−ρ²)∫σ²/T)),

lo que elimina el ruido de B y deja una estimación muy suave en K.

Fórmula de Alòs (PDF Teorema 14.5):

    V₀ = E[BS(0, X₀, v₀)] + (ρ/2) E[∫₀ᵀ e^{−rs} H(s, X_s, v_s) Λ_s ds],
    v_s² = (1/(T−s)) ∫_sᵀ σ_r² dr,  H = (∂_x³ − ∂_x²)BS,  Λ_s = σ_s ∫_sᵀ D^W_s σ_r² dr.

Skew en el dinero en tiempo corto (PDF Teorema 14.6):

* Heston: ∂_k I → ρν / (4√v₀)  (caso (a): D_sσ_r → ν/2).
* Rough Bergomi: ∂_k I ≈ ρ η √(2H) / (2 (H+½)(H+3/2)) · T^{H−1/2}  (caso (b)).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from scipy.optimize import brentq
from scipy.special import hyp2f1
from scipy.stats import norm

from . import bs
from .brownian import TimeGrid, rng


# --- Rough Bergomi -----------------------------------------------------------

@lru_cache(maxsize=16)
def _rbergomi_cholesky(T: float, n_steps: int, H: float) -> np.ndarray:
    """Factor de Cholesky de la covarianza de (W_{t_1..t_n}, Ŵ^H_{t_1..t_n})."""
    t = np.linspace(0.0, T, n_steps + 1)[1:]
    a = H - 0.5
    s, u = np.minimum.outer(t, t), np.maximum.outer(t, t)
    cov_ww = s
    # Cov(W_s, Ŵ_t) = ∫_0^{s∧t} K(t, v) dv
    m = np.minimum.outer(t, t)
    cov_wh = np.sqrt(2 * H) / (H + 0.5) * (t[None, :] ** (H + 0.5) - (t[None, :] - m) ** (H + 0.5))
    # Cov(Ŵ_s, Ŵ_t) = 2H ∫_0^s (s−v)^a (t−v)^a dv, s ≤ t (forma cerrada con 2F1)
    with np.errstate(divide="ignore", invalid="ignore"):
        d = u - s
        off = d ** a * s ** (a + 1) / (a + 1) * hyp2f1(-a, a + 1, a + 2, -s / d)
    cov_hh = 2 * H * np.where(d > 0, off, s ** (2 * H) / (2 * H))
    cov = np.block([[cov_ww, cov_wh], [cov_wh.T, cov_hh]])
    cov += 1e-12 * np.eye(2 * n_steps)
    return np.linalg.cholesky(cov)


@dataclass(frozen=True)
class VolPaths:
    """Trayectorias de un modelo de volatilidad estocástica en una malla.

    W: browniano de la volatilidad, (n_paths, n_steps+1); var: σ², (n_paths, n_steps+1);
    dW = incrementos de W. ``H``/``eta`` solo para rough Bergomi (para D^W σ²).
    """

    grid: TimeGrid
    W: np.ndarray
    var: np.ndarray
    H: float | None = None
    eta: float | None = None

    @property
    def dW(self) -> np.ndarray:
        return np.diff(self.W, axis=1)


def rough_bergomi_paths(
    T: float, n_steps: int, n_paths: int, H: float, eta: float, xi0: float,
    gen: np.random.Generator | None = None,
) -> VolPaths:
    """Rough Bergomi simulado exactamente en la malla (Cholesky de la ley conjunta de W y Ŵ^H)."""
    gen = gen or rng()
    grid = TimeGrid(T, n_steps)
    L = _rbergomi_cholesky(float(T), int(n_steps), float(H))
    Z = gen.standard_normal((n_paths, 2 * n_steps)) @ L.T
    W = np.concatenate([np.zeros((n_paths, 1)), Z[:, :n_steps]], axis=1)
    Wh = np.concatenate([np.zeros((n_paths, 1)), Z[:, n_steps:]], axis=1)
    var = xi0 * np.exp(eta * Wh - 0.5 * eta**2 * grid.t ** (2 * H))
    return VolPaths(grid, W, var, H, eta)


def heston_paths(
    T: float, n_steps: int, n_paths: int, v0: float, kappa: float, theta: float, nu: float,
    gen: np.random.Generator | None = None,
) -> VolPaths:
    """Heston, varianza por Euler con truncamiento total (v⁺ en los coeficientes)."""
    gen = gen or rng()
    grid = TimeGrid(T, n_steps)
    dW = gen.standard_normal((n_paths, n_steps)) * np.sqrt(grid.dt)
    v = np.empty((n_paths, n_steps + 1))
    v[:, 0] = v0
    for k in range(n_steps):  # bucle temporal, vectorizado en trayectorias
        vp = np.maximum(v[:, k], 0.0)
        v[:, k + 1] = v[:, k] + kappa * (theta - vp) * grid.dt + nu * np.sqrt(vp) * dW[:, k]
    W = np.concatenate([np.zeros((n_paths, 1)), np.cumsum(dW, axis=1)], axis=1)
    return VolPaths(grid, W, np.maximum(v, 0.0))


# --- Precios y volatilidad implícita ---------------------------------------

def _mixing_inputs(p: VolPaths, rho: float):
    sig = np.sqrt(p.var[:, :-1])
    int_var = p.var[:, :-1].sum(axis=1) * p.grid.dt
    int_sdw = (sig * p.dW).sum(axis=1)
    return int_var, int_sdw


def call_prices(p: VolPaths, S0: float, K: np.ndarray, r: float, rho: float) -> tuple[np.ndarray, np.ndarray]:
    """Precio de calls por el estimador condicional; devuelve (precio, error estándar) por strike."""
    T = p.grid.T
    int_var, int_sdw = _mixing_inputs(p, rho)
    S_eff = S0 * np.exp(rho * int_sdw - 0.5 * rho**2 * int_var)
    vol = np.sqrt(np.maximum((1 - rho**2) * int_var, 1e-300) / T)
    K = np.atleast_1d(np.asarray(K, dtype=float))
    samples = bs.call_price(S_eff[:, None], K[None, :], T, r, vol[:, None])
    return samples.mean(axis=0), samples.std(axis=0, ddof=1) / np.sqrt(samples.shape[0])


def implied_vol(price: float, S0: float, K: float, T: float, r: float) -> float:
    """Volatilidad implícita de Black–Scholes de una call (brentq)."""
    intrinsic = max(S0 - K * np.exp(-r * T), 0.0)
    if not intrinsic < price < S0:
        return np.nan
    return brentq(lambda s: bs.call_price(S0, K, T, r, s) - price, 1e-6, 5.0, xtol=1e-12)


def atm_skew(p: VolPaths, S0: float, r: float, rho: float, dk: float | None = None) -> float:
    """∂_k I en k = log(K/F) = 0 por diferencias centradas, con los mismos números aleatorios."""
    T = p.grid.T
    F = S0 * np.exp(r * T)
    if dk is None:
        dk = 0.05 * np.sqrt(np.mean(p.var[:, 0]) * T)
    K = F * np.exp(np.array([-dk, dk]))
    prices, _ = call_prices(p, S0, K, r, rho)
    iv = [implied_vol(c, S0, k, T, r) for c, k in zip(prices, K)]
    return (iv[1] - iv[0]) / (2 * dk)


def heston_skew_limit(v0: float, nu: float, rho: float) -> float:
    """Límite T → 0 del skew ATM en Heston (PDF Teorema 14.6(a)): ρν / (4√v₀)."""
    return rho * nu / (4 * np.sqrt(v0))


def rbergomi_skew_asymptotic(T, H: float, eta: float, rho: float):
    """Skew ATM a primer orden en rough Bergomi (PDF Teorema 14.6(b) y Ejemplo 14.7)."""
    return rho * eta * np.sqrt(2 * H) / (2 * (H + 0.5) * (H + 1.5)) * np.asarray(T) ** (H - 0.5)


# --- Fórmula de Alòs ----------------------------------------------------------

def bs_x_derivs_H(x, tau, v, K: float, r: float):
    """H(s, x, v) = (∂_x³ − ∂_x²) BS(s, x, v) con x = log S y τ = T − s.

    Con d₁ = (x − log K + (r + v²/2)τ)/(v√τ):  H = e^x φ(d₁)/(v√τ) · (1 − d₁/(v√τ)).
    """
    sv = v * np.sqrt(tau)
    d1 = (x - np.log(K) + (r + 0.5 * v**2) * tau) / sv
    return np.exp(x) * norm.pdf(d1) / sv * (1.0 - d1 / sv)


@dataclass(frozen=True)
class AlosDecomposition:
    """Precio de una call y su descomposición de Alòs, cada término con su error estándar.

    price: precio Monte Carlo (estimador condicional); hull_white: E[BS(0, X₀, v₀)];
    correction: (ρ/2) E[∫ e^{−rs} H Λ ds]. Si la fórmula es exacta, price ≈ hull_white + correction.
    """

    price: float
    price_se: float
    hull_white: float
    hull_white_se: float
    correction: float
    correction_se: float

    @property
    def alos(self) -> float:
        return self.hull_white + self.correction


def alos_decomposition_rbergomi(
    p: VolPaths, S0: float, K: float, r: float, rho: float, gen: np.random.Generator | None = None,
) -> AlosDecomposition:
    """Evalúa los dos lados de la fórmula de Alòs (PDF T. 14.5) en rough Bergomi.

    Necesita la trayectoria completa de X (se simula B independiente) porque H se evalúa en X_s,
    y la volatilidad futura v_s y Λ_s, que anticipan el futuro de σ: se calculan sobre la propia
    trayectoria. Λ_s usa D^W_s σ_r² = η √(2H) σ_r² (r−s)^{H−1/2}, integrando el núcleo
    exactamente en cada celda de la malla.
    """
    if p.H is None or p.eta is None:
        raise ValueError("Se necesitan trayectorias de rough_bergomi_paths")
    gen = gen or rng()
    g = p.grid
    n, dt, T = g.n_steps, g.dt, g.T
    t = g.t
    var = p.var[:, :-1]  # σ² en los nodos izquierdos t_0..t_{n−1}
    sig = np.sqrt(var)

    # Precio por el estimador condicional
    price, price_se = call_prices(p, S0, np.array([K]), r, rho)

    # Trayectoria de X (con B independiente)
    dB = gen.standard_normal(p.dW.shape) * np.sqrt(dt)
    dX = (r - 0.5 * var) * dt + sig * (rho * p.dW + np.sqrt(1 - rho**2) * dB)
    X = np.log(S0) + np.concatenate([np.zeros((dX.shape[0], 1)), np.cumsum(dX, axis=1)], axis=1)

    # v_s² = (1/(T−s)) ∫_s^T σ² en s = t_i (i = 0..n−1)
    tail = np.cumsum(var[:, ::-1], axis=1)[:, ::-1] * dt
    tau = T - t[:-1]
    v = np.sqrt(tail / tau)

    # Término de Hull–White
    hw = bs.call_price(S0, K, T, r, v[:, 0])

    # Λ_{t_i} = σ_{t_i} η √(2H) Σ_{j≥i} σ²_{t_j} ∫_{t_j}^{t_{j+1}} (r − t_i)^{H−1/2} dr
    a = p.H - 0.5
    i_idx, j_idx = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    lo = np.maximum(t[j_idx] - t[i_idx], 0.0)
    hi = np.maximum(t[j_idx + 1] - t[i_idx], 0.0)
    M = np.where(j_idx >= i_idx, (hi ** (a + 1) - lo ** (a + 1)) / (a + 1), 0.0)
    Lam = sig * p.eta * np.sqrt(2 * p.H) * (var @ M.T)

    Hs = bs_x_derivs_H(X[:, :-1], tau, v, K, r)
    corr = 0.5 * rho * (np.exp(-r * t[:-1]) * Hs * Lam).sum(axis=1) * dt

    m = hw.size
    return AlosDecomposition(
        price=float(price[0]), price_se=float(price_se[0]),
        hull_white=float(hw.mean()), hull_white_se=float(hw.std(ddof=1) / np.sqrt(m)),
        correction=float(corr.mean()), correction_se=float(corr.std(ddof=1) / np.sqrt(m)),
    )
