"""Carga de precios y generadores sintéticos (curso §2 y §13).

Todo el curso funciona sin red: los scripts usan ``--csv`` con datos propios o, por defecto,
datos sintéticos deterministas (semilla fija). ``download`` usa yfinance sólo si está instalado.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def load_prices(path: str | Path) -> pd.DataFrame:
    """Lee un CSV con columna de fecha (``date``/``Date``) y columnas de precio.

    Acepta OHLCV (``open, high, low, close, volume``) o una columna por activo.
    Los nombres se normalizan a minúsculas salvo los de activos (tickers).
    """
    df = pd.read_csv(path)
    date_col = next((c for c in df.columns if c.lower() in ("date", "fecha", "datetime")), df.columns[0])
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col).sort_index()
    df.index.name = "date"
    ohlc = {"open", "high", "low", "close", "adj close", "volume"}
    df.columns = [c.lower() if c.lower() in ohlc else c for c in df.columns]
    return df


def download(ticker: str, start: str = "2018-01-01") -> pd.DataFrame:  # pragma: no cover - red
    """Descarga OHLCV con yfinance (opcional, no es dependencia del curso)."""
    try:
        import yfinance as yf
    except ImportError as exc:
        raise ImportError("pip install yfinance para descargar datos reales") from exc
    df = yf.download(ticker, start=start, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    df.index.name = "date"
    return df


def synthetic_ohlc(n: int = 750, s0: float = 100.0, mu: float = 0.08, sigma: float = 0.20,
                   seed: int = 0, start: str = "2022-01-03", df_t: float = 4.0) -> pd.DataFrame:
    """OHLCV sintético: cierres con rentabilidades t-Student (colas gruesas) escaladas a ``sigma``.

    High/Low se construyen con un rango intradía proporcional a la volatilidad diaria.
    """
    rng = np.random.default_rng(seed)
    dt = 1 / TRADING_DAYS
    z = rng.standard_t(df_t, n) / np.sqrt(df_t / (df_t - 2))
    r = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * z
    close = s0 * np.exp(np.cumsum(r))
    prev = np.concatenate([[s0], close[:-1]])
    open_ = prev * np.exp(0.25 * sigma * np.sqrt(dt) * rng.standard_normal(n))
    span = np.abs(rng.normal(0, sigma * np.sqrt(dt), n)) * close
    high = np.maximum(open_, close) + span
    low = np.minimum(open_, close) - span
    volume = rng.lognormal(13, 0.3, n).round()
    idx = pd.bdate_range(start, periods=n, name="date")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=idx)


def synthetic_universe(tickers: list[str], n: int = 750, rho: float = 0.4, sigma: float = 0.25,
                       mu: float = 0.07, seed: int = 1, start: str = "2022-01-03") -> pd.DataFrame:
    """Cierres de varios activos con correlación constante ``rho`` (modelo de un factor)."""
    rng = np.random.default_rng(seed)
    k = len(tickers)
    dt = 1 / TRADING_DAYS
    market = rng.standard_normal((n, 1))
    idio = rng.standard_normal((n, k))
    z = np.sqrt(rho) * market + np.sqrt(1 - rho) * idio
    r = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * z
    prices = 100 * np.exp(np.cumsum(r, axis=0))
    return pd.DataFrame(prices, index=pd.bdate_range(start, periods=n, name="date"), columns=tickers)


def synthetic_pair(n: int = 750, beta: float = 1.3, half_life: float = 15.0, spread_vol: float = 0.01,
                   seed: int = 2) -> pd.DataFrame:
    """Par cointegrado: log y = beta·log x + s, con s un AR(1) de vida media ``half_life`` días."""
    rng = np.random.default_rng(seed)
    phi = 0.5 ** (1 / half_life)
    lx = np.log(50) + np.cumsum(0.015 * rng.standard_normal(n))
    eps = spread_vol * rng.standard_normal(n)
    s = np.zeros(n)
    for t in range(1, n):  # recursión AR(1): una sola serie, no trayectorias
        s[t] = phi * s[t - 1] + eps[t]
    ly = 0.5 + beta * lx + s
    idx = pd.bdate_range("2022-01-03", periods=n, name="date")
    return pd.DataFrame({"x": np.exp(lx), "y": np.exp(ly)}, index=idx)
