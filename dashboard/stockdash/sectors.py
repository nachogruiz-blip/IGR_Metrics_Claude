"""Múltiplos de referencia por sector para valorar en términos **relativos**.

Un PER de 30 es caro para un banco y normal para una empresa de software; por eso los múltiplos
de valoración (PER, EV/EBITDA, precio/ventas, precio/valor contable) se puntúan frente a la
mediana aproximada de su sector, no contra umbrales absolutos.

Puntuación relativa (``relative_multiple``):

    score = clip( −log(x / mediana) / log(SPREAD), −1, 1 ),   SPREAD = 1.6

es decir, 0 en la mediana del sector, +1 si cotiza 1,6 veces más barato y −1 si 1,6 veces
más caro (simétrico en escala logarítmica). Un múltiplo ≤ 0 (pérdidas) puntúa −1.

Valores de referencia
---------------------
Medianas **aproximadas** de grandes compañías de EE. UU. y Europa (orden de magnitud de las
tablas sectoriales de A. Damodaran, NYU Stern, y de los múltiplos de los índices sectoriales
MSCI en 2024–2026), redondeadas. No son datos en tiempo real: revisarlos una vez al año.
``None`` significa que el múltiplo no es significativo en ese sector y el indicador no puntúa
(p. ej. EV/EBITDA o precio/ventas en banca; precio/valor contable fuera de financieras e
inmobiliarias).

Las claves de sector son las de Yahoo Finance (``info["sector"]``).
"""

from __future__ import annotations

from typing import Callable

import numpy as np

SPREAD = 1.6

# sector Yahoo → mediana de referencia de cada múltiplo
SECTOR_MULTIPLES: dict[str, dict[str, float | None]] = {
    #                         PER est.  PER hist.  EV/EBITDA  P/ventas  P/VC
    "Technology":             {"pe_forward": 25, "pe_trailing": 30, "ev_ebitda": 20, "ps": 6.0, "pb": None},
    "Communication Services": {"pe_forward": 18, "pe_trailing": 20, "ev_ebitda": 10, "ps": 3.0, "pb": None},
    "Consumer Cyclical":      {"pe_forward": 20, "pe_trailing": 22, "ev_ebitda": 13, "ps": 1.5, "pb": None},
    "Consumer Defensive":     {"pe_forward": 19, "pe_trailing": 21, "ev_ebitda": 13, "ps": 1.3, "pb": None},
    "Healthcare":             {"pe_forward": 18, "pe_trailing": 24, "ev_ebitda": 15, "ps": 3.5, "pb": None},
    "Industrials":            {"pe_forward": 20, "pe_trailing": 23, "ev_ebitda": 14, "ps": 2.0, "pb": None},
    "Energy":                 {"pe_forward": 11, "pe_trailing": 12, "ev_ebitda": 6, "ps": 1.2, "pb": None},
    "Utilities":              {"pe_forward": 16, "pe_trailing": 18, "ev_ebitda": 11, "ps": 2.5, "pb": None},
    "Basic Materials":        {"pe_forward": 15, "pe_trailing": 17, "ev_ebitda": 9, "ps": 1.8, "pb": None},
    "Real Estate":            {"pe_forward": 30, "pe_trailing": 32, "ev_ebitda": 18, "ps": 6.0, "pb": 1.6},
    "Financial Services":     {"pe_forward": 12, "pe_trailing": 13, "ev_ebitda": None, "ps": None, "pb": 1.3},
}
DEFAULT_MULTIPLES: dict[str, float | None] = {
    "pe_forward": 18, "pe_trailing": 21, "ev_ebitda": 12, "ps": 2.5, "pb": None,
}
RELATIVE_KEYS = tuple(DEFAULT_MULTIPLES)  # indicadores que se puntúan frente al sector


def sector_medians(sector: str | None) -> dict[str, float | None]:
    """Medianas del sector; las del mercado en general si el sector es desconocido."""
    return SECTOR_MULTIPLES.get(sector or "", DEFAULT_MULTIPLES)


def relative_multiple(median: float, spread: float = SPREAD) -> Callable[[float], float]:
    """Puntúa un múltiplo «menor es mejor» frente a la ``median`` del sector (ver módulo)."""
    k = np.log(spread)

    def f(x: float) -> float:
        if x is None or not np.isfinite(x):
            return np.nan
        if x <= 0:
            return -1.0
        return float(np.clip(-np.log(x / median) / k, -1.0, 1.0))
    return f


def relative_scorers(sector: str | None) -> dict[str, Callable[[float], float] | None]:
    """{clave de indicador: función de puntuación relativa o None (no puntúa en el sector)}."""
    med = sector_medians(sector)
    return {k: (relative_multiple(v) if v else None) for k, v in med.items()}
