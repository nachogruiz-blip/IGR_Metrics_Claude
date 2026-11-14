"""Simulación de movimiento browniano y de GBM.

Convención: una malla uniforme t_0=0 < t_1 < ... < t_n = T con dt = T/n.
Las trayectorias se devuelven con forma (n_paths, n_steps + 1) e incluyen t=0.
Los incrementos tienen forma (n_paths, n_steps).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class TimeGrid:
    """Malla temporal uniforme en [0, T]."""

    T: float
    n_steps: int

    @property
    def dt(self) -> float:
        return self.T / self.n_steps

    @property
    def t(self) -> np.ndarray:
        return np.linspace(0.0, self.T, self.n_steps + 1)


def rng(seed: int | None = None) -> np.random.Generator:
    """Generador reproducible (PCG64)."""
    return np.random.default_rng(seed)


def brownian_increments(
    grid: TimeGrid, n_paths: int, gen: np.random.Generator | None = None
) -> np.ndarray:
    """Incrementos ΔW_k ~ N(0, dt), forma (n_paths, n_steps)."""
    gen = gen or rng()
    return gen.standard_normal((n_paths, grid.n_steps)) * np.sqrt(grid.dt)


def paths_from_increments(dW: np.ndarray) -> np.ndarray:
    """W_{t_k} = sum_{j<k} ΔW_j, con W_0 = 0."""
    W = np.zeros((dW.shape[0], dW.shape[1] + 1))
    np.cumsum(dW, axis=1, out=W[:, 1:])
    return W


def brownian_paths(
    grid: TimeGrid, n_paths: int, gen: np.random.Generator | None = None
) -> np.ndarray:
    """Trayectorias brownianas, forma (n_paths, n_steps + 1)."""
    return paths_from_increments(brownian_increments(grid, n_paths, gen))


def gbm_from_brownian(
    W: np.ndarray, grid: TimeGrid, S0: float, r: float, sigma: float
) -> np.ndarray:
    """Solución exacta S_t = S0 exp((r - σ²/2) t + σ W_t) bajo la medida neutral al riesgo."""
    return S0 * np.exp((r - 0.5 * sigma**2) * grid.t + sigma * W)


def terminal_gbm(
    n_paths: int,
    T: float,
    S0: float,
    r: float,
    sigma: float,
    gen: np.random.Generator | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Simula sólo (W_T, S_T): suficiente para pagos europeos. Devuelve (W_T, S_T)."""
    gen = gen or rng()
    WT = gen.standard_normal(n_paths) * np.sqrt(T)
    ST = S0 * np.exp((r - 0.5 * sigma**2) * T + sigma * WT)
    return WT, ST
