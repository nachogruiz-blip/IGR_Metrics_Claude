"""Análisis técnico sobre OHLCV diario: medias, RSI, MACD, Bollinger, ATR, ADX, OBV, soportes y
resistencias, cruces de medias, momentum y fuerza relativa; pilar «Técnico».

Las definiciones de los indicadores (Wilder, Appel, Bollinger) son las mismas que en
``dashboard/stockdash/technical.py``; se replican para que este proyecto sea independiente.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .common import Item, Pillar, finite, piecewise, ramp


# --------------------------------------------------------------------------- indicadores
def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def _wilder(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """RSI de Wilder: 100 − 100/(1 + RS). Sin bajadas en la ventana = 100; sin movimiento = 50."""
    d = close.diff()
    gain, loss = _wilder(d.clip(lower=0.0), n), _wilder(-d.clip(upper=0.0), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = 100.0 - 100.0 / (1.0 + gain / loss)
    out = out.where(loss > 0, 100.0).where((gain > 0) | (loss > 0), 50.0)
    return out.where(gain.notna())


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": line, "macd_signal": sig, "macd_hist": line - sig})


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid = sma(close, n)
    sd = close.rolling(n, min_periods=n).std(ddof=0)
    up, lo = mid + k * sd, mid - k * sd
    return pd.DataFrame({"bb_mid": mid, "bb_up": up, "bb_lo": lo,
                         "pctb": (close - lo) / (up - lo).replace(0.0, np.nan)})


def true_range(df: pd.DataFrame) -> pd.Series:
    prev = df["Close"].shift(1)
    return pd.concat([df["High"] - df["Low"], (df["High"] - prev).abs(),
                      (df["Low"] - prev).abs()], axis=1).max(axis=1)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    return _wilder(true_range(df), n)


def adx(df: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    up, down = df["High"].diff(), -df["Low"].diff()
    pdm = up.where((up > down) & (up > 0), 0.0)
    mdm = down.where((down > up) & (down > 0), 0.0)
    tr = _wilder(true_range(df), n)
    pdi, mdi = 100 * _wilder(pdm, n) / tr, 100 * _wilder(mdm, n) / tr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0.0, np.nan)
    return pd.DataFrame({"adx": _wilder(dx, n), "plus_di": pdi, "minus_di": mdi})


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    return (np.sign(close.diff()).fillna(0.0) * volume).cumsum()


def indicator_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Serie completa de indicadores (para gráficos y para la foto actual)."""
    c = df["Close"]
    out = pd.DataFrame({"close": c})
    for n in (20, 50, 200):
        out[f"sma{n}"] = sma(c, n)
    out["rsi"] = rsi(c)
    out = out.join(macd(c)).join(bollinger(c)).join(adx(df))
    out["atr"] = atr(df)
    out["obv"] = obv(c, df["Volume"])
    return out


# --------------------------------------------------------------------------- niveles
def pivots(df: pd.DataFrame, window: int = 10) -> tuple[pd.Series, pd.Series]:
    """Máximos y mínimos locales: la vela es el extremo de ±``window`` sesiones."""
    w = 2 * window + 1
    hi = df["High"][df["High"] == df["High"].rolling(w, center=True, min_periods=w).max()]
    lo = df["Low"][df["Low"] == df["Low"].rolling(w, center=True, min_periods=w).min()]
    return hi, lo


def levels(df: pd.DataFrame, lookback: int = 252, window: int = 10,
           tol_atr: float = 1.0) -> list[tuple[float, int]]:
    """Zonas de soporte/resistencia: pivotes del último año agrupados si distan menos de
    ``tol_atr`` ATR. Devuelve (nivel medio, nº de toques), ordenado por nivel."""
    d = df.iloc[-lookback:]
    hi, lo = pivots(d, window)
    pts = np.sort(np.concatenate([hi.to_numpy(), lo.to_numpy()]))
    if pts.size == 0:
        return []
    tol = float(atr(df).iloc[-1]) * tol_atr
    groups, cur = [], [pts[0]]
    for p in pts[1:]:  # recorrido sobre unas decenas de pivotes ordenados
        if p - cur[-1] <= tol:
            cur.append(p)
        else:
            groups.append(cur)
            cur = [p]
    groups.append(cur)
    return [(float(np.mean(g)), len(g)) for g in groups]


def last_cross(fast: pd.Series, slow: pd.Series) -> tuple[str, pd.Timestamp | None]:
    """Último cruce de ``fast`` sobre ``slow``: («alcista»|«bajista»|«», fecha)."""
    diff = (fast - slow).dropna()
    sign = np.sign(diff)
    ch = sign.ne(sign.shift()) & sign.shift().notna()
    if not ch.any():
        return "", None
    t = ch[ch].index[-1]
    return ("alcista" if sign[t] > 0 else "bajista"), t


# --------------------------------------------------------------------------- foto y pilar
@dataclass
class Technical:
    frame: pd.DataFrame
    price: float
    atr: float
    support: float           # soporte más cercano por debajo (NaN si no hay)
    resistance: float        # resistencia más cercana por encima
    levels: list[tuple[float, int]]
    cross: str               # último cruce SMA50/SMA200
    cross_date: pd.Timestamp | None
    trend: str               # «alcista», «bajista», «lateral»
    pillar: Pillar
    flags: list[str] = field(default_factory=list)   # sobrecompra, extensión, etc.


def _ret(close: pd.Series, n: int, skip: int = 0) -> float:
    if len(close) <= n:
        return float("nan")
    return float(close.iloc[-1 - skip] / close.iloc[-1 - n] - 1)


def analyze(df: pd.DataFrame, bench: pd.Series | None = None) -> Technical:
    f = indicator_frame(df)
    last = f.iloc[-1]
    c = df["Close"]
    p, a = float(last["close"]), float(last["atr"])
    lv = levels(df)
    sup = max((x for x, _ in lv if x < p - 0.25 * a), default=float("nan"))
    res = min((x for x, _ in lv if x > p + 0.25 * a), default=float("nan"))
    cross, cdate = last_cross(f["sma50"], f["sma200"])

    above200 = p / last["sma200"] - 1 if finite(last["sma200"]) else float("nan")
    s50_200 = last["sma50"] / last["sma200"] - 1 if finite(last["sma200"]) else float("nan")
    slope200 = f["sma200"].iloc[-1] / f["sma200"].iloc[-21] - 1 if len(f) > 221 else float("nan")
    mom12_1 = _ret(c, 252, 21)
    mom3 = _ret(c, 63)
    rs = float("nan")
    if bench is not None and len(bench) > 130:
        b = bench.reindex(c.index).ffill()
        rs = _ret(c, 126) - _ret(b, 126)
    adx_v = float(last["adx"])
    vol_up = df["Volume"].where(c.diff() > 0).iloc[-50:].mean()
    vol_dn = df["Volume"].where(c.diff() < 0).iloc[-50:].mean()
    vol_ratio = vol_up / vol_dn if finite(vol_dn) and vol_dn > 0 else float("nan")
    hi52, lo52 = df["High"].iloc[-252:].max(), df["Low"].iloc[-252:].min()
    pos52 = (p - lo52) / (hi52 - lo52) if hi52 > lo52 else float("nan")

    if finite(above200) and finite(s50_200):
        if above200 > 0 and s50_200 > 0:
            trend = "alcista"
        elif above200 < 0 and s50_200 < 0:
            trend = "bajista"
        else:
            trend = "lateral"
    else:
        trend = "lateral"
    if finite(adx_v) and adx_v < 18 and trend != "lateral" and abs(above200) < 0.05:
        trend = "lateral"

    pil = Pillar("Técnico")
    pil.items += [
        Item("above_sma200", "Precio frente a la media de 200 sesiones", above200,
             ramp(above200, -0.15, 0.15), "pct", "Tendencia de fondo", 1.2),
        Item("sma50_vs_200", "Media 50 frente a media 200", s50_200, ramp(s50_200, -0.08, 0.08), "pct",
             f"Último cruce {cross} ({cdate:%d/%m/%Y})" if cdate is not None else "", 1.0),
        Item("sma200_slope", "Pendiente de la media 200 (1 mes)", slope200, ramp(slope200, -0.02, 0.02),
             "pct", "", 0.6),
        Item("mom12_1", "Momentum 12 meses (sin el último)", mom12_1, ramp(mom12_1, -0.25, 0.30), "pct",
             "Efecto momentum (Jegadeesh-Titman)", 1.0),
        Item("mom3", "Rentabilidad 3 meses", mom3, ramp(mom3, -0.15, 0.15), "pct", "", 0.6),
        Item("rel_strength", "Fuerza relativa 6 meses vs índice", rs, ramp(rs, -0.15, 0.15), "pct", "", 0.8),
        Item("macd_hist", "Histograma MACD (relativo al precio)", last["macd_hist"] / p,
             ramp(last["macd_hist"] / p, -0.006, 0.006), "pct", "> 0: impulso alcista a corto", 0.5),
        Item("rsi", "RSI(14)", last["rsi"],
             piecewise(last["rsi"], [20, 30, 45, 55, 70, 80], [0.3, 0.2, -0.3, 0.3, 0.2, -0.3]),
             "num", "> 70 sobrecompra; < 30 sobreventa (lectura de timing, no de tendencia)", 0.4),
        Item("volume_balance", "Volumen en subidas / en bajadas (50 s.)", vol_ratio,
             ramp(vol_ratio, 0.75, 1.3), "num", "> 1: acumulación", 0.4),
        Item("pos_52w", "Posición en el rango de 52 semanas", pos52, ramp(pos52, 0.1, 0.9), "pct0",
             "0 % = mínimo anual, 100 % = máximo", 0.4),
    ]
    flags: list[str] = []
    r, pb = float(last["rsi"]), float(last["pctb"])
    ext = (p - last["sma20"]) / a if finite(last["sma20"]) and a > 0 else float("nan")
    if finite(r) and r >= 70:
        flags.append(f"RSI en sobrecompra ({r:.0f})")
    if finite(r) and r <= 30:
        flags.append(f"RSI en sobreventa ({r:.0f})")
    if finite(pb) and pb > 1:
        flags.append("Precio por encima de la banda de Bollinger superior")
    if finite(pb) and pb < 0:
        flags.append("Precio por debajo de la banda de Bollinger inferior")
    if finite(ext) and ext > 2.5:
        flags.append(f"Muy extendido: {ext:.1f} ATR sobre la media de 20")
    if finite(ext) and ext < -2.5:
        flags.append(f"Muy castigado: {abs(ext):.1f} ATR bajo la media de 20")
    if cdate is not None and (df.index[-1] - cdate).days <= 30:
        flags.append(f"Cruce {'dorado' if cross == 'alcista' else 'de la muerte'} reciente "
                     f"({cdate:%d/%m/%Y})")
    if finite(adx_v):
        pil.notes.append(f"ADX {adx_v:.0f}: {'tendencia definida' if adx_v >= 25 else 'tendencia débil o rango' if adx_v < 20 else 'tendencia moderada'}.")
    return Technical(f, p, a, sup, res, lv, cross, cdate, trend, pil, flags)
