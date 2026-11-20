"""Renta fija (curso §10): precio, TIR, duración, convexidad y DV01."""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq


def _cashflows(face: float, coupon: float, years: float, freq: int):
    n = int(round(years * freq))
    t = np.arange(1, n + 1) / freq
    cf = np.full(n, face * coupon / freq)
    cf[-1] += face
    return t, cf


def bond_price(face: float, coupon: float, ytm: float, years: float, freq: int = 2) -> float:
    """P = Σ CF_k / (1 + y/f)^{f t_k} (fecha de pago de cupón, precio limpio = sucio)."""
    t, cf = _cashflows(face, coupon, years, freq)
    return float(np.sum(cf / (1 + ytm / freq) ** (freq * t)))


def ytm(price: float, face: float, coupon: float, years: float, freq: int = 2) -> float:
    return float(brentq(lambda y: bond_price(face, coupon, y, years, freq) - price, -0.05, 1.0))


def macaulay_duration(face: float, coupon: float, y: float, years: float, freq: int = 2) -> float:
    t, cf = _cashflows(face, coupon, years, freq)
    disc = cf / (1 + y / freq) ** (freq * t)
    return float(np.sum(t * disc) / np.sum(disc))


def modified_duration(face: float, coupon: float, y: float, years: float, freq: int = 2) -> float:
    """D_mod = D_mac/(1 + y/f) = −(1/P) dP/dy."""
    return macaulay_duration(face, coupon, y, years, freq) / (1 + y / freq)


def convexity(face: float, coupon: float, y: float, years: float, freq: int = 2) -> float:
    """C = (1/P) d²P/dy² = Σ CF_k t_k (t_k + 1/f) (1+y/f)^{−f t_k − 2} / P."""
    t, cf = _cashflows(face, coupon, years, freq)
    p = bond_price(face, coupon, y, years, freq)
    return float(np.sum(cf * t * (t + 1 / freq) / (1 + y / freq) ** (freq * t + 2)) / p)


def dv01(face: float, coupon: float, y: float, years: float, freq: int = 2) -> float:
    """Variación de precio por −1 pb: D_mod·P·0,0001."""
    return modified_duration(face, coupon, y, years, freq) * bond_price(face, coupon, y, years, freq) * 1e-4


def price_change_approx(price: float, mod_dur: float, conv: float, dy: float) -> float:
    """ΔP ≈ −D_mod·P·Δy + ½·C·P·Δy²."""
    return -mod_dur * price * dy + 0.5 * conv * price * dy**2


def dv01_hedge_ratio(dv01_position: float, dv01_hedge: float) -> float:
    """Nocional del instrumento de cobertura por unidad de posición para DV01 neutro."""
    return dv01_position / dv01_hedge
