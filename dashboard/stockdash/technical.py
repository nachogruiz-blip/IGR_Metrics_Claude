"""Indicadores técnicos sobre series OHLCV diarias.

Todas las funciones son vectoriales (pandas/numpy) y devuelven series alineadas con la entrada;
los primeros valores son NaN mientras no hay ventana suficiente.

Convención de entrada: ``DataFrame`` con columnas ``Open, High, Low, Close, Volume`` e índice de
fechas ordenado ascendentemente (precios ajustados por dividendos y splits).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


# --------------------------------------------------------------------------- medias y osciladores
def sma(s: pd.Series, n: int) -> pd.Series:
    """Media móvil simple de ``n`` sesiones."""
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    """Media móvil exponencial con ``span = n`` (α = 2/(n+1))."""
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def _wilder(s: pd.Series, n: int) -> pd.Series:
    """Suavizado de Wilder (EMA con α = 1/n)."""
    return s.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """RSI de Wilder: 100 − 100/(1 + RS), RS = media de subidas / media de bajadas.

    Si no hay bajadas en la ventana el RSI vale 100; si no hay movimiento, 50.
    """
    delta = close.diff()
    gain = _wilder(delta.clip(lower=0.0), n)
    loss = _wilder(-delta.clip(upper=0.0), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = 100.0 - 100.0 / (1.0 + gain / loss)
    out = out.where(loss > 0, 100.0)
    out = out.where((gain > 0) | (loss > 0), 50.0)
    return out.where(gain.notna())


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD = EMA_fast − EMA_slow, señal = EMA_signal(MACD), histograma = MACD − señal."""
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": line, "signal": sig, "hist": line - sig})


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    """Bandas de Bollinger (media ± k·σ) y %B = (P − inferior)/(superior − inferior)."""
    mid = sma(close, n)
    sd = close.rolling(n, min_periods=n).std(ddof=0)
    upper, lower = mid + k * sd, mid - k * sd
    width = upper - lower
    pctb = (close - lower) / width.replace(0.0, np.nan)
    return pd.DataFrame({"mid": mid, "upper": upper, "lower": lower, "pctb": pctb,
                         "bandwidth": width / mid})


def true_range(df: pd.DataFrame) -> pd.Series:
    prev = df["Close"].shift(1)
    return pd.concat([df["High"] - df["Low"], (df["High"] - prev).abs(),
                      (df["Low"] - prev).abs()], axis=1).max(axis=1)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Average True Range de Wilder."""
    return _wilder(true_range(df), n)


def adx(df: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    """ADX de Wilder con +DI y −DI. ADX < 20 ≈ mercado sin tendencia (lateral)."""
    up = df["High"].diff()
    down = -df["Low"].diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    tr = _wilder(true_range(df), n)
    pdi = 100 * _wilder(plus_dm, n) / tr
    mdi = 100 * _wilder(minus_dm, n) / tr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0.0, np.nan)
    return pd.DataFrame({"adx": _wilder(dx.fillna(0.0), n).where(dx.notna().cumsum() >= n),
                         "plus_di": pdi, "minus_di": mdi})


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume: suma acumulada de ±volumen según el signo del cambio de precio."""
    return (np.sign(close.diff()).fillna(0.0) * volume).cumsum()


def realized_vol(close: pd.Series, n: int) -> pd.Series:
    """Volatilidad realizada anualizada de los log-rendimientos en ventana ``n``."""
    return np.log(close).diff().rolling(n, min_periods=n).std() * np.sqrt(TRADING_DAYS)


# --------------------------------------------------------------------------- marco para gráficos
def indicator_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Serie temporal completa de indicadores (para los gráficos de la ficha)."""
    c = df["Close"]
    out = pd.DataFrame(index=df.index)
    out["close"] = c
    for n in (20, 50, 200):
        out[f"sma{n}"] = sma(c, n)
    out["rsi"] = rsi(c)
    out = out.join(macd(c)).join(bollinger(c)).join(adx(df))
    out["atr"] = atr(df)
    out["obv"] = obv(c, df["Volume"])
    out["vol63"] = realized_vol(c, 63)
    return out


# --------------------------------------------------------------------------- foto actual
def _ret(c: pd.Series, n: int) -> float:
    return float(c.iloc[-1] / c.iloc[-1 - n] - 1.0) if len(c) > n else np.nan


def _last(s: pd.Series) -> float:
    return float(s.iloc[-1]) if len(s) and pd.notna(s.iloc[-1]) else np.nan


def snapshot(df: pd.DataFrame, bench_close: pd.Series | None = None) -> dict[str, float]:
    """Valores actuales de todos los indicadores técnicos que alimentan la puntuación.

    ``bench_close`` (opcional) es el cierre del índice de referencia para la fuerza relativa.
    """
    df = df.dropna(subset=["Close"])
    c = df["Close"]
    ind = indicator_frame(df)
    price = float(c.iloc[-1])
    s50, s200 = _last(ind["sma50"]), _last(ind["sma200"])
    s50_prev = float(ind["sma50"].iloc[-22]) if len(ind) > 22 else np.nan

    window = df.iloc[-TRADING_DAYS:]
    hi52, lo52 = float(window["High"].max()), float(window["Low"].min())
    vol63, vol252 = _last(ind["vol63"]), _last(realized_vol(c, TRADING_DAYS))

    o = ind["obv"]
    avg_vol = float(df["Volume"].iloc[-21:].mean()) if len(df) > 21 else np.nan
    obv_slope = (float(o.iloc[-1] - o.iloc[-22]) / (21 * avg_vol)
                 if len(o) > 22 and avg_vol > 0 else np.nan)
    v20, v100 = df["Volume"].iloc[-20:].mean(), df["Volume"].iloc[-100:].mean()

    ret_3m = _ret(c, 63)
    rel = np.nan
    if bench_close is not None:
        b = bench_close.dropna().reindex(c.index).ffill()
        if b.notna().sum() > 64:
            rel = ret_3m - _ret(b, 63)

    pdi, mdi = _last(ind["plus_di"]), _last(ind["minus_di"])
    return {
        "price": price,
        "chg_1d": _ret(c, 1),
        "ret_1m": _ret(c, 21),
        "ret_3m": ret_3m,
        "ret_6m": _ret(c, 126),
        "ret_12m": _ret(c, 252),
        "mom_12_1": (float(c.iloc[-22] / c.iloc[-253] - 1.0) if len(c) > 253 else np.nan),
        "sma50": s50,
        "sma200": s200,
        "dist_sma50": price / s50 - 1.0,
        "dist_sma200": price / s200 - 1.0,
        "sma50_vs_200": s50 / s200 - 1.0,
        "sma50_slope": s50 / s50_prev - 1.0,
        "rsi": _last(ind["rsi"]),
        "macd": _last(ind["macd"]),
        "macd_signal": _last(ind["signal"]),
        "macd_hist_pct": 100.0 * _last(ind["hist"]) / price,
        "bb_pctb": _last(ind["pctb"]),
        "adx": _last(ind["adx"]),
        "plus_di": pdi,
        "minus_di": mdi,
        "di_balance": (pdi - mdi) / (pdi + mdi) if (pdi + mdi) > 0 else np.nan,
        "atr": _last(ind["atr"]),
        "atr_pct": _last(ind["atr"]) / price,
        "vol_63": vol63,
        "vol_252": vol252,
        "vol_ratio": vol63 / vol252 if vol252 > 0 else np.nan,
        "high_52w": hi52,
        "low_52w": lo52,
        "dd_52w": price / hi52 - 1.0,
        "rel_strength_3m": rel,
        "obv_slope": obv_slope,
        "volume_ratio": float(v20 / v100) if v100 > 0 else np.nan,
    }
