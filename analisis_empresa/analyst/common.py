"""Piezas comunes: puntuaciones en [−1, 1], ítems evaluados y pilares.

Convención: +1 = favorable para comprar, −1 = desfavorable, 0 = neutro. Los valores se guardan
en fracciones (0.15 = 15 %); el formato es cosa de la presentación (``fmt``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

TRADING_DAYS = 252


def finite(x) -> bool:
    try:
        return x is not None and bool(np.isfinite(float(x)))
    except (TypeError, ValueError):
        return False


def ramp(x: float, lo: float, hi: float) -> float:
    """Lineal de −1 (en ``lo``) a +1 (en ``hi``), recortada. Si ``lo > hi`` se invierte el
    sentido (menos es mejor). NaN si no hay dato."""
    if not finite(x):
        return float("nan")
    return float(np.clip(-1.0 + 2.0 * (float(x) - lo) / (hi - lo), -1.0, 1.0))


def piecewise(x: float, xs: list[float], ys: list[float]) -> float:
    """Interpolación lineal por tramos (``xs`` crecientes), constante fuera del rango."""
    if not finite(x):
        return float("nan")
    return float(np.interp(float(x), xs, ys))


def fmt(v, kind: str = "num") -> str:
    """Formato para tablas e informe: ``pct`` (+12.3 %), ``pct0`` (12.3 %), ``x`` (12.3×),
    ``num`` (1.23), ``int`` (7), ``money`` (1 234.56)."""
    if not finite(v):
        return "—"
    v = float(v)
    return {
        "pct": f"{v:+.1%}", "pct0": f"{v:.1%}", "x": f"{v:.1f}×", "num": f"{v:.2f}",
        "int": f"{v:.0f}", "money": f"{v:,.2f}".replace(",", " "),
    }[kind]


@dataclass
class Item:
    """Un indicador evaluado: valor, puntuación en [−1, 1] (NaN = sin dato) y lectura."""

    key: str
    label: str
    value: float
    score: float
    kind: str = "num"          # formato del valor (ver ``fmt``)
    note: str = ""             # lectura en lenguaje natural
    weight: float = 1.0

    @property
    def shown(self) -> str:
        return fmt(self.value, self.kind)


@dataclass
class Pillar:
    """Bloque de análisis (balance, valoración, técnico…) con su puntuación agregada."""

    name: str
    items: list[Item] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)   # observaciones que no puntúan

    @property
    def score(self) -> float:
        """Media ponderada de las puntuaciones disponibles (los pesos se renormalizan)."""
        pairs = [(i.score, i.weight) for i in self.items if finite(i.score) and i.weight > 0]
        if not pairs:
            return float("nan")
        s, w = np.array(pairs).T
        return float(np.clip((s * w).sum() / w.sum(), -1.0, 1.0))

    @property
    def coverage(self) -> float:
        """Fracción del peso con dato."""
        tot = sum(i.weight for i in self.items)
        ok = sum(i.weight for i in self.items if finite(i.score))
        return ok / tot if tot else 0.0

    def get(self, key: str) -> Item | None:
        return next((i for i in self.items if i.key == key), None)

    def value(self, key: str) -> float:
        it = self.get(key)
        return it.value if it is not None else float("nan")


def weighted(scores: dict[str, float], weights: dict[str, float]) -> float:
    """Media ponderada de puntuaciones ignorando las que faltan."""
    pairs = [(scores[k], w) for k, w in weights.items() if finite(scores.get(k))]
    if not pairs:
        return float("nan")
    s, w = np.array(pairs).T
    return float((s * w).sum() / w.sum())
