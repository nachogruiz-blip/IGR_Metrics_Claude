"""Renta variable (curso §7): beta, factores, momentum, gaps y pares."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def ols(y, X, add_const: bool = True) -> dict[str, np.ndarray]:
    """MCO con errores estándar clásicos. Devuelve coef, se, t y R²."""
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    if add_const:
        X = np.column_stack([np.ones(len(X)), X])
    mask = ~(np.isnan(y) | np.isnan(X).any(axis=1))
    y, X = y[mask], X[mask]
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    dof = len(y) - X.shape[1]
    s2 = resid @ resid / dof
    se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
    r2 = 1 - resid @ resid / np.sum((y - y.mean()) ** 2)
    return {"coef": coef, "se": se, "t": coef / se, "r2": float(r2), "resid": resid}


def beta(asset_ret, market_ret) -> float:
    """β = Cov(r_i, r_m)/Var(r_m)."""
    a = pd.concat([pd.Series(np.asarray(asset_ret, float)), pd.Series(np.asarray(market_ret, float))], axis=1).dropna()
    c = np.cov(a.iloc[:, 0], a.iloc[:, 1], ddof=1)
    return float(c[0, 1] / c[1, 1])


def capm(asset_ret, market_ret, rf: float = 0.0, periods: int = 252) -> dict[str, float]:
    """Regresión r_i − r_f = α + β(r_m − r_f) + ε. α anualizado (aritmético)."""
    d = rf / periods
    res = ols(np.asarray(asset_ret) - d, np.asarray(market_ret) - d)
    return {"alpha_annual": float(res["coef"][0] * periods), "beta": float(res["coef"][1]),
            "t_alpha": float(res["t"][0]), "r2": res["r2"]}


def factor_regression(returns: pd.Series, factors: pd.DataFrame) -> pd.DataFrame:
    """Exposición a factores (mercado, tamaño, valor, momentum...) con estadísticos t."""
    df = pd.concat([returns.rename("_y"), factors], axis=1).dropna()
    res = ols(df["_y"], df[factors.columns])
    return pd.DataFrame({"coef": res["coef"], "t": res["t"]}, index=["alpha", *factors.columns])


def momentum_12_1(prices: pd.DataFrame, lookback: int = 252, skip: int = 21) -> pd.Series:
    """Momentum 12-1: rentabilidad de t−lookback a t−skip (omite el último mes), último dato."""
    m = prices.shift(skip) / prices.shift(lookback) - 1
    return m.iloc[-1].sort_values(ascending=False)


def gap_stats(ohlc: pd.DataFrame, threshold: float = 0.01) -> dict[str, float]:
    """Gaps de apertura |O_t/C_{t−1} − 1| > umbral y proporción que se «cierran» en la sesión."""
    pc = ohlc["close"].shift(1)
    gap = ohlc["open"] / pc - 1
    up = gap > threshold
    dn = gap < -threshold
    filled = (up & (ohlc["low"] <= pc)) | (dn & (ohlc["high"] >= pc))
    n = int((up | dn).sum())
    return {"n_gaps": n, "gap_up": int(up.sum()), "gap_down": int(dn.sum()),
            "fill_rate": float(filled.sum() / n) if n else float("nan")}


# ---------------------------------------------------------------- pares
def hedge_ratio(y, x, log: bool = True) -> float:
    """β de la regresión y = a + β x (en logaritmos por defecto)."""
    y, x = np.asarray(y, float), np.asarray(x, float)
    if log:
        y, x = np.log(y), np.log(x)
    return float(ols(y, x)["coef"][1])


def spread(y: pd.Series, x: pd.Series, beta_: float | None = None) -> pd.Series:
    b = hedge_ratio(y, x) if beta_ is None else beta_
    return np.log(y) - b * np.log(x)


def half_life(s) -> float:
    """Vida media de reversión de un AR(1): Δs_t = a + b·s_{t−1} ⇒ HL = −ln 2 / ln(1+b)."""
    s = np.asarray(s, float)
    b = ols(np.diff(s), s[:-1])["coef"][1]
    return float(-math.log(2) / math.log1p(b)) if b < 0 else float("inf")


def adf_tstat(s) -> float:
    """Estadístico t de Dickey–Fuller (con constante, sin retardos). Crítico 5 % ≈ −2,86.

    Si se aplica a residuos de una regresión estimada (Engle–Granger), el crítico 5 % ≈ −3,34.
    """
    s = np.asarray(s, float)
    return float(ols(np.diff(s), s[:-1])["t"][1])


def rolling_zscore(s: pd.Series, n: int = 60) -> pd.Series:
    return (s - s.rolling(n).mean()) / s.rolling(n).std()


def pair_positions(z: pd.Series, entry: float = 2.0, exit: float = 0.5) -> pd.Series:
    """Posición en el spread: −1 si z > entry, +1 si z < −entry, 0 al volver a |z| < exit."""
    ev = pd.Series(np.nan, index=z.index)
    ev[z.abs() < exit] = 0.0
    ev[z > entry] = -1.0
    ev[z < -entry] = 1.0
    return ev.ffill().fillna(0.0)


def dollar_neutral_shares(capital: float, price_y: float, price_x: float, beta_: float) -> tuple[int, int]:
    """Acciones de y (largo) y x (corto) con nocional de x = β·nocional de y."""
    ny = math.floor(capital / (price_y * (1 + abs(beta_))))
    nx = round(beta_ * ny * price_y / price_x)
    return ny, nx
