"""Factores macro para activos sin estados financieros (oro y otras materias primas, divisas).

Sustituye a los pilares de balance, rentabilidad y valoración por un pilar «Factores macro»:

1. **Sensibilidad a cada factor** (dólar, tipos a 10 años, bonos ligados a la inflación,
   S&P 500, VIX): regresión de los log-rendimientos **semanales** del activo sobre la variación
   del factor en los últimos 2 años,

       r_activo = a + β·Δfactor + e,

   con Δfactor = log-rendimiento (``price``), variación en puntos del rendimiento (``yield``,
   ^TNX cotiza en %) o log-variación del nivel (``level``, VIX).
2. **Viento a favor o en contra**: efecto implícito = β × movimiento del factor en las últimas
   13 semanas. Es la parte de la evolución reciente del activo que «explica» ese factor; si el
   factor sigue moviéndose en esa dirección, empuja en ese sentido. Puntúa con
   ``ramp(efecto, −4 %, +4 %)`` y pesa min(|ρ|/0.4, 1) (un factor que apenas explica nada
   apenas cuenta; con |ρ| ≥ 0.4 pesa lo mismo que la extensión del precio, 0.7… ver pesos).
3. **Valor relativo**: extensión del precio frente a su media de 3 años (z de log-precio) y, en
   el oro, ratio oro/plata en percentil de su historia (ratio alto = oro caro frente a plata).

Si la relación estimada tiene el signo contrario al esperado por la teoría (p. ej. oro sube con
el dólar) con |ρ| > 0.15 se avisa de una «relación inusual»: el régimen puede haber cambiado.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .common import Item, Pillar, finite, ramp

WEEKS_FIT = 104          # ventana de estimación (2 años de semanas)
WEEKS_MOVE = 13          # movimiento reciente del factor (≈ 3 meses)
IMPLIED_SPAN = 0.04      # efecto implícito que puntúa ±1
ROLL_WEEKS = 26          # correlación móvil (gráfico)
FULL_WEIGHT_CORR = 0.4   # |ρ| a partir de la cual un factor pesa 1 (por debajo, proporcional)


def weekly(s: pd.Series) -> pd.Series:
    return s.resample("W-FRI").last().dropna()


def factor_change(s: pd.Series, kind: str) -> pd.Series:
    """Variación del factor según su tipo (ver docstring del módulo)."""
    if kind == "yield":
        return s.diff()
    return np.log(s).diff()


@dataclass
class DriverStat:
    name: str
    ticker_kind: str
    expected_sign: int
    move: float          # movimiento del factor en 13 semanas (fracción, o pp si es rendimiento)
    beta: float
    corr: float
    implied: float       # β × movimiento: efecto implícito sobre el activo
    unusual: bool        # signo de la relación contrario al esperado


@dataclass
class Macro:
    drivers: list[DriverStat]
    rebased: pd.DataFrame               # activo y factores en base 100 (último año)
    rolling_corr: pd.DataFrame          # correlación móvil 26 semanas activo-factor
    relative: dict[str, float]
    pillar: Pillar
    notes: list[str] = field(default_factory=list)


def regress(y: pd.Series, x: pd.Series) -> tuple[float, float]:
    """(β, ρ) de la regresión MCO de ``y`` sobre ``x`` (series alineadas, sin NaN)."""
    d = pd.concat([y, x], axis=1).dropna()
    if len(d) < 20 or d.iloc[:, 1].var() == 0:
        return float("nan"), float("nan")
    c = np.cov(d.iloc[:, 0], d.iloc[:, 1])
    return float(c[0, 1] / c[1, 1]), float(c[0, 1] / np.sqrt(c[0, 0] * c[1, 1]))


def analyze(close: pd.Series, drivers: dict[str, pd.Series],
            spec: dict[str, tuple[str, str, int]], is_gold: bool = False) -> Macro:
    """Pilar «Factores macro». ``spec`` = ``data.MACRO_DRIVERS[...]`` (ticker, tipo, signo)."""
    wa = weekly(close)
    ra = np.log(wa).diff()
    pil = Pillar("Factores macro")
    stats: list[DriverStat] = []
    corr_roll = {}
    notes: list[str] = []
    for name, series in drivers.items():
        if name not in spec:
            continue
        _, kind, sign = spec[name]
        if kind == "ratio":
            continue
        wf = weekly(series).reindex(wa.index).ffill()
        dx = factor_change(wf, kind)
        beta, corr = regress(ra.iloc[-WEEKS_FIT:], dx.iloc[-WEEKS_FIT:])
        if kind == "yield":
            move = float(wf.iloc[-1] - wf.iloc[-1 - WEEKS_MOVE])
        else:
            move = float(np.log(wf.iloc[-1] / wf.iloc[-1 - WEEKS_MOVE]))
        implied = beta * move if finite(beta) else float("nan")
        unusual = bool(sign != 0 and finite(beta) and np.sign(beta) != sign and abs(corr) > 0.15)
        stats.append(DriverStat(name, kind, sign, move, beta, corr, implied, unusual))
        corr_roll[name] = ra.rolling(ROLL_WEEKS).corr(dx)
        move_txt = f"{move:+.2f} pp" if kind == "yield" else f"{move:+.1%}"
        beta_txt = (f"β {beta:+.3f} por pp" if kind == "yield" else f"β {beta:+.2f}") if finite(beta) else "β —"
        pil.items.append(Item(
            f"driver_{len(stats)}", f"{name}: efecto de los últimos 3 meses", implied,
            ramp(implied, -IMPLIED_SPAN, IMPLIED_SPAN), "pct",
            f"Factor {move_txt} en 13 semanas; {beta_txt}, ρ {corr:+.2f}" +
            (" — relación inusual" if unusual else ""),
            float(min(abs(corr) / FULL_WEIGHT_CORR, 1.0)) if finite(corr) else 0.0))
        if unusual:
            notes.append(f"Relación inusual con «{name}»: la teoría espera signo "
                         f"{'positivo' if sign > 0 else 'negativo'} y en los 2 últimos años ha sido "
                         f"{'positivo' if beta > 0 else 'negativo'} (ρ {corr:+.2f}). El régimen "
                         "puede haber cambiado; no extrapolar.")

    # ------------------------------------------------------------ valor relativo
    relative: dict[str, float] = {}
    lp = np.log(close)
    win = lp.iloc[-756:]
    z = float((lp.iloc[-1] - win.mean()) / win.std()) if len(win) > 250 and win.std() > 0 else float("nan")
    relative["z_3y"] = z
    pil.items.append(Item("extension_3y", "Extensión frente a la media de 3 años (z del log-precio)",
                          z, ramp(z, 2.0, -1.0), "num",
                          "> 2: muy por encima de su media (riesgo de corrección); < 0: por debajo",
                          0.7))
    if is_gold:
        silver = next((drivers[n] for n, (_, k, _) in spec.items() if k == "ratio" and n in drivers), None)
        if silver is not None:
            ratio = (close / silver.reindex(close.index).ffill()).dropna()
            if len(ratio) > 250:
                pct = float((ratio <= ratio.iloc[-1]).mean())
                relative["gold_silver"] = float(ratio.iloc[-1])
                relative["gold_silver_pct"] = pct
                pil.items.append(Item("gold_silver", "Ratio oro/plata (percentil histórico)", pct,
                                      ramp(pct, 0.9, 0.1), "pct0",
                                      f"Ratio actual {ratio.iloc[-1]:.0f}; alto = oro caro frente a plata",
                                      0.5))
    spx = drivers.get("S&P 500")
    if spx is not None:
        r = (close / spx.reindex(close.index).ffill()).dropna()
        if len(r) > 250:
            relative["vs_spx_pct"] = float((r <= r.iloc[-1]).mean())

    # ------------------------------------------------------------ gráficos
    # Base 100 sólo para series de precio (rendimientos y VIX no son comparables así).
    frame = pd.concat({"Activo": close, **{n: s for n, s in drivers.items()
                                           if n in spec and spec[n][1] in ("price", "ratio")}}, axis=1)
    frame = frame.ffill().iloc[-252:].dropna(axis=1, how="all")
    rebased = frame / frame.bfill().iloc[0] * 100
    rolling = pd.DataFrame(corr_roll).dropna(how="all")

    tail = sorted((d for d in stats if finite(d.implied)), key=lambda d: -abs(d.implied) * abs(d.corr))
    if tail:
        d = tail[0]
        notes.insert(0, f"Factor dominante reciente: «{d.name}» (efecto implícito {d.implied:+.1%} "
                        f"en 3 meses, ρ {d.corr:+.2f}).")
    return Macro(stats, rebased, rolling, relative, pil, notes)
