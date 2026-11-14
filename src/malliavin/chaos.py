r"""Descomposición en caos de Wiener para funcionales F = f(W_T).

Para F = f(W_T) con E[F^2] < ∞:

    F = \sum_{n\ge 0} I_n(f_n),   f_n = c_n 1_{[0,T]}^{\otimes n},

y como I_n(1_{[0,T]}^{\otimes n}) = T^{n/2} He_n(W_T / \sqrt{T}) (Hermite probabilísticos;
la guía PDF los llama H_n, Definición 6.1),

    F = \sum_n a_n He_n(Z),   Z = W_T/\sqrt{T},   a_n = E[f(\sqrt{T} Z) He_n(Z)] / n!.

Los coeficientes a_n se calculan por integración numérica frente a la densidad
gaussiana en una malla fina (robusto para pagos con saltos o esquinas, p.ej. digitales).
Además, la derivada de Malliavin actúa como operador de "aniquilación":
D_t He_n(Z) = n He_{n-1}(Z) / \sqrt{T}, de modo que F ∈ D^{1,2} si y sólo si
E||DF||^2_{L^2[0,T]} = \sum_n n·n!·a_n^2 < ∞.
"""

from __future__ import annotations

from math import factorial, sqrt, pi
from typing import Callable

import numpy as np
from numpy.polynomial import hermite_e as He


def hermite_e(n: int, x: np.ndarray) -> np.ndarray:
    """Polinomio de Hermite probabilista He_n(x)."""
    c = np.zeros(n + 1)
    c[n] = 1.0
    return He.hermeval(x, c)


def chaos_coefficients(
    f: Callable[[np.ndarray], np.ndarray], T: float, n_max: int, n_grid: int = 40_001, L: float = 14.0
) -> np.ndarray:
    """Coeficientes a_0..a_{n_max} de f(W_T) en la base He_n(W_T/√T).

    a_n = E[f(√T Z) He_n(Z)] / n!, integrando con la regla del trapecio en [-L, L].
    """
    x = np.linspace(-L, L, n_grid)
    w = np.exp(-0.5 * x**2) / sqrt(2 * pi) * (x[1] - x[0])
    w[[0, -1]] *= 0.5
    fx = f(sqrt(T) * x)
    return np.array(
        [np.sum(w * fx * hermite_e(n, x)) / factorial(n) for n in range(n_max + 1)]
    )


def chaos_truncation(a: np.ndarray, WT: np.ndarray, T: float, n: int | None = None) -> np.ndarray:
    """Suma parcial sum_{k<=n} a_k He_k(W_T/√T)."""
    n = len(a) - 1 if n is None else n
    return He.hermeval(np.asarray(WT) / sqrt(T), a[: n + 1])


def chaos_energy(a: np.ndarray) -> np.ndarray:
    """Varianza aportada por cada caos: E[I_n(f_n)^2] = n! a_n^2 (isometría)."""
    return np.array([factorial(n) * a[n] ** 2 for n in range(len(a))])


def exponential_martingale_coefficients(sigma: float, T: float, n_max: int) -> np.ndarray:
    """Caso exacto: exp(σW_T - σ²T/2) = sum σ^n T^{n/2} He_n(Z) / n!."""
    return np.array([(sigma * sqrt(T)) ** n / factorial(n) for n in range(n_max + 1)])
