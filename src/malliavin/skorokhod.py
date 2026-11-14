r"""Divergencia δ (integral de Skorokhod) e integración por partes.

Dualidad (definición de δ como adjunto de D):

    E[⟨DF, u⟩_{L²[0,T]}] = E[F δ(u)].

Reglas útiles implementadas aquí:

* u determinista h:          δ(h) = ∫_0^T h(t) dW_t  (integral de Wiener).
* u adaptado:                δ(u) = ∫_0^T u_t dW_t   (Itô).
* u = G·h, G ∈ D^{1,2}:      δ(G h) = G ∫ h dW - ⟨DG, h⟩.

Ejemplo clásico no adaptado: δ(W_T 1_{[0,T]}) = W_T² - T  (≠ W_T² de Itô "ingenuo").
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MCEstimate:
    """Estimación Monte Carlo con error estándar."""

    value: float
    stderr: float

    def __str__(self) -> str:  # pragma: no cover - cosmético
        return f"{self.value:.6f} ± {1.96 * self.stderr:.6f}"


def mc(x: np.ndarray) -> MCEstimate:
    x = np.asarray(x, dtype=float)
    return MCEstimate(float(x.mean()), float(x.std(ddof=1) / np.sqrt(x.size)))


def ito_integral(u: np.ndarray, dW: np.ndarray) -> np.ndarray:
    """∑_k u_{t_k} ΔW_k (punto izquierdo). u y dW con forma (n_paths, n_steps)."""
    return np.sum(u * dW, axis=1)


def wiener_integral(h: np.ndarray, dW: np.ndarray) -> np.ndarray:
    """δ(h) para h determinista muestreada en la malla (n_steps,)."""
    return dW @ h


def skorokhod_product(
    G: np.ndarray, DG: np.ndarray, h: np.ndarray, dW: np.ndarray, dt: float
) -> np.ndarray:
    """δ(G h) = G ∫h dW - ⟨DG, h⟩.

    G: (n_paths,), DG: (n_paths, n_steps), h: (n_steps,) determinista.
    """
    return G * wiener_integral(h, dW) - (DG @ h) * dt


def inner(DF: np.ndarray, u: np.ndarray, dt: float) -> np.ndarray:
    """⟨DF, u⟩_{L²[0,T]} trayectoria a trayectoria."""
    return np.sum(DF * u, axis=1) * dt


def integration_by_parts_check(
    F: np.ndarray, DF: np.ndarray, u: np.ndarray, delta_u: np.ndarray, dt: float
) -> tuple[MCEstimate, MCEstimate]:
    """Devuelve (E[⟨DF,u⟩], E[F δ(u)]): deben coincidir salvo error MC."""
    return mc(inner(DF, u, dt)), mc(F * delta_u)
