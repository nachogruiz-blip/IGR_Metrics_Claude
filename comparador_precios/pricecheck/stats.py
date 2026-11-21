"""Estadísticos de precio sobre un subconjunto de ofertas elegido por el usuario.

La app deja marcar qué ofertas entran en la comparativa y qué estadísticos se muestran; aquí se
calculan (la app no calcula). ``None`` si no hay datos suficientes (p. ej. desviación con 1 valor).
"""

from __future__ import annotations

import statistics as st
from typing import Callable, Sequence

from .models import Assessment, finite


def _quantile(p: float) -> Callable[[Sequence[float]], float]:
    def f(xs: Sequence[float]) -> float:
        xs = sorted(xs)
        if len(xs) == 1:
            return xs[0]
        h = (len(xs) - 1) * p          # interpolación lineal (tipo 7, la de numpy/Excel)
        lo = int(h)
        return xs[lo] + (h - lo) * (xs[min(lo + 1, len(xs) - 1)] - xs[lo])
    return f


# nombre → (función, mínimo de valores). El orden es el de la interfaz.
STATS: dict[str, tuple[Callable[[Sequence[float]], float], int]] = {
    "Mediana": (st.median, 1),
    "Media": (st.fmean, 1),
    "Mínimo": (min, 1),
    "Máximo": (max, 1),
    "Percentil 25": (_quantile(0.25), 1),
    "Percentil 75": (_quantile(0.75), 1),
    "Rango intercuartílico": (lambda xs: _quantile(0.75)(xs) - _quantile(0.25)(xs), 2),
    "Desviación típica": (st.stdev, 2),
    "Media recortada 10 %": (lambda xs: st.fmean(_trim(xs, 0.10)), 1),
}
DEFAULT_STATS = ("Mediana", "Media", "Mínimo", "Máximo")
# estadísticos que son una posición en el eje de precios (se pueden dibujar como línea)
LOCATION_STATS = ("Mediana", "Media", "Percentil 25", "Percentil 75", "Media recortada 10 %")

# base de precio sobre la que calcular
BASES: dict[str, Callable[[Assessment], float]] = {
    "Precio final": lambda a: a.final_price,
    "Precio + envío": lambda a: a.offer.total,
    "Precio": lambda a: a.offer.price,
}


def _trim(xs: Sequence[float], frac: float) -> list[float]:
    xs = sorted(xs)
    k = int(len(xs) * frac)
    return xs[k:len(xs) - k] if len(xs) - 2 * k > 0 else xs


def describe(values: Sequence[float], names: Sequence[str] = DEFAULT_STATS) -> dict[str, float | None]:
    """{estadístico: valor} para los ``names`` pedidos (en el orden de ``STATS``)."""
    xs = [float(v) for v in values if finite(v)]
    out: dict[str, float | None] = {}
    for name, (fn, need) in STATS.items():
        if name in names:
            out[name] = fn(xs) if len(xs) >= need else None
    return out


def describe_offers(assessments: Sequence[Assessment], names: Sequence[str] = DEFAULT_STATS,
                    base: str = "Precio final") -> dict[str, float | None]:
    return describe([BASES[base](a) for a in assessments], names)


def default_selection(assessments: Sequence[Assessment]) -> list[bool]:
    """Qué ofertas entran por defecto en la comparativa: todas salvo las que exigen contratar
    un servicio y las de producto no nuevo."""
    return [not a.requires_service and a.offer.condition == "nuevo" for a in assessments]
