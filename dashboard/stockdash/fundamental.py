"""Métricas fundamentales normalizadas a partir del diccionario ``info`` de Yahoo Finance.

Yahoo usa convenciones heterogéneas (``debtToEquity`` en %, ``dividendYield`` en % en versiones
recientes de yfinance, etc.). Aquí todo se lleva a **fracciones** (0.15 = 15 %) y a múltiplos
puros, y lo que falta o no tiene sentido (p. ej. PER con beneficio negativo) queda como NaN o
se marca explícitamente.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def _num(info: dict[str, Any], *keys: str) -> float:
    """Primer valor numérico finito entre ``keys``; NaN si no hay ninguno."""
    for k in keys:
        v = info.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
            return float(v)
    return np.nan


def _ratio(a: float, b: float) -> float:
    return a / b if (np.isfinite(a) and np.isfinite(b) and b != 0) else np.nan


def extract(info: dict[str, Any], price: float | None = None) -> dict[str, Any]:
    """Convierte ``yfinance.Ticker.info`` en métricas homogéneas.

    Devuelve claves de texto (``name``, ``sector``, ``industry``, ``currency``) y numéricas:

    * Valoración: ``pe_trailing``, ``pe_forward``, ``peg``, ``ev_ebitda``, ``ps``, ``pb``,
      ``fcf_yield``, ``div_yield``.
    * Calidad: ``roe``, ``roa``, ``gross_margin``, ``op_margin``, ``net_margin``.
    * Crecimiento: ``rev_growth``, ``eps_growth``.
    * Salud: ``debt_equity`` (múltiplo), ``net_debt_ebitda``, ``current_ratio``.
    * Analistas: ``target_upside``, ``rec_mean`` (1 = compra fuerte … 5 = venta), ``n_analysts``.
    """
    px = price if price is not None else _num(info, "currentPrice", "regularMarketPrice",
                                                  "previousClose")
    eps_t, eps_f = _num(info, "trailingEps"), _num(info, "forwardEps")
    pe_t, pe_f = _num(info, "trailingPE"), _num(info, "forwardPE")
    # PER con beneficio negativo: Yahoo a veces lo omite; lo marcamos como -1 (sin beneficio).
    if not np.isfinite(pe_t) and np.isfinite(eps_t) and eps_t <= 0:
        pe_t = -1.0
    if not np.isfinite(pe_f) and np.isfinite(eps_f) and eps_f <= 0:
        pe_f = -1.0

    mcap = _num(info, "marketCap")
    ebitda = _num(info, "ebitda")
    debt, cash = _num(info, "totalDebt"), _num(info, "totalCash")
    net_debt = debt - (cash if np.isfinite(cash) else 0.0) if np.isfinite(debt) else np.nan

    de = _num(info, "debtToEquity")
    de = de / 100.0 if np.isfinite(de) else np.nan  # Yahoo lo da en %

    div_rate = _num(info, "dividendRate", "trailingAnnualDividendRate")
    div_yield = _ratio(div_rate, px) if np.isfinite(div_rate) else 0.0

    target = _num(info, "targetMeanPrice")
    n_an = _num(info, "numberOfAnalystOpinions")

    return {
        "name": info.get("shortName") or info.get("longName") or "",
        "sector": info.get("sector") or "—",
        "industry": info.get("industry") or "—",
        "currency": info.get("currency") or "",
        "market_cap": mcap,
        # valoración
        "pe_trailing": pe_t,
        "pe_forward": pe_f,
        "peg": _num(info, "trailingPegRatio", "pegRatio"),
        "ev_ebitda": _num(info, "enterpriseToEbitda"),
        "ps": _num(info, "priceToSalesTrailing12Months"),
        "pb": _num(info, "priceToBook"),
        "fcf_yield": _ratio(_num(info, "freeCashflow"), mcap),
        "div_yield": div_yield,
        # calidad
        "roe": _num(info, "returnOnEquity"),
        "roa": _num(info, "returnOnAssets"),
        "gross_margin": _num(info, "grossMargins"),
        "op_margin": _num(info, "operatingMargins"),
        "net_margin": _num(info, "profitMargins"),
        # crecimiento
        "rev_growth": _num(info, "revenueGrowth"),
        "eps_growth": _num(info, "earningsGrowth", "earningsQuarterlyGrowth"),
        # salud financiera
        "debt_equity": de,
        "net_debt_ebitda": _ratio(net_debt, ebitda) if (np.isfinite(ebitda) and ebitda > 0)
        else np.nan,
        "current_ratio": _num(info, "currentRatio"),
        # analistas
        "target_upside": _ratio(target, px) - 1.0 if np.isfinite(target) else np.nan,
        "rec_mean": _num(info, "recommendationMean"),
        "n_analysts": n_an,
    }
