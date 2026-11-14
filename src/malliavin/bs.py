"""Fórmulas cerradas de Black–Scholes usadas como referencia exacta."""

from __future__ import annotations

import numpy as np
from scipy.stats import norm


def _d1d2(S0, K, T, r, sigma):
    d1 = (np.log(S0 / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    return d1, d1 - sigma * np.sqrt(T)


def call_price(S0, K, T, r, sigma):
    d1, d2 = _d1d2(S0, K, T, r, sigma)
    return S0 * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)


def call_greeks(S0, K, T, r, sigma) -> dict[str, float]:
    """Delta, gamma, vega y rho de una call europea."""
    d1, d2 = _d1d2(S0, K, T, r, sigma)
    return {
        "delta": norm.cdf(d1),
        "gamma": norm.pdf(d1) / (S0 * sigma * np.sqrt(T)),
        "vega": S0 * norm.pdf(d1) * np.sqrt(T),
        "rho": K * T * np.exp(-r * T) * norm.cdf(d2),
    }


def digital_price(S0, K, T, r, sigma):
    """Digital cash-or-nothing: paga 1 si S_T > K."""
    _, d2 = _d1d2(S0, K, T, r, sigma)
    return np.exp(-r * T) * norm.cdf(d2)


def digital_greeks(S0, K, T, r, sigma) -> dict[str, float]:
    d1, d2 = _d1d2(S0, K, T, r, sigma)
    disc = np.exp(-r * T)
    sq = sigma * np.sqrt(T)
    return {
        "delta": disc * norm.pdf(d2) / (S0 * sq),
        "gamma": -disc * norm.pdf(d2) * d1 / (S0**2 * sq**2),
        "vega": -disc * norm.pdf(d2) * d1 / sigma,
        "rho": disc * (-T * norm.cdf(d2) + norm.pdf(d2) * np.sqrt(T) / sigma),
    }


def call_delta_t(S, K, tau, r, sigma):
    """Delta de la call en tiempo t con vencimiento residual tau = T - t (vectorizado)."""
    tau = np.maximum(tau, 1e-12)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * tau) / (sigma * np.sqrt(tau))
    return norm.cdf(d1)


def lognormal_pdf(x, S0, T, r, sigma):
    """Densidad de S_T bajo GBM."""
    x = np.asarray(x, dtype=float)
    m = np.log(S0) + (r - 0.5 * sigma**2) * T
    s = sigma * np.sqrt(T)
    out = np.zeros_like(x)
    pos = x > 0
    out[pos] = norm.pdf((np.log(x[pos]) - m) / s) / (x[pos] * s)
    return out
