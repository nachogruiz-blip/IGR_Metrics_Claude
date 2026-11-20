"""Divisas (curso §8): pips, lotes, cruces, forwards por paridad cubierta y carry."""
from __future__ import annotations

import math

STANDARD_LOT = 100_000

# Sesiones aproximadas en horas UTC [apertura, cierre) (sin horario de verano).
SESSIONS = {"Sídney": (21, 6), "Tokio": (0, 9), "Londres": (7, 16), "Nueva York": (12, 21)}


def split_pair(pair: str) -> tuple[str, str]:
    p = pair.replace("/", "").upper()
    if len(p) != 6:
        raise ValueError(f"par no válido: {pair}")
    return p[:3], p[3:]


def pip_size(pair: str) -> float:
    """0,01 si la divisa cotizada es JPY; 0,0001 en el resto."""
    return 0.01 if split_pair(pair)[1] == "JPY" else 0.0001


def pip_value(pair: str, rate: float, lots: float = 1.0, account_ccy: str = "USD",
              quote_to_account: float | None = None) -> float:
    """Valor de un pip en la divisa de la cuenta.

    En divisa cotizada vale pip·lotes·100 000. Se convierte: si la cuenta es la cotizada, nada;
    si es la base, ÷ rate; si es otra, × ``quote_to_account`` (unidades de cuenta por unidad cotizada).
    """
    base, quote = split_pair(pair)
    v = pip_size(pair) * lots * STANDARD_LOT
    account_ccy = account_ccy.upper()
    if account_ccy == quote:
        return v
    if account_ccy == base:
        return v / rate
    if quote_to_account is None:
        raise ValueError("indica quote_to_account para convertir a la divisa de la cuenta")
    return v * quote_to_account


def lots_for_risk(equity: float, risk_pct: float, stop_pips: float, pip_value_per_lot: float,
                  step: float = 0.01) -> float:
    """Lotes tal que el stop cueste ``risk_pct`` del capital (redondeo a micro-lotes)."""
    raw = equity * risk_pct / (stop_pips * pip_value_per_lot)
    return math.floor(raw / step + 1e-9) * step


def usd_value(quotes: dict[str, float], ccy: str) -> float:
    """Dólares por unidad de ``ccy`` a partir de cotizaciones contra USD (EURUSD, USDJPY...)."""
    ccy = ccy.upper()
    if ccy == "USD":
        return 1.0
    if ccy + "USD" in quotes:
        return quotes[ccy + "USD"]
    if "USD" + ccy in quotes:
        return 1.0 / quotes["USD" + ccy]
    raise KeyError(f"falta cotización de {ccy} contra USD")


def cross_rate(quotes: dict[str, float], pair: str) -> float:
    """Tipo cruzado vía USD: BASE/QUOTE = (USD por BASE)/(USD por QUOTE). P. ej. EURJPY = EURUSD·USDJPY."""
    base, quote = split_pair(pair)
    return usd_value(quotes, base) / usd_value(quotes, quote)


def triangular_arbitrage(ab: float, bc: float, ac: float) -> float:
    """Beneficio relativo de A→B→C→A con precios medios: ab·bc/ac − 1 (≈ 0 sin arbitraje)."""
    return ab * bc / ac - 1


def forward_rate(spot: float, r_quote: float, r_base: float, t: float, continuous: bool = False) -> float:
    """Paridad cubierta de intereses: F = S·(1 + r_q t)/(1 + r_b t)  (o S·e^{(r_q − r_b)t})."""
    if continuous:
        return spot * math.exp((r_quote - r_base) * t)
    return spot * (1 + r_quote * t) / (1 + r_base * t)


def forward_points(spot: float, forward: float, pair: str) -> float:
    """Puntos forward en pips: (F − S)/pip."""
    return (forward - spot) / pip_size(pair)


def carry_return(s0: float, s1: float, r_base: float, r_quote: float, t: float) -> float:
    """Rentabilidad (sobre el nocional en cotizada) de comprar BASE financiándose en QUOTE.

    Pide prestado S₀ en cotizada, compra 1 de base, la invierte a r_b y deshace a S₁:
    [(1 + r_b t)·S₁ − (1 + r_q t)·S₀] / S₀ ≈ (S₁/S₀ − 1) + (r_b − r_q)·t.
    """
    return ((1 + r_base * t) * s1 - (1 + r_quote * t) * s0) / s0


def carry_breakeven_spot(s0: float, r_base: float, r_quote: float, t: float) -> float:
    """Spot a vencimiento que anula el carry: el forward de la paridad cubierta."""
    return forward_rate(s0, r_quote, r_base, t)


def relative_ppp(s0: float, cpi_base_ratio: float, cpi_quote_ratio: float) -> float:
    """PPA relativa: S_justo = S₀·(P_q,t/P_q,0)/(P_b,t/P_b,0)."""
    return s0 * cpi_quote_ratio / cpi_base_ratio


def open_sessions(hour_utc: float) -> list[str]:
    out = []
    for name, (o, c) in SESSIONS.items():
        inside = o <= hour_utc < c if o < c else (hour_utc >= o or hour_utc < c)
        if inside:
            out.append(name)
    return out
