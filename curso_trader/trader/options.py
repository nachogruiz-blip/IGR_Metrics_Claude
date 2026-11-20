"""Opciones y volatilidad (curso §11): Black–Scholes(–Merton), Black-76, griegas, IV."""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm


def _d1d2(S, K, T, r, sigma, q):
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    return d1, d1 - sigma * np.sqrt(T)


def bs_price(S, K, T, r, sigma, q=0.0, kind: str = "call"):
    """Black–Scholes–Merton con dividendo continuo q (vectorizado).

    Con q = r_extranjero es Garman–Kohlhagen (FX); con S = F y q = r es Black-76.
    """
    d1, d2 = _d1d2(S, K, T, r, sigma, q)
    if kind == "call":
        return S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    return K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1)


def black76(F, K, T, r, sigma, kind: str = "call"):
    """Opciones sobre futuros: descuento e^{−rT} de [F N(d1) − K N(d2)]."""
    return bs_price(F, K, T, r, sigma, q=r, kind=kind)


def garman_kohlhagen(S, K, T, r_dom, r_for, sigma, kind: str = "call"):
    return bs_price(S, K, T, r_dom, sigma, q=r_for, kind=kind)


def greeks(S, K, T, r, sigma, q=0.0, kind: str = "call") -> dict:
    """Delta, gamma, vega (por 1 punto de vol = 0,01), theta (por día natural), rho (por 1 %)."""
    d1, d2 = _d1d2(S, K, T, r, sigma, q)
    eq, er = np.exp(-q * T), np.exp(-r * T)
    pdf = norm.pdf(d1)
    gamma = eq * pdf / (S * sigma * np.sqrt(T))
    vega = S * eq * pdf * np.sqrt(T) / 100
    common = -S * eq * pdf * sigma / (2 * np.sqrt(T))
    if kind == "call":
        delta = eq * norm.cdf(d1)
        theta = common - r * K * er * norm.cdf(d2) + q * S * eq * norm.cdf(d1)
        rho = K * T * er * norm.cdf(d2) / 100
    else:
        delta = -eq * norm.cdf(-d1)
        theta = common + r * K * er * norm.cdf(-d2) - q * S * eq * norm.cdf(-d1)
        rho = -K * T * er * norm.cdf(-d2) / 100
    return {"delta": delta, "gamma": gamma, "vega": vega, "theta": theta / 365, "rho": rho}


def implied_vol(price: float, S: float, K: float, T: float, r: float, q: float = 0.0,
                kind: str = "call") -> float:
    """Volatilidad implícita por Brent en [1e-4, 5]."""
    intrinsic = max(0.0, (S * math.exp(-q * T) - K * math.exp(-r * T)) * (1 if kind == "call" else -1))
    if price <= intrinsic + 1e-12:
        raise ValueError("precio por debajo del valor intrínseco descontado")
    return float(brentq(lambda s: float(bs_price(S, K, T, r, s, q, kind)) - price, 1e-4, 5.0))


def expected_move(S: float, iv: float, days: float, calendar: int = 365) -> float:
    """Movimiento esperado a 1σ: S·σ·√(días/365)."""
    return S * iv * math.sqrt(days / calendar)


def straddle_breakevens(K: float, call: float, put: float) -> tuple[float, float]:
    prem = call + put
    return K - prem, K + prem


def straddle_implied_move(S: float, straddle: float) -> float:
    """Regla del operador: movimiento implícito ≈ precio del straddle ATM / S (≈ 0,8·σ√T)."""
    return straddle / S


def payoff(S_T, legs: list[tuple[str, float, float, float]]):
    """Pago a vencimiento de una estrategia. ``legs``: (tipo, strike, cantidad, prima pagada)."""
    S_T = np.asarray(S_T, float)
    total = np.zeros_like(S_T)
    for kind, K, qty, prem in legs:
        if kind == "call":
            v = np.maximum(S_T - K, 0)
        elif kind == "put":
            v = np.maximum(K - S_T, 0)
        else:  # subyacente: K = precio de entrada
            v = S_T - K
        total += qty * (v - prem)
    return total
