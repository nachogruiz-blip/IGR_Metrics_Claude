r"""Derivada de Malliavin.

Dos enfoques:

1. Analítico: fórmulas cerradas para funcionales típicos (ver `analytic_*`).
2. Discreto: si F depende de los incrementos ΔW_0..ΔW_{n-1} de una malla,
   F = φ(ΔW_0, ..., ΔW_{n-1}), entonces la derivada de Malliavin es la
   función escalonada

       D_t F = ∂φ/∂(ΔW_k)   para t ∈ [t_k, t_{k+1}).

   `discrete_malliavin_derivative` aproxima ese gradiente por diferencias
   centradas. Es la idea de "derivada de Fréchet en dirección de Cameron–Martin":
   ⟨DF, h⟩ = d/dε F(W + ε∫_0^· h) |_{ε=0}.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from .brownian import TimeGrid, paths_from_increments

Functional = Callable[[np.ndarray], np.ndarray]
"""Un funcional recibe trayectorias W (n_paths, n_steps+1) y devuelve (n_paths,)."""


def discrete_malliavin_derivative(
    F: Functional, dW: np.ndarray, eps: float = 1e-5
) -> np.ndarray:
    """D_{t_k} F aproximada, forma (n_paths, n_steps).

    Perturba cada incremento ΔW_k (es decir, desplaza W en ±eps·1_{[t_{k+1},T]})
    y aplica diferencias centradas. Coste: 2·n_steps evaluaciones de F.
    """
    n_paths, n_steps = dW.shape
    D = np.empty((n_paths, n_steps))
    for k in range(n_steps):
        up = dW.copy()
        dn = dW.copy()
        up[:, k] += eps
        dn[:, k] -= eps
        D[:, k] = (F(paths_from_increments(up)) - F(paths_from_increments(dn))) / (2 * eps)
    return D


def directional_derivative(
    F: Functional, W: np.ndarray, grid: TimeGrid, h: Callable[[np.ndarray], np.ndarray], eps: float = 1e-5
) -> np.ndarray:
    """⟨DF, h⟩_{L²[0,T]} ≈ [F(W + ε H) - F(W - ε H)] / (2ε),  H_t = ∫_0^t h(s) ds."""
    t = grid.t
    hs = h(t[:-1])
    H = np.concatenate([[0.0], np.cumsum(hs * grid.dt)])
    return (F(W + eps * H) - F(W - eps * H)) / (2 * eps)


# --- Fórmulas analíticas -------------------------------------------------

def analytic_terminal_power(W: np.ndarray, grid: TimeGrid, p: int) -> np.ndarray:
    """F = W_T^p  =>  D_t F = p W_T^{p-1} 1_{[0,T]}(t)."""
    WT = W[:, -1:]
    return np.broadcast_to(p * WT ** (p - 1), (W.shape[0], grid.n_steps)).copy()


def analytic_time_integral(W: np.ndarray, grid: TimeGrid) -> np.ndarray:
    """F = ∫_0^T W_s ds  =>  D_t F = T - t (determinista)."""
    return np.broadcast_to(grid.T - grid.t[:-1], (W.shape[0], grid.n_steps)).copy()


def analytic_running_max(W: np.ndarray, grid: TimeGrid) -> np.ndarray:
    """F = max_{s≤T} W_s  =>  D_t F = 1_{[0, τ*]}(t), τ* = argmax."""
    tau_idx = np.argmax(W, axis=1)
    k = np.arange(grid.n_steps)
    return (k[None, :] < tau_idx[:, None]).astype(float)


def analytic_gbm_terminal(S: np.ndarray, sigma: float, grid: TimeGrid) -> np.ndarray:
    """F = S_T (GBM)  =>  D_t S_T = σ S_T 1_{[0,T]}(t)."""
    return np.broadcast_to(sigma * S[:, -1:], (S.shape[0], grid.n_steps)).copy()
