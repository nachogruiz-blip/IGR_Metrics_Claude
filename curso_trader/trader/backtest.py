"""Backtest vectorizado y estrategias de ejemplo (curso §5).

Convención anti look-ahead: la posición decidida con el cierre de t se aplica a la
rentabilidad de t → t+1, es decir ``pnl_t = pos_{t−1}·r_t − coste·|pos_t − pos_{t−1}|``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import indicators as ind


def backtest(close: pd.Series, position: pd.Series, cost_bps: float = 1.0) -> pd.DataFrame:
    """Devuelve ``ret`` (activo), ``pos``, ``strategy`` (neto) y ``equity`` (base 1)."""
    r = close.pct_change().fillna(0.0)
    pos = position.reindex(close.index).fillna(0.0)
    turnover = pos.diff().abs().fillna(pos.abs())
    strat = pos.shift(1).fillna(0.0) * r - cost_bps * 1e-4 * turnover
    return pd.DataFrame({"ret": r, "pos": pos, "strategy": strat, "equity": (1 + strat).cumprod()})


def sma_crossover(close: pd.Series, fast: int = 20, slow: int = 100, long_only: bool = False) -> pd.Series:
    """+1 si SMA rápida > lenta, −1 (o 0 si ``long_only``) en caso contrario."""
    f, s = ind.sma(close, fast), ind.sma(close, slow)
    pos = pd.Series(np.where(f > s, 1.0, 0.0 if long_only else -1.0), index=close.index)
    return pos.where(s.notna(), 0.0)


def donchian_breakout(ohlc: pd.DataFrame, entry: int = 55, exit: int = 20) -> pd.Series:
    """Sistema tortuga simplificado: entra al romper el máximo/mínimo de ``entry`` días, sale con ``exit``."""
    up_e = ohlc["high"].rolling(entry).max().shift(1)
    dn_e = ohlc["low"].rolling(entry).min().shift(1)
    up_x = ohlc["high"].rolling(exit).max().shift(1)
    dn_x = ohlc["low"].rolling(exit).min().shift(1)
    c = ohlc["close"]
    # Dos máquinas de estados independientes; son excluyentes porque romper el máximo de
    # ``entry`` días implica romper también el de ``exit`` días (y cerrar el corto).
    long_ev = pd.Series(np.nan, index=c.index)
    long_ev[c < dn_x] = 0.0
    long_ev[c > up_e] = 1.0
    short_ev = pd.Series(np.nan, index=c.index)
    short_ev[c > up_x] = 0.0
    short_ev[c < dn_e] = 1.0
    return long_ev.ffill().fillna(0.0) - short_ev.ffill().fillna(0.0)


def rsi_reversion(close: pd.Series, n: int = 2, low: float = 10, high: float = 90,
                  trend: int = 200) -> pd.Series:
    """Reversión a la media con RSI corto, sólo a favor de la tendencia (precio > SMA ``trend``)."""
    r = ind.rsi(close, n)
    up = close > ind.sma(close, trend)
    ev = pd.Series(np.nan, index=close.index)
    ev[(r < low) & up] = 1.0
    ev[r > high] = 0.0
    ev[~up] = 0.0
    return ev.ffill().fillna(0.0)


def vol_targeted(position: pd.Series, close: pd.Series, target: float = 0.10, n: int = 20,
                 max_leverage: float = 3.0) -> pd.Series:
    """Escala una señal ±1 para que la volatilidad ex ante sea ``target`` (anual)."""
    vol = ind.realized_vol(close, n)
    w = (target / vol).clip(upper=max_leverage)
    return (position * w).fillna(0.0)


def trades(close: pd.Series, position: pd.Series) -> pd.DataFrame:
    """Lista de operaciones (tramos de posición constante ≠ 0) con su rentabilidad."""
    pos = position.reindex(close.index).fillna(0.0)
    held = pos.shift(1).fillna(0.0)
    r = close.pct_change().fillna(0.0)
    block = (held != held.shift(1)).cumsum()
    df = pd.DataFrame({"held": held, "r": held * r, "block": block})
    df = df[df["held"] != 0]
    if df.empty:
        return pd.DataFrame(columns=["entry", "exit", "side", "days", "ret"])
    g = df.groupby("block")
    out = pd.DataFrame({
        "entry": g.apply(lambda x: x.index[0], include_groups=False),
        "exit": g.apply(lambda x: x.index[-1], include_groups=False),
        "side": g["held"].first(),
        "days": g.size(),
        "ret": g["r"].apply(lambda x: float(np.prod(1 + x) - 1)),
    })
    return out.reset_index(drop=True)


def walk_forward_splits(n: int, train: int, test: int) -> list[tuple[slice, slice]]:
    """Ventanas consecutivas (entrenamiento, prueba) sin solape hacia el futuro."""
    out = []
    start = 0
    while start + train + test <= n:
        out.append((slice(start, start + train), slice(start + train, start + train + test)))
        start += test
    return out
