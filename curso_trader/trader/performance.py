"""Métricas de rendimiento y de operaciones (curso §5)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, norm, skew


def _clean(r) -> np.ndarray:
    r = np.asarray(r, dtype=float)
    return r[~np.isnan(r)]


def cagr(returns, periods: int = 252) -> float:
    """Rentabilidad anual compuesta a partir de rentabilidades simples por periodo."""
    r = _clean(returns)
    growth = np.prod(1 + r)
    return float(growth ** (periods / len(r)) - 1)


def annual_vol(returns, periods: int = 252) -> float:
    return float(np.std(_clean(returns), ddof=1) * math.sqrt(periods))


def sharpe(returns, rf: float = 0.0, periods: int = 252) -> float:
    """Sharpe anualizado: √periods · media(r − rf/periods) / desv(r)."""
    r = _clean(returns) - rf / periods
    sd = np.std(r, ddof=1)
    return float(np.mean(r) / sd * math.sqrt(periods)) if sd > 0 else float("nan")


def sortino(returns, rf: float = 0.0, periods: int = 252) -> float:
    """Como Sharpe pero con la desviación a la baja √E[min(r,0)²]."""
    r = _clean(returns) - rf / periods
    dd = math.sqrt(np.mean(np.minimum(r, 0) ** 2))
    return float(np.mean(r) / dd * math.sqrt(periods)) if dd > 0 else float("nan")


def max_drawdown_from_returns(returns) -> float:
    eq = np.cumprod(1 + _clean(returns))
    return float(np.min(eq / np.maximum.accumulate(eq) - 1))


def calmar(returns, periods: int = 252) -> float:
    mdd = max_drawdown_from_returns(returns)
    return float(cagr(returns, periods) / abs(mdd)) if mdd < 0 else float("nan")


def probabilistic_sharpe(returns, sr_benchmark: float = 0.0) -> float:
    """PSR de Bailey y López de Prado (2012): P[SR verdadero > SR*] con SR por periodo.

    PSR = Φ( (ŜR − SR*)·√(n−1) / √(1 − γ₃ŜR + (γ₄−1)/4·ŜR²) ), γ₄ curtosis no en exceso.
    """
    r = _clean(returns)
    n = len(r)
    sr = np.mean(r) / np.std(r, ddof=1)
    g3 = skew(r)
    g4 = kurtosis(r, fisher=False)
    den = math.sqrt(max(1 - g3 * sr + (g4 - 1) / 4 * sr**2, 1e-12))
    return float(norm.cdf((sr - sr_benchmark) * math.sqrt(n - 1) / den))


def expected_max_sharpe(n_trials: int, sr_std: float = 1.0) -> float:
    """Máximo esperado de ``n_trials`` Sharpe nulos ~ N(0, sr_std²) (sesgo de selección, §5.4).

    Aproximación de Bailey et al.: σ·[(1−γ)Φ⁻¹(1−1/N) + γ Φ⁻¹(1−1/(N e))], γ = Euler–Mascheroni.
    """
    g = 0.5772156649
    n = n_trials
    return float(sr_std * ((1 - g) * norm.ppf(1 - 1 / n) + g * norm.ppf(1 - 1 / (n * math.e))))


def trade_stats(pnls) -> dict[str, float]:
    """Estadísticas por operación: acierto, payoff, profit factor, esperanza."""
    p = _clean(pnls)
    wins, losses = p[p > 0], p[p < 0]
    avg_w = wins.mean() if len(wins) else 0.0
    avg_l = -losses.mean() if len(losses) else 0.0
    return {
        "n": int(len(p)),
        "hit_rate": float(len(wins) / len(p)) if len(p) else float("nan"),
        "avg_win": float(avg_w),
        "avg_loss": float(avg_l),
        "payoff": float(avg_w / avg_l) if avg_l > 0 else float("inf"),
        "profit_factor": float(wins.sum() / -losses.sum()) if len(losses) else float("inf"),
        "expectancy": float(p.mean()) if len(p) else float("nan"),
    }


def summary(returns, periods: int = 252) -> pd.Series:
    r = _clean(returns)
    return pd.Series({
        "CAGR": cagr(r, periods),
        "Vol anual": annual_vol(r, periods),
        "Sharpe": sharpe(r, periods=periods),
        "Sortino": sortino(r, periods=periods),
        "Max DD": max_drawdown_from_returns(r),
        "Calmar": calmar(r, periods),
        "PSR(SR>0)": probabilistic_sharpe(r),
        "Asimetría": float(skew(r)),
        "Curtosis exc.": float(kurtosis(r)),
    })
