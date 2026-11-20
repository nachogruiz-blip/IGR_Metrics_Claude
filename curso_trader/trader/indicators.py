"""Indicadores técnicos (curso §3). Entradas: ``pd.Series``/``DataFrame`` OHLC en minúsculas."""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(x: pd.Series, n: int) -> pd.Series:
    return x.rolling(n).mean()


def ema(x: pd.Series, n: int) -> pd.Series:
    """Media exponencial con α = 2/(n+1)."""
    return x.ewm(span=n, adjust=False).mean()


def _wilder(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """RSI de Wilder: 100 − 100/(1+RS), RS = media(subidas)/media(bajadas), en [0, 100]."""
    d = close.diff()
    up = _wilder(d.clip(lower=0), n)
    down = _wilder(-d.clip(upper=0), n)
    rs = up / down
    out = 100 - 100 / (1 + rs)
    return out.where(down > 0, 100.0).where(up.notna())


def true_range(ohlc: pd.DataFrame) -> pd.Series:
    """TR_t = max(H−L, |H−C_{t−1}|, |L−C_{t−1}|)."""
    pc = ohlc["close"].shift(1)
    tr = pd.concat([ohlc["high"] - ohlc["low"], (ohlc["high"] - pc).abs(), (ohlc["low"] - pc).abs()], axis=1)
    return tr.max(axis=1)


def atr(ohlc: pd.DataFrame, n: int = 14) -> pd.Series:
    """Average True Range (suavizado de Wilder)."""
    return _wilder(true_range(ohlc), n)


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    m = sma(close, n)
    s = close.rolling(n).std(ddof=0)
    return pd.DataFrame({"mid": m, "upper": m + k * s, "lower": m - k * s, "pct_b": (close - (m - k * s)) / (2 * k * s)})


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def donchian(ohlc: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """Canal de Donchian de las ``n`` sesiones *anteriores* (sin mirar el día actual)."""
    return pd.DataFrame({"upper": ohlc["high"].rolling(n).max().shift(1),
                         "lower": ohlc["low"].rolling(n).min().shift(1)})


def zscore(x: pd.Series, n: int) -> pd.Series:
    return (x - x.rolling(n).mean()) / x.rolling(n).std()


def realized_vol(close: pd.Series, n: int = 20, periods: int = 252) -> pd.Series:
    """Volatilidad anualizada de rentabilidades logarítmicas en ventana ``n``."""
    return np.log(close).diff().rolling(n).std() * np.sqrt(periods)


def pivot_points(high: float, low: float, close: float) -> dict[str, float]:
    """Pivotes clásicos (floor trader) a partir del H/L/C de la sesión anterior."""
    p = (high + low + close) / 3
    return {"R3": high + 2 * (p - low), "R2": p + (high - low), "R1": 2 * p - low, "P": p,
            "S1": 2 * p - high, "S2": p - (high - low), "S3": low - 2 * (high - p)}
