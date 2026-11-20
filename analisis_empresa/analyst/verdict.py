"""Veredicto: ¿comprar, vender o esperar? Combina los pilares en dos ejes y aplica reglas de
*timing* y de veto.

Ejes (puntuaciones en [−1, 1]):
- **Atractivo fundamental** A = media ponderada de calidad (balance y rentabilidad) y
  valoración: ¿es una buena empresa a buen precio? Horizonte de años.
- **Momento técnico** T = pilar técnico: ¿acompaña el precio? Horizonte de semanas-meses.
- **Riesgo** R = pilar de series temporales: modula la convicción y el tamaño, no la dirección.

Matriz de decisión (umbrales en ``A_BUY``, ``A_SELL``, ``T_UP``, ``T_DOWN``):

| A \\ T            | T ≥ T_UP     | intermedio          | T ≤ T_DOWN                     |
|-------------------|--------------|---------------------|--------------------------------|
| A ≥ A_BUY         | COMPRAR      | COMPRAR (escalonado)| ESPERAR (a confirmación técnica)|
| intermedio        | COMPRAR táct.| MANTENER            | VENDER (táctico)               |
| A ≤ A_SELL        | VENDER (aprovechar fortaleza) | VENDER | VENDER                    |

Superposiciones: insolvencia (Altman < 1.81, cobertura < 1.5×, deuda neta/EBITDA > 4.5×) veta la
compra; sobrecompra/extensión convierte COMPRAR en ESPERAR (a un retroceso); resultados en menos
de ``EARNINGS_DAYS`` días convierte COMPRAR en ESPERAR (a los resultados); volatilidad en máximos
rebaja la convicción.

Activos sin estados financieros (oro, materias primas, divisas): se pasa ``macro`` (pilar
«Factores macro», ver ``macro.py``) y el atractivo de fondo es A = puntuación macro; calidad y
valoración quedan sin dato y las reglas de solvencia y resultados no aplican.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .common import Pillar, finite, fmt, weighted

A_BUY, A_SELL = 0.25, -0.25
T_UP, T_DOWN = 0.15, -0.25
T_TACTICAL = 0.40
EARNINGS_DAYS = 14
QUALITY_WEIGHTS = {"Balance y solvencia": 0.45, "Rentabilidad y crecimiento": 0.55}
FUNDAMENTAL_WEIGHTS = {"calidad": 0.5, "valoración": 0.5}
COMPOSITE_WEIGHTS = {"calidad": 0.30, "valoración": 0.30, "técnico": 0.30, "riesgo": 0.10}
MACRO_COMPOSITE_WEIGHTS = {"macro": 0.40, "técnico": 0.45, "riesgo": 0.15}


@dataclass
class Verdict:
    action: str                 # COMPRAR | ESPERAR | MANTENER | VENDER
    bias: str                   # intención de fondo: «compra», «venta» o «neutral»
    headline: str
    conviction: str             # alta | media | baja
    quality: float
    valuation: float
    fundamental: float          # A
    timing: float               # T
    risk: float                 # R
    composite: float
    reasons_for: list[str] = field(default_factory=list)
    reasons_against: list[str] = field(default_factory=list)
    wait_for: list[str] = field(default_factory=list)     # disparadores / condiciones
    warnings: list[str] = field(default_factory=list)
    levels: dict[str, float] = field(default_factory=dict)


def _top(pillars: list[Pillar], positive: bool, k: int = 5) -> list[str]:
    items = [(i, p.name) for p in pillars for i in p.items if finite(i.score) and i.weight > 0]
    items = [(i, n) for i, n in items if (i.score > 0.25 if positive else i.score < -0.25)]
    items.sort(key=lambda x: -abs(x[0].score) * x[0].weight)
    return [f"{i.label}: {i.shown}" for i, _ in items[:k]]


def _conviction(a: float, t: float, agree: bool) -> str:
    m = np.nanmean([abs(a), abs(t)]) if agree else abs(a) * 0.5
    return "alta" if m >= 0.5 else "media" if m >= 0.28 else "baja"


def decide(balance: Pillar, profitability: Pillar, valuation: Pillar, technical: Pillar,
           risk: Pillar, *, price: float, atr: float, sma20: float, sma50: float,
           support: float, resistance: float, flags: list[str], fair_value: float,
           analyst_target: float, vol_pct: float, vol_trend: float,
           asof: pd.Timestamp, earnings_date: pd.Timestamp | None,
           ex_dividend_date: pd.Timestamp | None = None, macro: Pillar | None = None) -> Verdict:
    t, r = technical.score, risk.score
    if macro is None:
        q = weighted({k: p.score for k, p in (("Balance y solvencia", balance),
                                              ("Rentabilidad y crecimiento", profitability))},
                     QUALITY_WEIGHTS)
        v = valuation.score
        a = weighted({"calidad": q, "valoración": v}, FUNDAMENTAL_WEIGHTS)
        comp = weighted({"calidad": q, "valoración": v, "técnico": t, "riesgo": r}, COMPOSITE_WEIGHTS)
        F, good = "Fundamentales", "Buena empresa, precio razonable y tendencia a favor."
        pos, neg = "atractivos", "débiles"
    else:
        q = v = float("nan")
        a = macro.score
        comp = weighted({"macro": a, "técnico": t, "riesgo": r}, MACRO_COMPOSITE_WEIGHTS)
        F, good = "Factores macro", "Factores macro a favor y tendencia alcista."
        pos, neg = "a favor", "en contra"
    a = a if finite(a) else 0.0
    t = t if finite(t) else 0.0

    warnings: list[str] = []
    wait: list[str] = []
    z, cov, nde = balance.value("altman_z"), balance.value("interest_coverage"), balance.value("net_debt_ebitda")
    distress = [msg for cond, msg in (
        (finite(z) and z < 1.81, f"Z de Altman {z:.2f} (< 1.81: zona de riesgo de insolvencia)"),
        (finite(cov) and cov < 1.5, f"Cobertura de intereses {cov:.1f}× (< 1.5×)"),
        (finite(nde) and nde > 4.5, f"Deuda neta/EBITDA {nde:.1f}× (> 4.5×)"),
    ) if cond]
    warnings += distress
    overextended = [f for f in flags if f.startswith(("RSI en sobrecompra", "Precio por encima", "Muy extendido"))]
    oversold = [f for f in flags if f.startswith(("RSI en sobreventa", "Precio por debajo", "Muy castigado"))]
    days_to_earn = (earnings_date - asof).days if earnings_date is not None else None
    earnings_soon = days_to_earn is not None and 0 <= days_to_earn <= EARNINGS_DAYS
    hot_vol = finite(vol_pct) and vol_pct >= 0.9 and (not finite(vol_trend) or vol_trend > 0.15)

    # ---------------------------------------------------------------- matriz
    if a >= A_BUY:
        bias = "compra"
        if t >= T_UP:
            action, head = "COMPRAR", good
        elif t > T_DOWN:
            action, head = "COMPRAR", f"{F} {pos} con técnico neutro: entrada escalonada."
        else:
            action, head = "ESPERAR", (f"{F} {pos} pero el precio sigue en tendencia "
                                       "bajista: esperar a que se estabilice.")
            if finite(sma50):
                wait.append(f"Que el precio recupere la media de 50 sesiones ({fmt(sma50, 'money')}) "
                            "y el MACD cruce al alza.")
            if finite(support):
                wait.append(f"O una entrada parcial cerca del soporte ({fmt(support, 'money')}) "
                            "si aparece sobreventa (RSI < 30) y el soporte aguanta.")
            if oversold:
                wait.append("Ya hay señales de sobreventa (" + "; ".join(oversold) +
                            "): vigilar un giro en los próximos días.")
    elif a <= A_SELL:
        bias = "venta"
        action = "VENDER"
        head = ((f"{F} en contra; el rebote técnico es una ocasión para reducir." if macro is not None
                 else "Fundamentales débiles o valoración exigente; el rebote técnico es una ocasión "
                 "para reducir.") if t >= T_UP else f"{F} {neg} y precio sin apoyo técnico.")
        if oversold:
            wait.append("Está en sobreventa (" + "; ".join(oversold) + "): puede haber un rebote "
                        "técnico; vender de forma escalonada en él en vez de malvender hoy.")
    else:
        if t >= T_TACTICAL:
            bias, action = "compra", "COMPRAR"
            head = f"{F} neutros; la tendencia es fuerte: compra táctica con stop."
        elif t <= -T_TACTICAL:
            bias, action = "venta", "VENDER"
            head = f"{F} neutros y tendencia bajista clara."
        else:
            bias, action = "neutral", "MANTENER"
            head = (f"Sin ventaja clara: ni el precio ni los {F.lower()} dan una señal fuerte. "
                    "Quien la tenga, mantener; quien no, no hay prisa por entrar.")
            if finite(support) and finite(resistance):
                wait.append(f"Una ruptura por encima de {fmt(resistance, 'money')} (resistencia) "
                            f"o por debajo de {fmt(support, 'money')} (soporte) aclararía la dirección.")

    # ---------------------------------------------------------------- superposiciones
    if action == "COMPRAR" and distress:
        action, head = "ESPERAR", "Hay señales de compra pero el balance tiene riesgos serios."
        wait.append("Que mejore la solvencia (deuda, cobertura de intereses) en próximos resultados.")
    if action == "COMPRAR" and overextended:
        action = "ESPERAR"
        head = "Tesis de compra, pero el precio está sobreextendido a corto: esperar un retroceso."
        lo = max(x for x in (support, sma20 - atr) if finite(x)) if any(finite(x) for x in (support, sma20 - atr)) else float("nan")
        wait.append(f"Retroceso hacia la zona {fmt(lo, 'money')}–{fmt(sma20, 'money')} "
                    "(media de 20 sesiones / soporte) o que el RSI baje de 60. Señales: "
                    + "; ".join(overextended) + ".")
    if earnings_soon:
        msg = (f"Resultados el {earnings_date:%d/%m/%Y} (en {days_to_earn} días): pueden mover el "
               "precio con fuerza")
        if action == "COMPRAR":
            action = "ESPERAR"
            head = "Tesis de compra, pero hay resultados en pocos días: mejor esperar a publicarlos."
            wait.insert(0, msg + "; comprar después si confirman la tesis (o entrar con media posición).")
        else:
            wait.insert(0, msg + ".")
    if hot_vol:
        warnings.append("Volatilidad en la zona alta de su historia y previsión GARCH por encima de "
                        "lo normal: posiciones más pequeñas y stops más anchos.")
    if ex_dividend_date is not None and 0 <= (ex_dividend_date - asof).days <= 30:
        warnings.append(f"Fecha ex-dividendo el {ex_dividend_date:%d/%m/%Y}: el precio caerá en el "
                        "importe del dividendo ese día.")

    agree = (a >= 0) == (t >= 0)
    conv = _conviction(a, t, agree)
    if hot_vol or (distress and bias == "compra"):
        conv = {"alta": "media", "media": "baja", "baja": "baja"}[conv]

    # ---------------------------------------------------------------- niveles
    lv: dict[str, float] = {"precio": price}
    if finite(atr) and bias != "venta":
        near_sup = finite(support) and 0 < price - support <= 3 * atr
        lv["stop"] = support - 0.5 * atr if near_sup else price - 2.5 * atr
        lv["riesgo_stop"] = lv["stop"] / price - 1
    if bias == "compra":
        if action == "ESPERAR" and overextended:
            lv["entrada_desde"], lv["entrada_hasta"] = (max(support, sma20 - atr) if finite(support) else sma20 - atr), sma20
        elif action == "ESPERAR" and finite(sma50) and price < sma50:
            lv["confirmacion"] = sma50
        targets = sorted(x for x in (resistance, fair_value, analyst_target) if finite(x) and x > price)
        for k, x in zip(("objetivo_1", "objetivo_2"), targets):
            lv[k] = x
    if bias == "venta" and finite(resistance):
        lv["invalidacion"] = resistance   # si la supera con fuerza, la tesis bajista falla
    if finite(support):
        lv["soporte"] = support
    if finite(resistance):
        lv["resistencia"] = resistance

    pillars = [balance, profitability, valuation, technical, risk] + ([macro] if macro else [])
    return Verdict(action, bias, head, conv, q, v, a, t, r, comp,
                   _top(pillars, True), _top(pillars, False), wait, warnings, lv)
