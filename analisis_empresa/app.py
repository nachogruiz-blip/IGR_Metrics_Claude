"""Analizador de una empresa cotizada: balance, fundamentales, valoración, técnico, series
temporales y veredicto (Comprar / Vender / Esperar / Mantener).

Ejecutar:  streamlit run analisis_empresa/app.py
Modo demo (sin red, datos sintéticos):  ANALYST_DEMO=1 streamlit run analisis_empresa/app.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from scipy import stats

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyst import core, data, report  # noqa: E402
from analyst.common import Pillar, finite, fmt  # noqa: E402
from analyst.statements import PIOTROSKI_LABELS  # noqa: E402

# --------------------------------------------------------------------------- estilo
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]   # orden fijo: precio, SMA50, SMA200, …
POS, NEG, NEUTRAL = "#2a78d6", "#e34948", "#898781"     # diverging azul (+) / rojo (−)
GRID, AXIS, INK2 = "#e1e0d9", "#c3c2b7", "#52514e"
BAND = "rgba(42,120,214,0.10)"
ACTION_STYLE = {  # icono + texto: el color nunca va solo
    "COMPRAR": ("▲", "#0ca30c"), "ESPERAR": ("⏸", "#c98a00"),
    "MANTENER": ("●", "#898781"), "VENDER": ("▼", "#d03b3b"),
}

st.set_page_config(page_title="Análisis de empresa", page_icon="🔎", layout="wide")
st.markdown("""<style>
.verdict {font-size:2rem;font-weight:700;line-height:1.1;margin:.2rem 0}
.small {color:#898781;font-size:.85rem}
div[data-testid="stMetricValue"] {font-size:1.3rem}
</style>""", unsafe_allow_html=True)


def base_layout(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=40, b=8), template="none",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif",
                                color=INK2, size=12), hovermode="x unified",
                      legend=dict(orientation="h", y=-0.12, x=0, yanchor="top", traceorder="normal"))
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False)
    return fig


def s_fmt(x: float) -> str:
    return "—" if not finite(x) else f"{x:+.2f}"


def score_bg(v: float) -> str:
    if not finite(v):
        return ""
    a = min(abs(v), 1.0) * 0.55
    return f"background-color: rgba({'42,120,214' if v > 0 else '227,73,72'},{a:.2f})"


def pillar_table(p: Pillar) -> None:
    st.markdown(f"**{p.name}** — puntuación {s_fmt(p.score)} "
                f"<span class='small'>(cobertura {p.coverage:.0%})</span>", unsafe_allow_html=True)
    rows = [{"Indicador": i.label, "Valor": i.shown, "Puntuación": i.score, "Lectura": i.note}
            for i in p.items if i.weight > 0]
    df = pd.DataFrame(rows)
    st.dataframe(df.style.map(score_bg, subset=["Puntuación"]).format({"Puntuación": s_fmt}),
                 hide_index=True, width="stretch")
    for n in p.notes:
        st.caption(n)


# --------------------------------------------------------------------------- datos
DEMO_ENV = os.environ.get("ANALYST_DEMO") == "1"


@st.cache_data(ttl=3600, show_spinner=False)
def load(ticker: str, years: int, demo: bool) -> data.CompanyData:
    return data.demo(ticker) if demo else data.fetch(ticker, years)


with st.sidebar:
    st.header("Empresa")
    demo = st.toggle("Datos sintéticos (demo)", value=DEMO_ENV,
                     help="Sin conexión: empresas inventadas con perfiles conocidos.")
    if demo:
        ticker = st.selectbox("Perfil demo", list(data.DEMO_PROFILES), index=1)
    else:
        ticker = st.text_input("Ticker de Yahoo Finance", value="ITX.MC",
                               help="Ejemplos: SAN.MC, ITX.MC, IBE.MC (Madrid); ASML.AS; SAP.DE; "
                                    "MC.PA; AAPL, MSFT (EE. UU.)").strip().upper()
    years = st.slider("Años de historia de precios", 2, 10, 5)
    rf_override = st.number_input("Tipo libre de riesgo (%, 0 = automático)", 0.0, 10.0, 0.0, 0.1)
    st.caption("Herramienta de apoyo, no asesoramiento financiero.")

if not ticker:
    st.info("Introduce un ticker en la barra lateral.")
    st.stop()
try:
    with st.spinner(f"Descargando y analizando {ticker}…"):
        cd = load(ticker, years, demo)
except Exception as e:  # noqa: BLE001
    st.error(f"No se pudieron obtener datos de «{ticker}»: {e}")
    st.stop()
if rf_override > 0:
    cd.risk_free = rf_override / 100
A = core.analyze(cd)
v, val, tech, ts = A.verdict, A.valuation, A.technical, A.timeseries
cur = cd.currency

# --------------------------------------------------------------------------- cabecera y veredicto
st.title(f"{cd.name} ({cd.ticker})")
st.caption(f"Datos a {cd.asof:%d/%m/%Y} · {cd.info.get('sector', '—')} / {cd.info.get('industry', '—')} · "
           f"índice {cd.bench_ticker or '—'} · tipo sin riesgo {cd.risk_free:.2%}"
           + (" · **datos sintéticos**" if cd.demo else ""))
for w in cd.warnings:
    st.warning(w)

icon, color = ACTION_STYLE[v.action]
c1, c2 = st.columns([1.1, 2])
with c1:
    st.markdown(f"<div class='verdict' style='color:{color}'>{icon} {v.action}</div>"
                f"<div class='small'>Convicción {v.conviction} · intención de fondo: {v.bias}</div>",
                unsafe_allow_html=True)
    st.markdown(f"**{v.headline}**")
    m1, m2, m3 = st.columns(3)
    m1.metric("Precio", f"{fmt(cd.price, 'money')} {cur}")
    m2.metric("Valor estimado", fmt(val.fair_value, "money"), fmt(val.margin, "pct"),
              help=val.method or "Sin modelo de valoración aplicable")
    tgt = cd.info.get("targetMeanPrice")
    m3.metric("Objetivo analistas", fmt(tgt, "money"),
              fmt(tgt / cd.price - 1 if finite(tgt) else np.nan, "pct"))
with c2:
    axes = {"Calidad": v.quality, "Valoración": v.valuation, "Atractivo fundamental": v.fundamental,
            "Momento técnico": v.timing, "Riesgo": v.risk, "Compuesta": v.composite}
    names = list(axes)[::-1]
    vals = [axes[k] if finite(axes[k]) else 0 for k in names]
    fig = go.Figure(go.Bar(x=vals, y=names, orientation="h",
                           marker_color=[POS if x >= 0 else NEG for x in vals],
                           text=[s_fmt(axes[k]) for k in names], textposition="outside",
                           hovertemplate="%{y}: %{x:+.2f}<extra></extra>"))
    fig.update_xaxes(range=[-1.15, 1.15], zeroline=True, zerolinecolor=AXIS)
    base_layout(fig, 250).update_layout(hovermode="closest", title="Puntuaciones (−1 desfavorable, +1 favorable)")
    st.plotly_chart(fig, width="stretch")

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("**Qué esperar / disparadores**")
    for w in v.wait_for or ["Nada pendiente: la señal es operativa ya."]:
        st.markdown(f"- {w}")
    for w in v.warnings:
        st.markdown(f"- ⚠ {w}")
with c2:
    st.markdown("**A favor**")
    for x in v.reasons_for or ["—"]:
        st.markdown(f"- ✓ {x}")
    st.markdown("**En contra**")
    for x in v.reasons_against or ["—"]:
        st.markdown(f"- ✗ {x}")
with c3:
    st.markdown("**Niveles**")
    lv = pd.DataFrame([{"Nivel": report.LEVEL_LABELS.get(k, k),
                        "Valor": fmt(x, "pct") if k == "riesgo_stop" else fmt(x, "money")}
                       for k, x in v.levels.items()])
    st.dataframe(lv, hide_index=True, width="stretch")
    if cd.earnings_date is not None:
        st.caption(f"Próximos resultados: {cd.earnings_date:%d/%m/%Y}")

tabs = st.tabs(["Balance y cuentas", "Valoración", "Técnico", "Series temporales", "Informe",
                "Metodología"])

# --------------------------------------------------------------------------- balance
with tabs[0]:
    if cd.income.empty:
        st.info("No hay estados financieros disponibles para este valor.")
    else:
        r = A.ratios
        yrs = [f"{d:%Y}" for d in r.index]
        c1, c2 = st.columns(2)
        with c1:
            fig = go.Figure()
            for k, (name, ser) in enumerate((("Ventas", cd.income["revenue"]),
                                             ("Beneficio neto", cd.income["net_income"]),
                                             ("Flujo de caja libre", r["fcf"]))):
                fig.add_bar(x=yrs, y=ser.reindex(r.index) / 1e6, name=name, marker_color=SERIES[k])
            base_layout(fig, 330).update_layout(title=f"Cuenta de resultados y caja (millones {cur})",
                                                barmode="group")
            st.plotly_chart(fig, width="stretch")
        with c2:
            fig = go.Figure()
            for k, (name, key) in enumerate((("Margen EBIT", "ebit_margin"), ("Margen neto", "net_margin"),
                                             ("ROE", "roe"), ("ROIC", "roic"))):
                if r[key].notna().any():
                    fig.add_scatter(x=yrs, y=r[key], name=name, mode="lines+markers",
                                    line=dict(color=SERIES[k], width=2))
            fig.update_yaxes(tickformat=".0%")
            base_layout(fig, 330).update_layout(title="Márgenes y rentabilidad")
            st.plotly_chart(fig, width="stretch")
        show = {"Crec. ventas": ("revenue_growth", "pct"), "Margen bruto": ("gross_margin", "pct0"),
                "Margen EBIT": ("ebit_margin", "pct0"), "Margen neto": ("net_margin", "pct0"),
                "Margen FCF": ("fcf_margin", "pct0"), "ROE": ("roe", "pct0"), "ROA": ("roa", "pct0"),
                "ROIC": ("roic", "pct0"), "Liquidez": ("current_ratio", "num"),
                "Prueba ácida": ("quick_ratio", "num"), "Deuda/patrimonio": ("debt_to_equity", "num"),
                "Deuda neta/EBITDA": ("net_debt_ebitda", "x"), "Cobertura intereses": ("interest_coverage", "x"),
                "Flujo operativo/beneficio": ("ocf_to_net_income", "x"), "Payout": ("payout", "pct0"),
                "Variación de acciones": ("share_change", "pct")}
        tab = pd.DataFrame({name: [fmt(x, kind) for x in r[key]] for name, (key, kind) in show.items()},
                           index=yrs).T
        st.markdown("**Ratios por ejercicio**")
        st.dataframe(tab, width="stretch")
        pio = A.piotroski
        if pio.available:
            st.markdown(f"**F-score de Piotroski: {pio.score}/9** "
                        f"<span class='small'>({pio.available} pruebas con dato)</span>",
                        unsafe_allow_html=True)
            st.markdown(" · ".join(f"{'✓' if t else '✗' if t is not None else '?'} {PIOTROSKI_LABELS[k]}"
                                   for k, t in pio.tests.items()))
    c1, c2 = st.columns(2)
    with c1:
        pillar_table(A.balance)
    with c2:
        pillar_table(A.profitability)

# --------------------------------------------------------------------------- valoración
with tabs[1]:
    c1, c2 = st.columns([1, 1])
    with c1:
        if val.method:
            st.markdown(f"**{val.method}**: valor estimado **{fmt(val.fair_value, 'money')} {cur}** "
                        f"({fmt(val.margin, 'pct')} frente al precio).")
        for n in val.notes:
            st.markdown(f"- {n}")
        st.markdown(f"- Coste del capital propio (CAPM) {fmt(val.ke, 'pct0')}; WACC {fmt(val.wacc, 'pct0')}.")
        if not val.sensitivity.empty:
            sens = val.sensitivity.copy()
            sens.index = [f"{x:.1%}" for x in sens.index]
            sens.columns = [f"g {x:.1%}" for x in sens.columns]
            st.markdown("**Sensibilidad del valor por acción** (filas: tasa de descuento)")
            st.dataframe(sens.style.format(lambda x: fmt(x, "money")).map(
                lambda x: score_bg(np.clip(x / cd.price - 1, -1, 1)) if finite(x) else ""),
                width="stretch")
    with c2:
        refs = {"Precio": cd.price, "Valor estimado": val.fair_value,
                "Objetivo analistas": cd.info.get("targetMeanPrice"),
                "Mín. 52 sem.": cd.prices["Low"].iloc[-252:].min(),
                "Máx. 52 sem.": cd.prices["High"].iloc[-252:].max()}
        refs = {k: x for k, x in refs.items() if finite(x)}
        fig = go.Figure(go.Bar(x=list(refs.values()), y=list(refs), orientation="h",
                               marker_color=[SERIES[0] if k == "Precio" else NEUTRAL for k in refs],
                               text=[fmt(x, "money") for x in refs.values()], textposition="outside"))
        base_layout(fig, 280).update_layout(title=f"Precio frente a referencias ({cur})", hovermode="closest")
        st.plotly_chart(fig, width="stretch")
    pillar_table(val.pillar)

# --------------------------------------------------------------------------- técnico
with tabs[2]:
    f = tech.frame.iloc[-min(len(tech.frame), 504):]
    p = cd.prices.loc[f.index]
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.6, 0.2, 0.2],
                        vertical_spacing=0.04, subplot_titles=("Precio", "RSI(14)", "MACD"))
    fig.add_scatter(x=f.index, y=f["bb_up"], line=dict(width=0), showlegend=False, hoverinfo="skip", row=1, col=1)
    fig.add_scatter(x=f.index, y=f["bb_lo"], line=dict(width=0), fill="tonexty", fillcolor=BAND,
                    name="Bollinger (20, 2σ)", hoverinfo="skip", row=1, col=1)
    fig.add_candlestick(x=p.index, open=p["Open"], high=p["High"], low=p["Low"], close=p["Close"],
                        name="Precio", increasing_line_color=POS, decreasing_line_color=NEG, row=1, col=1)
    fig.add_scatter(x=f.index, y=f["sma50"], name="Media 50", line=dict(color=SERIES[1], width=1.6), row=1, col=1)
    fig.add_scatter(x=f.index, y=f["sma200"], name="Media 200", line=dict(color=SERIES[2], width=1.6), row=1, col=1)
    for lvl, n in tech.levels:
        if abs(lvl / tech.price - 1) < 0.25:
            fig.add_hline(y=lvl, line=dict(color=AXIS, width=1, dash="dot"), row=1, col=1,
                          annotation_text=f"{lvl:.2f} ({n} toques)", annotation_position="top left",
                          annotation_font_size=10)
    fig.add_scatter(x=f.index, y=f["rsi"], name="RSI", line=dict(color=SERIES[0], width=1.4), row=2, col=1)
    for y in (30, 70):
        fig.add_hline(y=y, line=dict(color=AXIS, dash="dash", width=1), row=2, col=1)
    fig.add_bar(x=f.index, y=f["macd_hist"], name="Histograma MACD",
                marker_color=np.where(f["macd_hist"] >= 0, POS, NEG), row=3, col=1)
    fig.add_scatter(x=f.index, y=f["macd"], name="MACD", line=dict(color=SERIES[0], width=1.2), row=3, col=1)
    fig.add_scatter(x=f.index, y=f["macd_signal"], name="Señal", line=dict(color=SERIES[1], width=1.2), row=3, col=1)
    fig.update_xaxes(rangeslider_visible=False)
    base_layout(fig, 720)
    st.plotly_chart(fig, width="stretch")
    st.markdown(f"Tendencia **{tech.trend}** · soporte {fmt(tech.support, 'money')} · resistencia "
                f"{fmt(tech.resistance, 'money')} · ATR {fmt(tech.atr, 'money')} "
                f"({fmt(tech.atr / tech.price, 'pct0')})")
    for fl in tech.flags:
        st.markdown(f"- ⚑ {fl}")
    pillar_table(tech.pillar)

# --------------------------------------------------------------------------- series temporales
with tabs[3]:
    s = ts.stats
    k = st.columns(6)
    k[0].metric("Rent. anual compuesta", fmt(s["cagr"], "pct"))
    k[1].metric("Volatilidad anual", fmt(s["vol_annual"], "pct0"))
    k[2].metric("Sharpe", fmt(s["sharpe"]))
    k[3].metric("Caída máxima", fmt(s["max_drawdown"], "pct"))
    k[4].metric("VaR 95 % diario", fmt(s["cf_var_95"], "pct0"), help="Cornish-Fisher")
    k[5].metric("β frente al índice", fmt(s.get("beta")))
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure()
        rv = ts.rolling_vol
        fig.add_scatter(x=rv.index, y=rv["vol63"], name="Realizada 63 s.", line=dict(color=SERIES[0], width=1.4))
        fig.add_scatter(x=rv.index, y=rv["ewma"], name="EWMA (λ = 0.94)", line=dict(color=SERIES[1], width=1.2))
        if ts.garch is not None:
            gidx = ts.returns.index[-(len(ts.garch.sigma2) - 1):]
            fig.add_scatter(x=gidx, y=np.sqrt(ts.garch.sigma2[:-1] * 252), name="GARCH(1,1)",
                            line=dict(color=SERIES[2], width=1.2))
            fig.add_hline(y=ts.garch.long_run_vol, line=dict(color=AXIS, dash="dash", width=1),
                          annotation_text="vol. largo plazo GARCH", annotation_position="top left",
                          annotation_font_size=10)
        fig.update_yaxes(tickformat=".0%")
        base_layout(fig, 330).update_layout(title="Volatilidad anualizada")
        st.plotly_chart(fig, width="stretch")
    with c2:
        r = ts.returns
        x = np.linspace(r.quantile(0.001), r.quantile(0.999), 200)
        fig = go.Figure()
        fig.add_histogram(x=r, histnorm="probability density", nbinsx=80, name="Rendimientos diarios",
                          marker_color=SERIES[0], opacity=0.75)
        fig.add_scatter(x=x, y=stats.norm.pdf(x, r.mean(), r.std()), name="Normal equivalente",
                        line=dict(color=SERIES[1], width=2))
        fig.add_vline(x=-s["hist_var_95"], line=dict(color=NEG, dash="dash", width=1),
                      annotation_text="VaR 95 %", annotation_font_size=10)
        fig.update_xaxes(tickformat=".0%")
        base_layout(fig, 330).update_layout(title="Distribución de rendimientos", hovermode="closest")
        st.plotly_chart(fig, width="stretch")
    c1, c2 = st.columns(2)
    with c1:
        dd = ts.drawdown
        fig = go.Figure(go.Scatter(x=dd.index, y=dd, fill="tozeroy", line=dict(color=NEG, width=1),
                                   fillcolor="rgba(227,73,72,0.15)", name="Caída"))
        fig.update_yaxes(tickformat=".0%")
        base_layout(fig, 280).update_layout(title="Caída desde máximos")
        st.plotly_chart(fig, width="stretch")
    with c2:
        ann = ts.annual.dropna()
        fig = go.Figure(go.Bar(x=[str(y) for y in ann.index], y=ann,
                               marker_color=[POS if x >= 0 else NEG for x in ann],
                               text=[f"{x:+.0%}" for x in ann], textposition="outside"))
        fig.update_yaxes(tickformat=".0%")
        base_layout(fig, 280).update_layout(title="Rentabilidad por año natural", hovermode="closest")
        st.plotly_chart(fig, width="stretch")
    c1, c2 = st.columns(2)
    with c1:
        sea = ts.monthly_seasonality
        meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        fig = go.Figure(go.Bar(x=[meses[m - 1] for m in sea.index], y=sea,
                               marker_color=[POS if x >= 0 else NEG for x in sea]))
        fig.update_yaxes(tickformat=".1%")
        base_layout(fig, 260).update_layout(title="Estacionalidad: rendimiento medio por mes",
                                            hovermode="closest")
        st.plotly_chart(fig, width="stretch")
        st.caption("Con 5 años hay 5 observaciones por mes: tómese como curiosidad, no como señal.")
    with c2:
        st.markdown("**Rango de precio estimado** (volatilidad GARCH, sin deriva)")
        cone = ts.cone.copy()
        cone["vol_anual"] = cone["vol_anual"].map(lambda x: fmt(x, "pct0"))
        for col in ("p05", "p16", "p50", "p84", "p95"):
            cone[col] = cone[col].map(lambda x: fmt(x, "money"))
        st.dataframe(cone.rename(columns={"vol_anual": "Vol. anual", "p05": "5 %", "p16": "16 %",
                                          "p50": "Mediana", "p84": "84 %", "p95": "95 %"}),
                     width="stretch")
        stat_rows = [("Asimetría", fmt(s["skew"])), ("Curtosis en exceso", fmt(s["excess_kurtosis"])),
                     ("Jarque-Bera (p)", fmt(s["jb_pvalue"], "num")),
                     ("Ljung-Box r (p)", fmt(s["lb_pvalue"])), ("Ljung-Box r² (p)", fmt(s["lb2_pvalue"])),
                     ("Ratio de varianzas (5 d)", f"{fmt(s['variance_ratio'])} (z {s['vr_z']:+.1f})"),
                     ("Hurst", fmt(s["hurst"])), ("Sortino", fmt(s["sortino"])),
                     ("Calmar", fmt(s["calmar"])), ("CVaR 95 % diario", fmt(s["hist_cvar_95"], "pct0")),
                     ("VaR 99 % diario (hist.)", fmt(s["hist_var_99"], "pct0"))]
        if ts.garch is not None:
            stat_rows += [("GARCH α / β", f"{s['garch_alpha']:.3f} / {s['garch_beta']:.3f}"),
                          ("Vida media de un choque", f"{s['garch_half_life']:.0f} sesiones")]
        st.dataframe(pd.DataFrame(stat_rows, columns=["Estadístico", "Valor"]), hide_index=True,
                     width="stretch")
    for n in ts.notes:
        st.markdown(f"- {n}")
    pillar_table(ts.pillar)

# --------------------------------------------------------------------------- informe y metodología
with tabs[4]:
    md = report.to_markdown(A)
    st.download_button("Descargar informe (Markdown)", md, file_name=f"analisis_{cd.ticker}.md",
                       mime="text/markdown")
    st.markdown(md)
with tabs[5]:
    st.markdown((HERE / "METODOLOGIA.md").read_text(encoding="utf-8"))
