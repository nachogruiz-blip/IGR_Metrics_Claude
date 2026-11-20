"""Dashboard de seguimiento de commodities por tramos de la curva de futuros.

Tramos: 1A, 2A y 3A rolling (M+1 … M+12·n) y años de calendario A (resto del año en curso),
A+1 y A+2. El mes en curso (mes 0) nunca cuenta: en noviembre el primer mes es diciembre.

Ejecutar:  streamlit run commodities/app.py
Modo demo (sin red, curvas sintéticas):  COMMODASH_DEMO=1 streamlit run commodities/app.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from commodash import data, strips  # noqa: E402
from commodash.contracts import CATALOG, Commodity, custom  # noqa: E402

# --------------------------------------------------------------------------- estilo
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # orden fijo
POS, NEG, NEUTRAL = "#2a78d6", "#e34948", "#898781"
GRID, AXIS, INK2 = "#e1e0d9", "#c3c2b7", "#52514e"
STRUCT_ICON = {"Contango": "↗", "Backwardation": "↘", "Plana": "→", "Sin datos": "–"}
MIN_COVERAGE = 0.8

st.set_page_config(page_title="Seguimiento de commodities", page_icon="🛢️", layout="wide")
st.markdown("""<style>
.small {color:#898781;font-size:.85rem}
div[data-testid="stMetricValue"] {font-size:1.3rem}
</style>""", unsafe_allow_html=True)


def fmt_price(v: float) -> str:
    if v is None or not np.isfinite(v):
        return "—"
    a = abs(v)
    return f"{v:,.0f}" if a >= 1000 else f"{v:.1f}" if a >= 100 else f"{v:.2f}" if a >= 10 \
        else f"{v:.3f}"


def fmt_pct(v: float) -> str:
    return "—" if v is None or not np.isfinite(v) else f"{v:+.1%}"


def change_color(v: float, scale: float = 0.10) -> str:
    """Fondo diverging: azul sube, rojo baja; saturado a ±``scale``."""
    if v is None or not np.isfinite(v):
        return ""
    a = min(abs(v) / scale, 1.0) * 0.55
    rgb = "42,120,214" if v > 0 else "227,73,72"
    return f"background-color: rgba({rgb},{a:.2f})"


def base_layout(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=36, b=8), template="none",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif",
                                color=INK2, size=12),
                      hovermode="x unified",
                      legend=dict(orientation="h", y=1.0, x=0, yanchor="bottom"))
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, showspikes=True,
                     spikemode="across", spikethickness=1, spikecolor=AXIS)
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False)
    return fig


# --------------------------------------------------------------------------- datos (cacheados)
DEMO = os.environ.get("COMMODASH_DEMO") == "1"


@st.cache_data(ttl=3600, show_spinner=False)
def load_panel(key: str, demo: bool, years: float) -> pd.DataFrame:
    c = CATALOG[key]
    return data.demo_panel(c, history_years=years) if demo else data.fetch_panel(
        c, history_years=years)


@st.cache_data(show_spinner=False)
def load_csv(raw: bytes) -> dict[str, pd.DataFrame]:
    return data.read_csv(raw)


cfg = data.load_config()
with st.sidebar:
    st.header("Commodities")
    demo = st.toggle("Modo demo (curvas sintéticas)", value=DEMO,
                     help="Sin conexión a Yahoo Finance: genera curvas de futuros ficticias.")
    selected = st.multiselect("Seguimiento", list(CATALOG),
                              default=[k for k in cfg["selected"] if k in CATALOG],
                              format_func=lambda k: f"{CATALOG[k].name} ({CATALOG[k].root})")
    years = st.slider("Histórico (años)", 1, 4, int(cfg["history_years"]))
    upload = st.file_uploader("Curvas propias (CSV)", type=["csv", "txt"],
                              help="Columnas: fecha, commodity, entrega (AAAA-MM), precio. "
                                   "Para TTF, electricidad, CO2… que no están en Yahoo.")
    weighting_opt = st.radio("Ponderación del strip", ["Según commodity", "Media simple",
                                                        "Por días de entrega"],
                             help="Gas y electricidad se suelen promediar por días (o horas).")
    c1, c2 = st.columns(2)
    if c1.button("Guardar selección", width="stretch"):
        data.save_config({**cfg, "selected": selected, "history_years": years})
        st.toast("Guardado en commodities.json")
    if c2.button("Refrescar datos", width="stretch"):
        st.cache_data.clear()
    st.divider()
    st.caption("Fuente: Yahoo Finance, contrato a contrato (cierres con retraso). "
               "Herramienta de seguimiento, no asesoramiento.")

sources: dict[str, tuple[Commodity, pd.DataFrame]] = {}
with st.spinner("Descargando curvas…"):
    for k in selected:
        try:
            sources[k] = (CATALOG[k], load_panel(k, demo, years))
        except Exception as exc:  # noqa: BLE001 — una fuente rota no debe tumbar el panel
            st.warning(f"{CATALOG[k].name}: error al descargar ({exc}).")
if upload is not None:
    try:
        for name, panel in load_csv(upload.getvalue()).items():
            sources[f"csv:{name}"] = (custom(name), panel)
    except ValueError as exc:
        st.error(f"CSV no válido: {exc}")

weighting_for = {"Media simple": "equal", "Por días de entrega": "days"}
results: dict[str, dict] = {}
empty = []
for k, (c, panel) in sources.items():
    if panel.empty or panel.notna().sum().sum() < 20:
        empty.append(c.name)
        continue
    w = weighting_for.get(weighting_opt, c.weighting)
    curves = strips.prepare(panel, w, listed_months=c.months)
    results[k] = {"c": c, "curves": curves, "weighting": w,
                  "stats": {s.key: strips.strip_stats(curves, s) for s in strips.STRIPS},
                  "structure": strips.structure(curves)}
if empty:
    st.warning("Sin datos para: " + ", ".join(empty))
if not results:
    st.error("No hay curvas que mostrar. Comprueba la conexión, activa el modo demo o sube un CSV.")
    st.stop()

asof = max(r["curves"].dates[-1] for r in results.values())
labels = {s.key: s.label(asof) for s in strips.STRIPS}
m0 = asof.to_period("M")

# --------------------------------------------------------------------------- cabecera
st.title("Seguimiento de commodities")
st.markdown(
    f"<div class='small'>Datos a {asof:%d-%m-%Y}. Mes 0 = "
    f"{strips.describe_months(pd.PeriodIndex([m0]))} (no cuenta). "
    + " · ".join(f"<b>{labels[s.key]}</b>: {strips.describe_months(s.months(asof))}"
                 for s in strips.STRIPS) + "</div>", unsafe_allow_html=True)
if strips.STRIPS[3].months(asof).empty:
    st.info(f"En diciembre no quedan meses del año en curso: {labels['A']} queda vacío.")

tab_panel, tab_ficha, tab_metodo = st.tabs(["Panel", "Ficha", "Metodología"])

# --------------------------------------------------------------------------- panel
with tab_panel:
    rows, chg_rows, alerts = [], [], []
    horizon = st.segmented_control("Variación (mismos contratos)", list(strips.HORIZONS),
                                   default="1S", key="horizon") or "1S"
    for k, r in results.items():
        c, ss = r["c"], r["stats"]
        fc = strips.forward_curve(r["curves"], n_months=1)
        name, (struct, slope) = c.name, r["structure"]
        rows.append({"Commodity": name, "Unidad": c.unit,
                     "M+1": fc["price"].iloc[0] if len(fc) else np.nan,
                     **{labels[s]: ss[s].value for s in ss},
                     "Estructura 12m": f"{STRUCT_ICON[struct]} {struct} ({fmt_pct(slope)})"})
        chg_rows.append({"Commodity": name, **{labels[s]: ss[s].changes[horizon] for s in ss}})
        for s, st_ in ss.items():
            if np.isfinite(st_.coverage) and st_.coverage < MIN_COVERAGE:
                alerts.append(f"**{name} {labels[s]}**: sólo {st_.coverage:.0%} de los meses "
                              "con cotización propia; el resto, interpolado o extrapolado.")
            elif not np.isfinite(st_.value) and len(st_.months):
                alerts.append(f"**{name} {labels[s]}**: curva insuficiente para el tramo.")

    st.subheader("Precio por tramo")
    price_cols = ["M+1"] + [labels[s.key] for s in strips.STRIPS]
    prices = pd.DataFrame(rows)
    name_col = {"Commodity": st.column_config.TextColumn(width="medium")}
    st.dataframe(prices.style.format({c_: fmt_price for c_ in price_cols}),
                 hide_index=True, width="stretch", column_config=name_col,
                 height=35 * (len(prices) + 1) + 3)

    st.subheader(f"Variación {horizon}")
    chg = pd.DataFrame(chg_rows)
    strip_cols = [labels[s.key] for s in strips.STRIPS]
    scale = {"1D": 0.03, "1S": 0.06, "1M": 0.12, "3M": 0.2}[horizon]
    st.dataframe(chg.style.map(lambda v: change_color(v, scale), subset=strip_cols)
                 .format({c_: fmt_pct for c_ in strip_cols}),
                 hide_index=True, width="stretch", column_config=name_col,
                 height=35 * (len(chg) + 1) + 3)
    st.caption("Azul sube, rojo baja. Variación *like-for-like*: precio actual del tramo frente "
               "al de los mismos contratos hace 1 día / 1 semana / 1 mes / 3 meses (sin el salto "
               "del roll).")
    for a in alerts:
        st.markdown(f"⚠ {a}")

# --------------------------------------------------------------------------- ficha
with tab_ficha:
    key = st.selectbox("Commodity", list(results), format_func=lambda k: results[k]["c"].name)
    r = results[key]
    c, curves, ss = r["c"], r["curves"], r["stats"]
    struct, slope = r["structure"]
    st.caption(f"{c.name} · {c.unit or 'unidad del CSV'} · "
               f"{'ponderación por días de entrega' if r['weighting'] == 'days' else 'media simple'}"
               f" · estructura 12m: {STRUCT_ICON[struct]} {struct} ({fmt_pct(slope)}) · "
               f"último dato {curves.dates[-1]:%d-%m-%Y}")

    for group in (strips.ROLLING, strips.CALENDAR):
        cols = st.columns(len(group))
        for col, s in zip(cols, group):
            x = ss[s.key]
            col.metric(x.label, fmt_price(x.value),
                       None if not np.isfinite(x.changes["1M"]) else f"{x.changes['1M']:+.2%} 1M")
            col.caption(strips.describe_months(x.months))

    # --- curva de futuros: hoy, hace 1 semana y hace 1 mes; strips de calendario superpuestos
    st.subheader("Curva de futuros")
    fig = go.Figure()
    for i, (name, lag) in enumerate((("Hoy", 0), ("Hace 1 semana", 5), ("Hace 1 mes", 21))):
        if lag >= len(curves.dates):
            continue
        d = curves.dates[-1 - lag]
        fc = strips.forward_curve(curves, d, n_months=40)
        x_ = fc.index.to_timestamp()
        fig.add_trace(go.Scatter(
            x=x_, y=fc["price"], name=f"{name} ({d:%d-%m})", mode="lines+markers",
            line=dict(color=SERIES[i], width=2.5 if lag == 0 else 1.5),
            marker=dict(size=6 if lag == 0 else 4, color=np.where(fc["quoted"], SERIES[i], "white"),
                        line=dict(color=SERIES[i], width=1.5)),
            hovertemplate="%{y:.4g}"))
    for s in strips.CALENDAR:
        x = ss[s.key]
        if len(x.months) and np.isfinite(x.value):
            x0 = x.months[0].to_timestamp()
            x1 = (x.months[-1] + 1).to_timestamp()
            fig.add_shape(type="line", x0=x0, x1=x1, y0=x.value, y1=x.value,
                          line=dict(color=NEUTRAL, width=2, dash="dash"))
            fig.add_annotation(x=x0, y=x.value, text=f"{x.label} {fmt_price(x.value)}",
                               showarrow=False, xanchor="left", yanchor="bottom", yshift=2,
                               bgcolor="rgba(255,255,255,0.75)",
                               font=dict(size=11, color=INK2))
    base_layout(fig, 420)
    fig.update_yaxes(title=c.unit)
    st.plotly_chart(fig, width="stretch")
    st.caption("Puntos rellenos: contrato con cotización propia; huecos: mes interpolado. "
               "Líneas discontinuas: precio de cada año de calendario (strip).")

    # --- histórico de los tramos (rolling y calendario en gráficos separados, mismo eje Y)
    st.subheader("Histórico de los tramos")
    hl, hr = st.columns(2)
    for col, group, title in ((hl, strips.ROLLING, "Rolling (se renueva cada mes)"),
                              (hr, strips.CALENDAR, "Años de calendario (producto fijo)")):
        f2 = go.Figure()
        for i, s in enumerate(group):
            h = ss[s.key].history["value"]
            f2.add_trace(go.Scatter(x=h.index, y=h, name=ss[s.key].label,
                                    line=dict(color=SERIES[i], width=1.8),
                                    hovertemplate="%{y:.4g}"))
        base_layout(f2, 360)
        col.markdown(f"**{title}**")
        col.plotly_chart(f2, width="stretch")

    # --- tabla de detalle
    st.subheader("Detalle por tramo")
    det = pd.DataFrame([{
        "Tramo": x.label, "Meses": strips.describe_months(x.months), "Nº meses": len(x.months),
        "Precio": x.value, **{f"Var. {h}": x.changes[h] for h in strips.HORIZONS},
        "Vol. 1M": x.vol_1m, "Vol. 3M": x.vol_3m, "Mín. 52s": x.low_52w, "Máx. 52s": x.high_52w,
        "Posición en rango": x.range_pos, "Cobertura": x.coverage} for x in ss.values()])
    var_cols = [f"Var. {h}" for h in strips.HORIZONS]
    st.dataframe(det.style.map(change_color, subset=var_cols).format({
        "Precio": fmt_price, "Mín. 52s": fmt_price, "Máx. 52s": fmt_price,
        **{v: fmt_pct for v in var_cols},
        "Vol. 1M": lambda v: "—" if not np.isfinite(v) else f"{v:.0%}",
        "Vol. 3M": lambda v: "—" if not np.isfinite(v) else f"{v:.0%}",
        "Posición en rango": lambda v: "—" if not np.isfinite(v) else f"{v:.0%}",
        "Cobertura": lambda v: "—" if not np.isfinite(v) else f"{v:.0%}"}),
        hide_index=True, width="stretch")
    st.caption("Volatilidad anualizada de las variaciones diarias like-for-like. Posición en "
               "rango: 0 % = mínimo de 52 semanas, 100 % = máximo. Cobertura: parte del tramo "
               "con cotización propia (el resto se interpola).")

    export = pd.DataFrame({ss[s.key].label: ss[s.key].history["value"] for s in strips.STRIPS})
    st.download_button("Descargar histórico de tramos (CSV)", export.to_csv().encode("utf-8"),
                       file_name=f"strips_{c.key}_{curves.dates[-1]:%Y%m%d}.csv",
                       mime="text/csv")

# --------------------------------------------------------------------------- metodología
with tab_metodo:
    st.markdown((Path(__file__).resolve().parent / "METODOLOGIA.md").read_text(encoding="utf-8"))
