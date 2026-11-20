"""Puntuación de fiabilidad de una tienda (0–100) y detección de precios anómalos.

Fórmulas y umbrales documentados en ``METODOLOGIA.md``; cualquier cambio aquí debe reflejarse
allí y en ``tests/test_scoring.py``.
"""

from __future__ import annotations

import math
from statistics import median

from .models import OfficialStatus, Reliability, Reputation, finite

# --- valoración bayesiana: r̄ = (n·r + m·μ) / (n + m)
PRIOR_MEAN = 3.5      # μ: nota que se supone a una tienda sin opiniones
PRIOR_WEIGHT = 50     # m: nº de opiniones «ficticias» con nota μ

WEIGHTS = {           # pesos de los componentes (se renormalizan si falta alguno)
    "valoracion": 0.40,
    "volumen": 0.10,
    "problemas": 0.20,
    "antiguedad": 0.15,
    "oficial": 0.15,
}
OFFICIAL_SCORE = {"oficial": 1.0, "minorista": 0.85, "marketplace_directo": 0.8,
                  "marketplace_tercero": 0.45, "desconocido": 0.4}

ISSUE_RATE_ZERO = 0.5     # tasa de problemas que deja el componente en 0
AGE_FULL_DAYS = 3 * 365   # antigüedad con la que el componente llega a 1
NEW_DOMAIN_DAYS = 180     # dominio «reciente»
FRAUD_VETO = 2            # nº de reportes de fraude que fuerzan «riesgo»
ANOMALY_RATIO = 0.6       # precio < 60 % de la mediana ⇒ anómalo
ANOMALY_MIN_OFFERS = 3
ANOMALY_PENALTY = 0.7     # factor sobre la puntuación si el precio es anómalo
NO_HTTPS_CAP = 30.0

LEVEL_THRESHOLDS = (("alta", 75.0), ("media", 55.0), ("baja", 35.0))  # resto: «riesgo»


def bayes_rating(rating: float | None, n: int, mu: float = PRIOR_MEAN, m: int = PRIOR_WEIGHT) -> float | None:
    if rating is None or n <= 0:
        return None
    return (n * rating + m * mu) / (n + m)


def level_for(score: float) -> str:
    if not finite(score):
        return "baja"
    return next((lvl for lvl, th in LEVEL_THRESHOLDS if score >= th), "riesgo")


def components(rep: Reputation, official: OfficialStatus) -> dict[str, float]:
    nan = float("nan")
    br = bayes_rating(rep.rating, rep.review_count)
    issue_rate = len(rep.issues) / rep.reviews_analyzed if rep.reviews_analyzed > 0 else None
    return {
        "valoracion": (br - 1.0) / 4.0 if br is not None else nan,
        "volumen": min(1.0, math.log10(1 + rep.review_count) / 4.0) if rep.review_count > 0 else nan,
        "problemas": max(0.0, 1.0 - issue_rate / ISSUE_RATE_ZERO) if issue_rate is not None else nan,
        "antiguedad": min(1.0, rep.domain_age_days / AGE_FULL_DAYS) if rep.domain_age_days is not None else nan,
        "oficial": OFFICIAL_SCORE[official.status],
    }


def weighted(comps: dict[str, float]) -> float:
    """Media ponderada de los componentes con dato, en 0–100 (pesos renormalizados)."""
    num = sum(WEIGHTS[k] * v for k, v in comps.items() if finite(v))
    den = sum(WEIGHTS[k] for k, v in comps.items() if finite(v))
    return 100.0 * num / den if den > 0 else float("nan")


def reliability(rep: Reputation, official: OfficialStatus, price_anomaly: bool = False) -> Reliability:
    comps = components(rep, official)
    score = weighted(comps)
    warns: list[str] = []
    counts = rep.issue_counts()

    if not finite(comps["valoracion"]):
        warns.append("Sin opiniones de la tienda en fuentes independientes")
    elif rep.rating is not None and rep.rating < 2.5:
        warns.append(f"Valoración baja: {rep.rating:.1f}/5 ({rep.review_count} opiniones)")
    if counts["entrega"]:
        warns.append(f"{counts['entrega']} reporte(s) de problemas de entrega")
    if counts["devolucion"]:
        warns.append(f"{counts['devolucion']} reporte(s) de problemas con devoluciones o reembolsos")
    if counts["fraude"]:
        warns.append(f"{counts['fraude']} reporte(s) de posible fraude")
    new_domain = rep.domain_age_days is not None and rep.domain_age_days < NEW_DOMAIN_DAYS
    if new_domain:
        warns.append(f"Dominio registrado hace sólo {rep.domain_age_days} días")
    if official.status == "marketplace_tercero":
        warns.append("Vendedor externo de marketplace: revisa su valoración propia en la plataforma")

    if price_anomaly and finite(score):
        score *= ANOMALY_PENALTY
        warns.append("Precio anormalmente bajo respecto al resto de tiendas (señal típica de fraude)")
    if rep.https is False and finite(score):
        score = min(score, NO_HTTPS_CAP)
        warns.append("La web no usa HTTPS")

    level = level_for(score)
    if counts["fraude"] >= FRAUD_VETO or (new_domain and price_anomaly):
        level = "riesgo"
        score = min(score, 34.9) if finite(score) else score
    # sin opiniones independientes de la tienda no se puede decir más que «baja»
    if not finite(comps["valoracion"]) and level in ("alta", "media"):
        level = "baja"
        score = min(score, LEVEL_THRESHOLDS[1][1] - 0.1)
    return Reliability(score=score, level=level, components=comps, warnings=warns)


def anomalies(totals: list[float]) -> tuple[float | None, list[bool]]:
    """(mediana, marca de anomalía por oferta). Sin marcas con menos de 3 ofertas."""
    if not totals:
        return None, []
    med = median(totals)
    if len(totals) < ANOMALY_MIN_OFFERS:
        return med, [False] * len(totals)
    return med, [t < ANOMALY_RATIO * med for t in totals]
