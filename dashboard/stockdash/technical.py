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
def features(df: pd.DataFrame, bench_close: pd.Series | None = None) -> pd.DataFrame:
    """Todas las variables de ``snapshot`` como series temporales (una fila por sesión).

    Cada fila usa **sólo información hasta esa fecha** (ventanas móviles y suavizados causales),
    así que el backtest puede leer la fila *t* sin sesgo de anticipación; ``tests`` lo verifica
    comparando con ``snapshot`` sobre el histórico truncado.
    """
    df = df.dropna(subset=["Close"])
    c = df["Close"]
    ind = indicator_frame(df)
    f = pd.DataFrame(index=df.index)
    f["price"] = c
    for name, n in (("chg_1d", 1), ("ret_1m", 21), ("ret_3m", 63), ("ret_6m", 126),
                    ("ret_12m", 252)):
        f[name] = c / c.shift(n) - 1.0
    f["mom_12_1"] = c.shift(21) / c.shift(252) - 1.0
    f["sma50"], f["sma200"] = ind["sma50"], ind["sma200"]
    f["dist_sma50"] = c / ind["sma50"] - 1.0
    f["dist_sma200"] = c / ind["sma200"] - 1.0
    f["sma50_vs_200"] = ind["sma50"] / ind["sma200"] - 1.0
    f["sma50_slope"] = ind["sma50"] / ind["sma50"].shift(21) - 1.0
    f["rsi"] = ind["rsi"]
    f["macd"], f["macd_signal"] = ind["macd"], ind["signal"]
    f["macd_hist_pct"] = 100.0 * ind["hist"] / c
    f["bb_pctb"] = ind["pctb"]
    f["adx"], f["plus_di"], f["minus_di"] = ind["adx"], ind["plus_di"], ind["minus_di"]
    f["di_balance"] = ((ind["plus_di"] - ind["minus_di"])
                       / (ind["plus_di"] + ind["minus_di"]).replace(0.0, np.nan))
    f["atr"] = ind["atr"]
    f["atr_pct"] = ind["atr"] / c
    f["vol_63"] = ind["vol63"]
    f["vol_252"] = realized_vol(c, TRADING_DAYS)
    f["vol_ratio"] = f["vol_63"] / f["vol_252"]
    f["high_52w"] = df["High"].rolling(TRADING_DAYS, min_periods=1).max()
    f["low_52w"] = df["Low"].rolling(TRADING_DAYS, min_periods=1).min()
    f["dd_52w"] = c / f["high_52w"] - 1.0
    avg_vol = df["Volume"].rolling(21, min_periods=21).mean()
    f["obv_slope"] = (ind["obv"] - ind["obv"].shift(21)) / (21 * avg_vol.replace(0.0, np.nan))
    f["volume_ratio"] = (df["Volume"].rolling(20, min_periods=1).mean()
                         / df["Volume"].rolling(100, min_periods=1).mean())
    f["rel_strength_3m"] = np.nan
    if bench_close is not None:
        b = bench_close.dropna().reindex(c.index).ffill()
        f["rel_strength_3m"] = f["ret_3m"] - (b / b.shift(63) - 1.0)
    return f


def snapshot(df: pd.DataFrame, bench_close: pd.Series | None = None) -> dict[str, float]:
    """Valores actuales (última sesión) de todos los indicadores técnicos que alimentan la
    puntuación. ``bench_close`` (opcional) es el cierre del índice de referencia para la fuerza
    relativa."""
    row = features(df, bench_close).iloc[-1]
    return {k: float(v) for k, v in row.items()}
