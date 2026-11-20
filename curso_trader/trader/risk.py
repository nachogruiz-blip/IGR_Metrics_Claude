"""Gestión del riesgo y tamaño de posición (curso §4)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import norm


# ---------------------------------------------------------------- tamaño de posición
def position_size_stop(equity: float, risk_pct: float, entry: float, stop: float,
                       point_value: float = 1.0, lot: float = 1.0) -> float:
    """Unidades tales que tocar el stop cueste ``risk_pct`` del capital (curso §4.2).

    N = ⌊ equity·risk_pct / (|entry − stop|·point_value) ⌋, redondeado a múltiplos de ``lot``.
    ``point_value``: dinero por unidad de precio y por unidad de tamaño (1 en acciones,
    1000 $ en CL, 100 000·… en FX si se mide en lotes).
    """
    dist = abs(entry - stop)
    if dist <= 0:
        raise ValueError("entry y stop deben ser distintos")
    raw = equity * risk_pct / (dist * point_value)
    return math.floor(raw / lot + 1e-12) * lot


def atr_position_size(equity: float, risk_pct: float, atr: float, atr_mult: float = 2.0,
                      point_value: float = 1.0, lot: float = 1.0) -> float:
    """Stop a ``atr_mult``·ATR: el riesgo monetario es constante y el tamaño se adapta a la volatilidad."""
    return position_size_stop(equity, risk_pct, 0.0, atr_mult * atr, point_value, lot)


def vol_target_weight(target_vol: float, realized_vol: float | np.ndarray, max_leverage: float = 3.0):
    """Peso w = σ*/σ̂ acotado en [0, max_leverage] (volatility targeting)."""
    return np.clip(target_vol / np.asarray(realized_vol, dtype=float), 0.0, max_leverage)


def kelly_fraction(win_rate: float, payoff: float) -> float:
    """Kelly discreto: f* = p − (1 − p)/b con b = ganancia media / pérdida media."""
    return win_rate - (1 - win_rate) / payoff


def kelly_gaussian(mu: float, sigma: float) -> float:
    """Kelly continuo: f* = μ/σ² (exceso de rentabilidad y varianza en la misma unidad de tiempo)."""
    return mu / sigma**2


def growth_rate(f: np.ndarray | float, win_rate: float, payoff: float) -> np.ndarray:
    """Crecimiento logarítmico esperado por operación: g(f) = p·ln(1+fb) + (1−p)·ln(1−f)."""
    f = np.asarray(f, dtype=float)
    return win_rate * np.log1p(f * payoff) + (1 - win_rate) * np.log1p(-f)


def risk_of_ruin_mc(win_rate: float, payoff: float, risk_pct: float, ruin_dd: float = 0.5,
                    n_trades: int = 500, n_paths: int = 20_000, seed: int = 0) -> float:
    """Probabilidad (Monte Carlo) de sufrir una caída ≥ ``ruin_dd`` desde máximos en ``n_trades``.

    Fracción fija: cada operación gana ``risk_pct·payoff`` o pierde ``risk_pct`` del capital vivo.
    """
    rng = np.random.default_rng(seed)
    wins = rng.random((n_paths, n_trades)) < win_rate
    logr = np.where(wins, np.log1p(risk_pct * payoff), np.log1p(-risk_pct))
    eq = np.cumsum(logr, axis=1)
    dd = eq - np.maximum.accumulate(np.maximum(eq, 0.0), axis=1)
    return float(np.mean(dd.min(axis=1) <= np.log1p(-ruin_dd)))


# ---------------------------------------------------------------- VaR / ES
def var_parametric(mu: float, sigma: float, alpha: float = 0.99) -> float:
    """VaR gaussiano como pérdida positiva: −(μ + σ·Φ⁻¹(1−α))."""
    return -(mu + sigma * norm.ppf(1 - alpha))


def es_parametric(mu: float, sigma: float, alpha: float = 0.99) -> float:
    """Expected Shortfall gaussiano: −μ + σ·φ(Φ⁻¹(α))/(1−α)."""
    return -mu + sigma * norm.pdf(norm.ppf(alpha)) / (1 - alpha)


def var_historical(returns, alpha: float = 0.99) -> float:
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    return float(-np.quantile(r, 1 - alpha))


def es_historical(returns, alpha: float = 0.99) -> float:
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    q = np.quantile(r, 1 - alpha)
    return float(-r[r <= q].mean())


def scale_var(var_1d: float, days: int) -> float:
    """Regla de la raíz del tiempo (sólo válida con rentabilidades i.i.d.)."""
    return var_1d * math.sqrt(days)


# ---------------------------------------------------------------- drawdown y cartera
def drawdown(equity) -> pd.Series:
    """Caída relativa desde el máximo previo: E_t / max_{s≤t} E_s − 1 (≤ 0)."""
    e = pd.Series(equity, dtype=float)
    return e / e.cummax() - 1


def max_drawdown(equity) -> float:
    return float(drawdown(equity).min())


def portfolio_vol(weights, cov) -> float:
    w = np.asarray(weights, dtype=float)
    return float(np.sqrt(w @ np.asarray(cov) @ w))


def risk_contributions(weights, cov) -> np.ndarray:
    """Contribución de cada posición a la volatilidad: RC_i = w_i (Σw)_i / σ_p  (Σ RC_i = σ_p)."""
    w = np.asarray(weights, dtype=float)
    c = np.asarray(cov, dtype=float)
    return w * (c @ w) / portfolio_vol(w, c)


def inverse_vol_weights(vols) -> np.ndarray:
    """Pesos ∝ 1/σ_i normalizados a suma 1 (paridad de riesgo ingenua)."""
    inv = 1 / np.asarray(vols, dtype=float)
    return inv / inv.sum()
