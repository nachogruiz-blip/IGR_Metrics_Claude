"""Cripto (curso §12): perpetuos, funding, base y liquidación."""
from __future__ import annotations


def annualized_funding(rate_per_interval: float, hours: float = 8.0) -> float:
    """Funding anualizado simple: tasa · (24/horas) · 365."""
    return rate_per_interval * 24 / hours * 365


def annualized_basis(spot: float, fut: float, days: float) -> float:
    """Base anualizada simple de un futuro con vencimiento: (F/S − 1)·365/días."""
    return (fut / spot - 1) * 365 / days


def cash_and_carry_pnl(spot: float, fut: float, notional: float, fees_bps: float = 10.0) -> float:
    """Comprar contado y vender futuro: se cobra la base F − S (al converger), menos 4 comisiones."""
    qty = notional / spot
    return qty * (fut - spot) - 4 * fees_bps * 1e-4 * notional


def liquidation_price(entry: float, leverage: float, maintenance: float = 0.005, side: str = "long") -> float:
    """Liquidación aproximada en margen aislado (lineal, sin comisiones).

    Largo: entry·(1 − 1/L + mm). Corto: entry·(1 + 1/L − mm).
    """
    if side == "long":
        return entry * (1 - 1 / leverage + maintenance)
    return entry * (1 + 1 / leverage - maintenance)
