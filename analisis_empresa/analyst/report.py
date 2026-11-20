"""Informe en Markdown de un ``Analysis`` (lo usa la CLI y el botón de descarga de la app)."""

from __future__ import annotations

from .common import Pillar, finite, fmt
from .core import Analysis
from .statements import PIOTROSKI_LABELS

ACTION_ICON = {"COMPRAR": "▲", "VENDER": "▼", "ESPERAR": "⏸", "MANTENER": "●"}
LEVEL_LABELS = {
    "precio": "Precio actual", "stop": "Stop orientativo", "riesgo_stop": "Distancia al stop",
    "entrada_desde": "Zona de entrada desde", "entrada_hasta": "Zona de entrada hasta",
    "confirmacion": "Nivel de confirmación (recuperar)", "objetivo_1": "Primer objetivo",
    "objetivo_2": "Segundo objetivo", "soporte": "Soporte", "resistencia": "Resistencia",
    "invalidacion": "Invalidación de la tesis bajista (superar)",
}


def _pillar_table(p: Pillar) -> list[str]:
    out = [f"### {p.name} — puntuación {_s(p.score)}",
           "", "| Indicador | Valor | Puntuación | Lectura |", "|---|---:|---:|---|"]
    for i in p.items:
        if i.weight <= 0:
            continue
        out.append(f"| {i.label} | {i.shown} | {_s(i.score)} | {i.note} |")
    out += [f"\n> {n}" for n in p.notes]
    return out + [""]


def _s(x: float) -> str:
    return "—" if not finite(x) else f"{x:+.2f}"


def to_markdown(a: Analysis) -> str:
    cd, v, val, tech, ts = a.data, a.verdict, a.valuation, a.technical, a.timeseries
    s = ts.stats
    cur = cd.currency
    L = [f"# {cd.name} ({cd.ticker})", "",
         f"Datos a {cd.asof:%d/%m/%Y} · precio {fmt(cd.price, 'money')} {cur} · "
         f"sector {cd.info.get('sector', '—')} · índice de referencia {cd.bench_ticker or '—'}"
         + (" · **DATOS SINTÉTICOS (demo)**" if cd.demo else ""), "",
         f"## Veredicto: {ACTION_ICON.get(v.action, '')} {v.action} (convicción {v.conviction})", "",
         f"**{v.headline}**", "",
         "| Eje | Puntuación |", "|---|---:|",
         f"| Calidad (balance + rentabilidad) | {_s(v.quality)} |",
         f"| Valoración | {_s(v.valuation)} |",
         f"| **Atractivo fundamental** | **{_s(v.fundamental)}** |",
         f"| **Momento técnico** | **{_s(v.timing)}** |",
         f"| Riesgo | {_s(v.risk)} |",
         f"| Compuesta | {_s(v.composite)} |", ""]
    if v.wait_for:
        L += ["### Qué esperar / disparadores", ""] + [f"- {w}" for w in v.wait_for] + [""]
    if v.warnings:
        L += ["### Avisos", ""] + [f"- ⚠ {w}" for w in v.warnings] + [""]
    L += ["### A favor", ""] + ([f"- {x}" for x in v.reasons_for] or ["- —"]) + [""]
    L += ["### En contra", ""] + ([f"- {x}" for x in v.reasons_against] or ["- —"]) + [""]
    L += ["### Niveles", "", "| Nivel | Valor |", "|---|---:|"]
    for k, x in v.levels.items():
        L.append(f"| {LEVEL_LABELS.get(k, k)} | {fmt(x, 'pct') if k == 'riesgo_stop' else fmt(x, 'money')} |")
    L.append("")

    L += ["## 1. Balance y cuentas", ""]
    if a.ratios is not None and len(a.ratios):
        r = a.ratios
        rows = {"Ventas": cd.income.get("revenue"), "Beneficio neto": cd.income.get("net_income"),
                "Flujo de caja libre": r["fcf"], "Deuda neta": r["net_debt"]}
        hdr = [f"{d:%Y}" for d in r.index]
        L += ["| (millones) | " + " | ".join(hdr) + " |", "|---|" + "---:|" * len(hdr)]
        for name, ser in rows.items():
            if ser is None:
                continue
            vals = ser.reindex(r.index)
            L.append(f"| {name} | " + " | ".join("—" if not finite(x) else f"{x / 1e6:,.0f}".replace(",", " ") for x in vals) + " |")
        pct_rows = {"Margen EBIT": "ebit_margin", "Margen neto": "net_margin", "ROE": "roe",
                    "ROIC": "roic", "Deuda neta/EBITDA": "net_debt_ebitda",
                    "Liquidez": "current_ratio", "Cobertura intereses": "interest_coverage"}
        for name, key in pct_rows.items():
            kind = "pct0" if key in ("ebit_margin", "net_margin", "roe", "roic") else "num"
            L.append(f"| {name} | " + " | ".join(fmt(x, kind) for x in r[key]) + " |")
        L.append("")
    pio = a.piotroski
    if pio.available:
        L += [f"**F-score de Piotroski: {pio.score}/9** ({pio.available} pruebas con dato): "
              + ", ".join(f"{'✓' if t else '✗' if t is not None else '?'} {PIOTROSKI_LABELS[k]}"
                          for k, t in pio.tests.items()), ""]
    L += _pillar_table(a.balance) + _pillar_table(a.profitability)

    L += ["## 2. Valoración", ""]
    if val.method:
        L += [f"- Método: **{val.method}** → valor estimado **{fmt(val.fair_value, 'money')}** "
              f"({fmt(val.margin, 'pct')} sobre el precio).",
              f"- Coste del capital propio {fmt(val.ke, 'pct0')}; WACC {fmt(val.wacc, 'pct0')}; "
              f"crecimiento a perpetuidad {fmt(val.gT, 'pct0')}."]
    L += [f"- {n}" for n in val.notes] + [""]
    if not val.sensitivity.empty:
        g = val.sensitivity.columns
        L += ["Sensibilidad del valor por acción (filas: tasa de descuento; columnas: g a perpetuidad):", "",
              "| tasa \\ g | " + " | ".join(f"{x:.1%}" for x in g) + " |", "|---|" + "---:|" * len(g)]
        for k, row in val.sensitivity.iterrows():
            L.append(f"| {k:.1%} | " + " | ".join(fmt(x, "money") for x in row) + " |")
        L.append("")
    L += _pillar_table(val.pillar)

    L += ["## 3. Análisis técnico", "",
          f"Tendencia **{tech.trend}**. Soporte {fmt(tech.support, 'money')}, resistencia "
          f"{fmt(tech.resistance, 'money')}, ATR(14) {fmt(tech.atr, 'money')} "
          f"({fmt(tech.atr / tech.price, 'pct0')} del precio)."
          + (f" Último cruce de medias 50/200: {tech.cross} el {tech.cross_date:%d/%m/%Y}." if tech.cross_date is not None else ""), ""]
    L += [f"- {f}" for f in tech.flags] + ([""] if tech.flags else [])
    L += _pillar_table(tech.pillar)

    L += ["## 4. Series temporales, rentabilidad y volatilidad", "",
          "| Métrica | Valor |", "|---|---:|",
          f"| Rentabilidad anual compuesta ({s['n'] / 252:.1f} años) | {fmt(s['cagr'], 'pct')} |",
          f"| Volatilidad anual | {fmt(s['vol_annual'], 'pct0')} |",
          f"| Volatilidad 21 sesiones (percentil histórico) | {fmt(s['vol21'], 'pct0')} ({fmt(s['vol21_percentile'], 'pct0')}) |",
          f"| Sharpe / Sortino | {fmt(s['sharpe'])} / {fmt(s['sortino'])} |",
          f"| Caída máxima / actual | {fmt(s['max_drawdown'], 'pct')} / {fmt(s['current_drawdown'], 'pct')} |",
          f"| VaR 95 % diario (hist. / normal / Cornish-Fisher) | {fmt(s['hist_var_95'], 'pct0')} / {fmt(s['normal_var_95'], 'pct0')} / {fmt(s['cf_var_95'], 'pct0')} |",
          f"| CVaR 95 % diario (histórico) | {fmt(s['hist_cvar_95'], 'pct0')} |",
          f"| VaR 99 % diario (histórico) | {fmt(s['hist_var_99'], 'pct0')} |",
          f"| Peor / mejor día | {fmt(s['worst_day'], 'pct')} / {fmt(s['best_day'], 'pct')} |"]
    if finite(s.get("beta")):
        L.append(f"| β / correlación con el índice | {fmt(s['beta'])} / {fmt(s['corr'])} |")
    L += [""] + [f"- {n}" for n in ts.notes] + [""]
    L += ["Rango de precio estimado (volatilidad GARCH, sin deriva):", "",
          "| Horizonte | 5 % | 16 % | Mediana | 84 % | 95 % |", "|---|---:|---:|---:|---:|---:|"]
    for h, row in ts.cone.iterrows():
        L.append(f"| {h} | " + " | ".join(fmt(row[c], "money") for c in ("p05", "p16", "p50", "p84", "p95")) + " |")
    L.append("")
    ann = ts.annual.dropna()
    if len(ann):
        L += ["Rentabilidad por año: " + ", ".join(f"{y}: {x:+.1%}" for y, x in ann.items()), ""]
    L += _pillar_table(ts.pillar)
    if cd.warnings:
        L += ["## Incidencias de datos", ""] + [f"- {w}" for w in cd.warnings] + [""]
    L += ["---", "*Herramienta de apoyo al análisis, no asesoramiento financiero. Umbrales "
          "heurísticos; los datos de Yahoo pueden tener errores o retrasos.*"]
    return "\n".join(L)
