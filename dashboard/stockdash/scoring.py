"""Puntuación de indicadores, agregación y estimación a 1–3 meses.

Esquema
-------
1. Cada indicador se transforma en una puntuación en [-1, 1] (+1 = muy favorable) mediante una
   función lineal a tramos con umbrales fijos (``Indicator.score``). Excepción: los múltiplos
   de valoración (PER, EV/EBITDA, P/ventas, P/VC) se puntúan **frente a la mediana de su sector**
   (``sectors.py``); ``Indicator.score`` es sólo el respaldo si no se pasa sector.
2. Los indicadores se agrupan en bloques. Dentro de cada bloque se promedian con pesos; los que
   faltan (NaN) se excluyen y los pesos se renormalizan.
3. Puntuación técnica T = media ponderada de los bloques técnicos; fundamental F, ídem.
4. Puntuación compuesta S = w_T·T + w_F·F (por defecto 0.6/0.4: el horizonte 1–3 meses pesa
   más el precio). Si falta F, S = T.
5. Recomendación actual por umbrales de S, con avisos de *timing* (sobrecompra/sobreventa).
6. Perspectiva 1–3 meses: S se amortigua si no hay tendencia (ADX < 20) y se clasifica en
   Alcista / Lateral / Bajista. Además se modela el rendimiento a h sesiones como
   N(μ, s²) con s = σ_63·√(h/252) y μ = κ·S·s; de ahí P(subida) = Φ(κ·S) y un rango ±1s.

Los umbrales son heurísticos (reglas habituales de análisis técnico y rangos típicos de ratios);
**no están calibrados con un backtest**. La salida es una ayuda de lectura, no una predicción.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import erf, sqrt
from typing import Callable

import numpy as np

from . import sectors


# --------------------------------------------------------------------------- funciones de puntuación
def ramp(lo: float, hi: float) -> Callable[[float], float]:
    """Lineal de ``lo`` (→ −1) a ``hi`` (→ +1), recortada. Si ``lo > hi`` la escala se invierte."""
    def f(x: float) -> float:
        if x is None or not np.isfinite(x):
            return np.nan
        return float(np.clip(-1.0 + 2.0 * (x - lo) / (hi - lo), -1.0, 1.0))
    return f


def piecewise(xs: list[float], ys: list[float]) -> Callable[[float], float]:
    """Interpolación lineal por tramos (constante fuera del rango de ``xs``)."""
    def f(x: float) -> float:
        if x is None or not np.isfinite(x):
            return np.nan
        return float(np.interp(x, xs, ys))
    return f


def positive_multiple(lo: float, hi: float) -> Callable[[float], float]:
    """Para múltiplos tipo PER: menor es mejor; ≤ 0 (sin beneficio) puntúa −1."""
    base = ramp(lo, hi)

    def f(x: float) -> float:
        if x is None or not np.isfinite(x):
            return np.nan
        return -1.0 if x <= 0 else base(x)
    return f


@dataclass(frozen=True)
class Indicator:
    key: str
    label: str
    block: str
    weight: float
    score: Callable[[float], float]
    fmt: str  # "pct", "x", "num", "pp"
    help: str


# --------------------------------------------------------------------------- catálogo técnico
TECHNICAL: list[Indicator] = [
    # Tendencia
    Indicator("dist_sma200", "Precio vs SMA200", "Tendencia", 1.0, ramp(-0.10, 0.10), "pct",
              "Por encima de la media de 200 sesiones = tendencia primaria alcista."),
    Indicator("dist_sma50", "Precio vs SMA50", "Tendencia", 0.8, ramp(-0.06, 0.06), "pct",
              "Tendencia de medio plazo."),
    Indicator("sma50_vs_200", "SMA50 vs SMA200", "Tendencia", 0.8, ramp(-0.05, 0.05), "pct",
              "Cruce dorado (>0) / cruce de la muerte (<0)."),
    Indicator("sma50_slope", "Pendiente SMA50 (1m)", "Tendencia", 0.7, ramp(-0.04, 0.04), "pct",
              "Variación de la SMA50 en el último mes."),
    Indicator("di_balance", "Dirección ADX (+DI/−DI)", "Tendencia", 0.7, ramp(-0.4, 0.4), "num",
              "(+DI − −DI)/(+DI + −DI): qué lado domina el movimiento direccional."),
    # Momentum
    Indicator("mom_12_1", "Momentum 12−1 meses", "Momentum", 1.0, ramp(-0.20, 0.30), "pct",
              "Rentabilidad de 12 meses excluyendo el último (factor momentum clásico)."),
    Indicator("ret_3m", "Rentabilidad 3 meses", "Momentum", 0.8, ramp(-0.12, 0.15), "pct",
              "Momentum de corto plazo."),
    Indicator("macd_hist_pct", "Histograma MACD (% precio)", "Momentum", 0.7, ramp(-0.5, 0.5),
              "num",
              "MACD − señal, en % del precio: aceleración del momentum."),
    Indicator("rel_strength_3m", "Fuerza relativa 3m", "Momentum", 0.8, ramp(-0.10, 0.10), "pp",
              "Rentabilidad a 3 meses menos la del índice de referencia."),
    # Osciladores (timing / reversión a la media)
    Indicator("rsi", "RSI(14)", "Osciladores", 1.0,
              piecewise([0, 20, 30, 40, 50, 60, 70, 80, 100],
                        [0.4, 0.6, 0.4, 0.0, 0.1, 0.2, -0.2, -0.7, -1.0]), "num",
              "<30 sobreventa (posible rebote); >70 sobrecompra (riesgo de corrección)."),
    Indicator("bb_pctb", "Bollinger %B", "Osciladores", 0.7,
              piecewise([-0.2, 0.0, 0.2, 0.5, 0.8, 1.0, 1.2],
                        [0.5, 0.4, 0.2, 0.0, 0.0, -0.3, -0.5]), "num",
              "Posición dentro de las bandas (0 = banda inferior, 1 = superior)."),
    # Volumen
    Indicator("obv_slope", "Flujo OBV (1m)", "Volumen", 1.0, ramp(-0.3, 0.3), "num",
              "Variación del On-Balance Volume en 21 sesiones / volumen medio: acumulación (+) o "
              "distribución (−)."),
    # Riesgo
    Indicator("dd_52w", "Distancia a máximo 52s", "Riesgo", 1.0, ramp(-0.35, -0.03), "pct",
              "Cerca de máximos anuales = fortaleza; caídas profundas = tendencia rota."),
    Indicator("vol_ratio", "Vol. 3m / vol. 12m", "Riesgo", 0.7, ramp(1.6, 0.8), "x",
              "Volatilidad reciente al alza suele acompañar a fases de estrés."),
]

TECH_BLOCKS = {"Tendencia": 0.35, "Momentum": 0.30, "Osciladores": 0.15, "Volumen": 0.10,
               "Riesgo": 0.10}

# --------------------------------------------------------------------------- catálogo fundamental
FUNDAMENTAL: list[Indicator] = [
    # Valoración
    # PER, EV/EBITDA, P/ventas y P/VC: en ``assess`` se puntúan relativos al sector
    # (sectors.py); los umbrales absolutos de abajo son el respaldo sin sector.
    Indicator("pe_forward", "PER estimado", "Valoración", 1.0, positive_multiple(35, 10), "x",
              "Precio / beneficio esperado 12m, frente a la mediana del sector. ≤0 = pérdidas."),
    Indicator("pe_trailing", "PER histórico", "Valoración", 0.6, positive_multiple(40, 12), "x",
              "Precio / beneficio de los últimos 12 meses, frente a la mediana del sector."),
    Indicator("peg", "PEG", "Valoración", 0.6, positive_multiple(3.0, 1.0), "x",
              "PER / crecimiento del BPA. <1 barato respecto a su crecimiento."),
    Indicator("ev_ebitda", "EV/EBITDA", "Valoración", 0.8, positive_multiple(25, 7), "x",
              "Valor empresa / EBITDA frente al sector; no aplica a banca."),
    Indicator("fcf_yield", "Rentab. flujo caja libre", "Valoración", 1.0, ramp(0.0, 0.07), "pct",
              "FCF / capitalización."),
    Indicator("ps", "Precio / ventas", "Valoración", 0.4, positive_multiple(12, 1.5), "x",
              "Frente al sector; útil cuando no hay beneficios."),
    Indicator("pb", "Precio / valor contable", "Valoración", 0.8, positive_multiple(4.0, 0.8),
              "x", "Sólo puntúa en financieras e inmobiliarias, frente a su sector."),
    # Calidad
    Indicator("roe", "ROE", "Calidad", 1.0, ramp(0.0, 0.25), "pct",
              "Beneficio / fondos propios."),
    Indicator("roa", "ROA", "Calidad", 0.6, ramp(0.0, 0.10), "pct", "Beneficio / activos."),
    Indicator("op_margin", "Margen operativo", "Calidad", 1.0, ramp(0.0, 0.25), "pct",
              "EBIT / ventas."),
    Indicator("net_margin", "Margen neto", "Calidad", 0.6, ramp(0.0, 0.20), "pct",
              "Beneficio neto / ventas."),
    Indicator("gross_margin", "Margen bruto", "Calidad", 0.4, ramp(0.15, 0.60), "pct",
              "Poder de fijación de precios."),
    # Crecimiento
    Indicator("rev_growth", "Crecimiento ventas", "Crecimiento", 1.0, ramp(-0.05, 0.20), "pct",
              "Interanual, último trimestre."),
    Indicator("eps_growth", "Crecimiento BPA", "Crecimiento", 0.8, ramp(-0.10, 0.25), "pct",
              "Interanual, último trimestre."),
    # Salud financiera
    Indicator("net_debt_ebitda", "Deuda neta / EBITDA", "Salud financiera", 1.0, ramp(4.0, 0.0),
              "x", "Años de EBITDA para pagar la deuda neta (<0 = caja neta)."),
    Indicator("debt_equity", "Deuda / patrimonio", "Salud financiera", 0.7, ramp(2.5, 0.3), "x",
              "Apalancamiento contable."),
    Indicator("current_ratio", "Liquidez corriente", "Salud financiera", 0.5, ramp(0.8, 2.0), "x",
              "Activo corriente / pasivo corriente."),
    # Analistas
    Indicator("target_upside", "Potencial precio objetivo", "Analistas", 1.0,
              ramp(-0.10, 0.25), "pct", "Precio objetivo medio de consenso / precio − 1."),
    Indicator("rec_mean", "Recomendación consenso", "Analistas", 0.7, ramp(3.5, 1.5), "num",
              "1 = compra fuerte, 3 = mantener, 5 = venta."),
]

FUND_BLOCKS = {"Valoración": 0.30, "Calidad": 0.25, "Crecimiento": 0.20,
               "Salud financiera": 0.15, "Analistas": 0.10}

MIN_ANALYSTS = 3  # por debajo, el consenso se ignora


# --------------------------------------------------------------------------- agregación
@dataclass
class Contribution:
    key: str
    label: str
    block: str
    value: float
    score: float
    impact: float  # aportación a la puntuación compuesta
    fmt: str
    help: str
    reference: str = ""  # p. ej. «mediana sector 25.0×» para los múltiplos relativos


@dataclass
class Assessment:
    technical: float
    fundamental: float
    composite: float
    blocks: dict[str, float]
    coverage_tech: float
    coverage_fund: float
    signal: str
    outlook: str
    outlook_score: float
    prob_up: float  # P(rentabilidad > 0) en el modelo; igual a 1 y 3 meses (μ ∝ s)
    range_1m: tuple[float, float]
    range_3m: tuple[float, float]
    stop: float
    notes: list[str] = field(default_factory=list)
    contributions: list[Contribution] = field(default_factory=list)


def _aggregate(values: dict[str, float], catalog: list[Indicator], blocks: dict[str, float],
               overrides: dict[str, Callable[[float], float] | None] | None = None):
    """Devuelve (puntuación, {bloque: puntuación}, cobertura, {key: (score, peso efectivo)}).

    ``overrides`` sustituye la función de puntuación de algunos indicadores (valoración relativa
    al sector); un valor ``None`` significa «no aplica» y el indicador se omite.
    """
    overrides = overrides or {}
    per_block: dict[str, list[tuple[Indicator, float]]] = {b: [] for b in blocks}
    n_ok = 0
    applicable = [i for i in catalog if not (i.key in overrides and overrides[i.key] is None)]
    for ind in applicable:
        scorer = overrides.get(ind.key) or ind.score
        s = scorer(values.get(ind.key, np.nan))
        if np.isfinite(s):
            per_block[ind.block].append((ind, s))
            n_ok += 1
    block_scores: dict[str, float] = {}
    for b, items in per_block.items():
        if items:
            w = np.array([i.weight for i, _ in items])
            block_scores[b] = float(np.dot(w, [s for _, s in items]) / w.sum())
    if not block_scores:
        return np.nan, {}, 0.0, {}
    bw_total = sum(blocks[b] for b in block_scores)
    total = sum(blocks[b] * v for b, v in block_scores.items()) / bw_total
    eff: dict[str, tuple[float, float]] = {}
    for b, items in per_block.items():
        if not items:
            continue
        wsum = sum(i.weight for i, _ in items)
        for ind, s in items:
            eff[ind.key] = (s, blocks[b] / bw_total * ind.weight / wsum)
    return float(total), block_scores, n_ok / len(applicable), eff


def _phi(x: float) -> float:
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


SIGNALS = [(0.45, "Compra fuerte"), (0.15, "Comprar"), (-0.15, "Mantener"),
           (-0.45, "Vender"), (-np.inf, "Venta fuerte")]
KAPPA = 0.5  # desplazamiento máximo de la media en unidades de σ·√h cuando |S| = 1
OUTLOOK_THRESHOLD = 0.15


def classify_signal(score: float) -> str:
    if not np.isfinite(score):
        return "Sin datos"
    for thr, label in SIGNALS:
        if score >= thr:
            return label
    return SIGNALS[-1][1]


def assess(tech: dict[str, float], fund: dict[str, float] | None,
           w_tech: float = 0.6) -> Assessment:
    """Evalúa un valor a partir de su foto técnica (``technical.snapshot``) y fundamental
    (``fundamental.extract``). ``w_tech`` es el peso del bloque técnico en la compuesta."""
    fund = dict(fund or {})
    if not (np.isfinite(fund.get("n_analysts", np.nan))
            and fund.get("n_analysts", 0) >= MIN_ANALYSTS):
        fund["target_upside"] = np.nan
        fund["rec_mean"] = np.nan

    T, tb, cov_t, eff_t = _aggregate(tech, TECHNICAL, TECH_BLOCKS)
    sector = fund.get("sector")
    F, fb, cov_f, eff_f = _aggregate(fund, FUNDAMENTAL, FUND_BLOCKS,
                                     sectors.relative_scorers(sector))
    medians = sectors.sector_medians(sector)
    w_t = w_tech if np.isfinite(F) else 1.0
    w_f = 1.0 - w_t
    S = w_t * T + (w_f * F if np.isfinite(F) else 0.0)

    contributions = []
    for catalog, eff, w, src in ((TECHNICAL, eff_t, w_t, tech), (FUNDAMENTAL, eff_f, w_f, fund)):
        for ind in catalog:
            if ind.key in eff:
                s, we = eff[ind.key]
                ref = (f"mediana sector {medians[ind.key]:.1f}×"
                       if src is fund and medians.get(ind.key) else "")
                contributions.append(Contribution(ind.key, ind.label, ind.block,
                                                  src.get(ind.key, np.nan), s, s * we * w,
                                                  ind.fmt, ind.help, ref))
    contributions.sort(key=lambda c: c.impact)

    # ------------------------------------------------------------------ perspectiva 1–3 meses
    adx_v = tech.get("adx", np.nan)
    trendless = np.isfinite(adx_v) and adx_v < 20 and abs(tb.get("Tendencia", 0.0)) < 0.35
    outlook_score = S * (0.5 if trendless else 1.0)
    if outlook_score > OUTLOOK_THRESHOLD:
        outlook = "Alcista"
    elif outlook_score < -OUTLOOK_THRESHOLD:
        outlook = "Bajista"
    else:
        outlook = "Lateral"

    price = tech["price"]
    sigma = tech.get("vol_63", np.nan)
    if not np.isfinite(sigma):
        sigma = tech.get("vol_252", 0.30)

    def band(h: int) -> tuple[float, float]:
        s = sigma * sqrt(h / 252.0)
        mu = KAPPA * outlook_score * s
        return price * np.exp(mu - s), price * np.exp(mu + s)

    p_up = _phi(KAPPA * outlook_score)

    # ------------------------------------------------------------------ avisos de timing
    notes: list[str] = []
    signal = classify_signal(S)
    rsi_v = tech.get("rsi", np.nan)
    if signal in ("Comprar", "Compra fuerte") and np.isfinite(rsi_v) and rsi_v > 70:
        notes.append(f"RSI {rsi_v:.0f} en sobrecompra: mejor entrar escalonado o esperar un "
                     f"retroceso hacia la SMA50 ({tech['sma50']:.2f}).")
    if signal in ("Vender", "Venta fuerte") and np.isfinite(rsi_v) and rsi_v < 30:
        notes.append(f"RSI {rsi_v:.0f} en sobreventa: es probable un rebote técnico; puede "
                     "convenir vender en ese rebote.")
    if trendless:
        notes.append(f"ADX {adx_v:.0f} < 20: sin tendencia definida, la perspectiva se "
                     "amortigua hacia lateral.")
    if np.isfinite(F) and np.isfinite(T) and T * F < 0 and min(abs(T), abs(F)) > 0.25:
        notes.append("Técnico y fundamental discrepan: "
                     + ("buen negocio con precio débil (posible oportunidad a más plazo)."
                        if F > 0 else "precio fuerte con fundamentales débiles (cuidado)."))
    if cov_f < 0.4:
        notes.append("Pocos datos fundamentales disponibles: la señal descansa sobre todo en el "
                     "técnico.")

    atr_v = tech.get("atr", np.nan)
    return Assessment(
        technical=T, fundamental=F, composite=S, blocks={**tb, **fb},
        coverage_tech=cov_t, coverage_fund=cov_f, signal=signal, outlook=outlook,
        outlook_score=outlook_score, prob_up=p_up,
        range_1m=band(21), range_3m=band(63),
        stop=price - 2.0 * atr_v if np.isfinite(atr_v) else np.nan,
        notes=notes, contributions=contributions,
    )
