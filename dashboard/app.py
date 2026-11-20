"""Dashboard de seguimiento de acciones: indicadores técnicos y fundamentales, señal agregada y
perspectiva a 1–3 meses.

Ejecutar:  streamlit run dashboard/app.py
Modo demo (sin red, datos sintéticos):  STOCKDASH_DEMO=1 streamlit run dashboard/app.py
"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stockdash import data, fundamental, scoring, technical  # noqa: E402

# --------------------------------------------------------------------------- estilo
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]  # orden fijo: precio, SMA50, SMA200, …
POS, NEG, NEUTRAL = "#2a78d6", "#e34948", "#898781"  # diverging azul (+) / rojo (−)
GRID, AXIS, INK, INK2 = "#e1e0d9", "#c3c2b7", "#0b0b0b", "#52514e"
BAND = "rgba(42,120,214,0.10)"

SIGNAL_STYLE = {  # icono + texto: el color nunca va solo
    "Compra fuerte": ("▲▲", "#0ca30c"), "Comprar": ("▲", "#0ca30c"),
    "Mantener": ("●", "#898781"), "Vender": ("▼", "#ec835a"),
    "Venta fuerte": ("▼▼", "#d03b3b"), "Sin datos": ("–", "#898781"),
}
OUTLOOK_ICON = {"Alcista": "↗", "Lateral": "→", "Bajista": "↘"}

st.set_page_config(page_title="Seguimiento de acciones", page_icon="📈", layout="wide")
st.markdown("""<style>
.signal {font-size:1.6rem;font-weight:600;line-height:1.2}
.small {color:#898781;font-size:.85rem}
div[data-testid="stMetricValue"] {font-size:1.35rem}
</style>""", unsafe_allow_html=True)


def fmt(v: float, kind: str) -> str:
    if v is None or not np.isfinite(v):
        return "—"
    return {"pct": f"{v:+.1%}", "pp": f"{100 * v:+.1f} pp",
            "x": f"{v:.1f}×", "num": f"{v:.2f}"}[kind]


def fmt_score(v: float) -> str:
    return "—" if not np.isfinite(v) else f"{v:+.2f}"


def score_color(v: float) -> str:
    """Fondo diverging para una puntuación en [-1, 1] (gris en 0)."""
    if not np.isfinite(v):
        return ""
    a = min(abs(v), 1.0) * 0.55
    rgb = "42,120,214" if v > 0 else "227,73,72"
    return f"background-color: rgba({rgb},{a:.2f})"


def base_layout(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=28, b=8), template="none",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif",
                                color=INK2, size=12),
                      hovermode="x unified",
                      legend=dict(orientation="h", y=1.0, x=0, yanchor="bottom",
                                  traceorder="normal"))
    fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, showspikes=True,
                     spikemode="across", spikethickness=1, spikecolor=AXIS)
    fig.update_yaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False)
    return fig


# --------------------------------------------------------------------------- datos (cacheados)
DEMO = os.environ.get("STOCKDASH_DEMO") == "1"


@st.cache_data(ttl=3600, show_spinner=False)
def load_prices(tickers: tuple[str, ...], demo: bool) -> dict[str, pd.DataFrame]:
    return data.demo_prices(list(tickers)) if demo else data.fetch_prices(list(tickers))


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def load_infos(tickers: tuple[str, ...], demo: bool, prices: tuple[float, ...]) -> dict:
    if demo:
        return {t: data.demo_info(t, p) for t, p in zip(tickers, prices)}
    with ThreadPoolExecutor(max_workers=8) as ex:
        return dict(zip(tickers, ex.map(data.fetch_info, tickers)))


# --------------------------------------------------------------------------- barra lateral
cfg = data.load_config()
with st.sidebar:
    st.header("Lista de seguimiento")
    demo = st.toggle("Modo demo (datos sintéticos)", value=DEMO,
                     help="Sin conexión a Yahoo Finance: genera precios y ratios ficticios.")
    text = st.text_area("Tickers (formato Yahoo)", ", ".join(cfg["tickers"]), height=110,
                        help="Ej.: AAPL, MSFT, SAN.MC (Madrid), ASML.AS (Ámsterdam), "
                             "SAP.DE (Fráncfort)")
    tickers = data.parse_tickers(text)
    c1, c2 = st.columns(2)
    if c1.button("Guardar lista", width="stretch"):
        data.save_config({**cfg, "tickers": tickers})
        st.toast("Lista guardada en watchlist.json")
    if c2.button("Refrescar datos", width="stretch"):
        st.cache_data.clear()

    st.subheader("Ponderación")
    w_tech = st.slider("Peso técnico en la puntuación", 0.0, 1.0, 0.6, 0.05,
                       help="Para 1–3 meses el precio (técnico) suele dominar; "
                            "el resto es fundamental.")
    st.caption(f"Técnico {w_tech:.0%} · Fundamental {1 - w_tech:.0%}")
    st.divider()
    st.caption("Herramienta de apoyo, no asesoramiento financiero. Los umbrales son "
               "heurísticos y no están validados con backtest.")

if not tickers:
    st.info("Añade tickers en la barra lateral.")
    st.stop()

benches = {t: data.benchmark_for(t, cfg["benchmarks"]) for t in tickers}
all_symbols = tuple(dict.fromkeys(tickers + list(benches.values())))
with st.spinner("Descargando precios…"):
    prices = load_prices(all_symbols, demo)
valid = [t for t in tickers if t in prices and len(prices[t]) > 260]
missing = [t for t in tickers if t not in valid]
if missing:
    st.warning("Sin histórico suficiente (≥ 1 año) para: " + ", ".join(missing))
if not valid:
    st.error("No se pudieron descargar datos. Comprueba la conexión o activa el modo demo.")
    st.stop()

snaps = {t: technical.snapshot(prices[t], prices.get(benches[t], pd.DataFrame()).get("Close"))
         for t in valid}
with st.spinner("Descargando fundamentales…"):
    infos = load_infos(tuple(valid), demo, tuple(snaps[t]["price"] for t in valid))
funds = {t: fundamental.extract(infos.get(t, {}), snaps[t]["price"]) for t in valid}
results = {t: scoring.assess(snaps[t], funds[t], w_tech) for t in valid}

# --------------------------------------------------------------------------- cabecera
st.title("Seguimiento de acciones")
counts = pd.Series([results[t].outlook for t in valid]).value_counts()
k1, k2, k3, k4 = st.columns(4)
k1.metric("Valores", len(valid))
k2.metric("↗ Alcistas 1–3m", int(counts.get("Alcista", 0)))
k3.metric("→ Laterales", int(counts.get("Lateral", 0)))
k4.metric("↘ Bajistas", int(counts.get("Bajista", 0)))

tab_panel, tab_ficha, tab_metodo = st.tabs(["Panel", "Ficha del valor", "Metodología"])

# --------------------------------------------------------------------------- panel
with tab_panel:
    rows = []
    for t in valid:
        s, f, a = snaps[t], funds[t], results[t]
        icon, _ = SIGNAL_STYLE[a.signal]
        rows.append({
            "Ticker": t, "Nombre": f["name"], "Precio": s["price"], "Día": s["chg_1d"],
            "1 mes": s["ret_1m"], "3 meses": s["ret_3m"], "RSI": s["rsi"],
            "Técnico": a.technical, "Fundam.": a.fundamental, "Total": a.composite,
            "Señal": f"{icon} {a.signal}", "1–3 meses": f"{OUTLOOK_ICON[a.outlook]} {a.outlook}",
            "P(subida)": a.prob_up,
            "Rango 3m (±1σ)": f"{a.range_3m[0]:.2f} – {a.range_3m[1]:.2f}",
        })
    table = pd.DataFrame(rows).sort_values("Total", ascending=False)
    styled = (table.style
              .map(score_color, subset=["Técnico", "Fundam.", "Total"])
              .format({"Precio": "{:.2f}", "Día": "{:+.1%}", "1 mes": "{:+.1%}",
                       "3 meses": "{:+.1%}", "RSI": "{:.0f}", "Técnico": fmt_score,
                       "Fundam.": fmt_score, "Total": fmt_score, "P(subida)": "{:.0%}"}))
    st.dataframe(styled, hide_index=True, width="stretch",
                 height=min(38 * (len(table) + 1) + 4, 600))
    st.caption("Puntuaciones en [−1, +1]: azul favorable, rojo desfavorable. "
               "Ordenado por puntuación total.")

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Técnico vs fundamental")
        sc = go.Figure()
        sc.add_hline(y=0, line=dict(color=AXIS, width=1))
        sc.add_vline(x=0, line=dict(color=AXIS, width=1))
        sc.add_trace(go.Scatter(
            x=[results[t].technical for t in valid],
            y=[np.nan_to_num(results[t].fundamental) for t in valid],
            mode="markers+text", text=valid, textposition="top center",
            textfont=dict(color=INK2, size=11),
            marker=dict(size=12, color=SERIES[0], line=dict(color="#fcfcfb", width=2)),
            customdata=[[results[t].signal, results[t].outlook] for t in valid],
            hovertemplate="<b>%{text}</b><br>Técnico %{x:+.2f} · Fundamental %{y:+.2f}"
                          "<br>%{customdata[0]} · %{customdata[1]}<extra></extra>",
            showlegend=False))
        for x, y, label in ((0.95, 0.95, "Fuerte en ambos"), (-0.95, 0.95, "Buen negocio, precio débil"),
                            (0.95, -0.95, "Precio fuerte, negocio débil"), (-0.95, -0.95, "Débil en ambos")):
            sc.add_annotation(x=x, y=y, text=label, showarrow=False,
                              font=dict(color=NEUTRAL, size=11),
                              xanchor="right" if x > 0 else "left")
        base_layout(sc, 420).update_layout(hovermode="closest")
        sc.update_xaxes(range=[-1.05, 1.05], title="Puntuación técnica", showspikes=False)
        sc.update_yaxes(range=[-1.05, 1.05], title="Puntuación fundamental", showspikes=False)
        st.plotly_chart(sc, width="stretch")
    with right:
        st.subheader("Avisos")
        any_note = False
        for t in valid:
            for n in results[t].notes:
                st.markdown(f"**{t}** — {n}")
                any_note = True
        if not any_note:
            st.caption("Sin avisos.")

# --------------------------------------------------------------------------- ficha
with tab_ficha:
    order = list(table["Ticker"])
    t = st.selectbox("Valor", order, format_func=lambda x: f"{x} — {funds[x]['name']}")
    s, f, a, df = snaps[t], funds[t], results[t], prices[t]
    icon, color = SIGNAL_STYLE[a.signal]

    h1, h2, h3 = st.columns([1.3, 1, 1])
    with h1:
        st.markdown(f"### {f['name'] or t}")
        st.caption(f"{t} · {f['sector']} · {f['industry']} · referencia {benches[t]}")
        st.markdown(f"<div class='signal' style='color:{color}'>{icon} {a.signal}</div>"
                    f"<div class='small'>Recomendación actual · puntuación {a.composite:+.2f}"
                    "</div>", unsafe_allow_html=True)
    with h2:
        st.metric("Precio", f"{s['price']:.2f} {f['currency']}", f"{s['chg_1d']:+.2%} hoy")
        st.metric("Perspectiva 1–3 meses", f"{OUTLOOK_ICON[a.outlook]} {a.outlook}")
        st.caption(f"P(subida) {a.prob_up:.0%} · puntuación ajustada {a.outlook_score:+.2f}")
    with h3:
        st.metric("Rango 1 mes (±1σ)", f"{a.range_1m[0]:.2f} – {a.range_1m[1]:.2f}")
        st.metric("Rango 3 meses (±1σ)", f"{a.range_3m[0]:.2f} – {a.range_3m[1]:.2f}")
        st.caption(f"Stop orientativo (2×ATR): {a.stop:.2f}")
    for n in a.notes:
        st.info(n)

    # --- gráfico principal: 4 paneles con eje X compartido (un eje Y por panel)
    ind = technical.indicator_frame(df).iloc[-260:]
    d = df.iloc[-260:]
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                        row_heights=[0.52, 0.12, 0.18, 0.18],
                        subplot_titles=("Precio, medias y bandas de Bollinger", "Volumen",
                                        "RSI (14)", "MACD (12, 26, 9)"))
    fig.add_trace(go.Scatter(x=ind.index, y=ind["upper"], line=dict(width=0), hoverinfo="skip",
                             showlegend=False), 1, 1)
    fig.add_trace(go.Scatter(x=ind.index, y=ind["lower"], line=dict(width=0), fill="tonexty",
                             fillcolor=BAND, name="Bollinger 20, 2σ", hoverinfo="skip"), 1, 1)
    fig.add_trace(go.Scatter(x=ind.index, y=ind["close"], name="Cierre",
                             line=dict(color=SERIES[0], width=2)), 1, 1)
    fig.add_trace(go.Scatter(x=ind.index, y=ind["sma50"], name="SMA50",
                             line=dict(color=SERIES[1], width=1.5)), 1, 1)
    fig.add_trace(go.Scatter(x=ind.index, y=ind["sma200"], name="SMA200",
                             line=dict(color=SERIES[2], width=1.5)), 1, 1)
    # cono de la estimación (±1σ desplazado por la puntuación)
    last = ind.index[-1]
    fut = pd.bdate_range(last, periods=64)
    hh = np.arange(64)
    sig = s["vol_63"] if np.isfinite(s["vol_63"]) else 0.3
    sd = sig * np.sqrt(hh / 252)
    mu = scoring.KAPPA * a.outlook_score * sd
    fig.add_trace(go.Scatter(x=fut, y=s["price"] * np.exp(mu + sd), line=dict(width=0),
                             hoverinfo="skip", showlegend=False), 1, 1)
    fig.add_trace(go.Scatter(x=fut, y=s["price"] * np.exp(mu - sd), line=dict(width=0),
                             fill="tonexty", fillcolor="rgba(137,135,129,0.18)",
                             name="Estimación 3m (±1σ)", hoverinfo="skip"), 1, 1)
    fig.add_trace(go.Scatter(x=fut, y=s["price"] * np.exp(mu), name="Centro estimado",
                             line=dict(color=NEUTRAL, width=1.5, dash="dot"),
                             hovertemplate="%{y:.2f}"), 1, 1)

    fig.add_trace(go.Bar(x=d.index, y=d["Volume"], name="Volumen", marker_color=AXIS,
                         showlegend=False), 2, 1)
    fig.add_trace(go.Scatter(x=ind.index, y=ind["rsi"], name="RSI",
                             line=dict(color=SERIES[0], width=1.5), showlegend=False), 3, 1)
    for lvl in (30, 70):
        fig.add_hline(y=lvl, line=dict(color=AXIS, width=1, dash="dash"), row=3, col=1)
    fig.add_trace(go.Bar(x=ind.index, y=ind["hist"], name="Histograma",
                         marker_color=np.where(ind["hist"] >= 0, POS, NEG), opacity=0.55,
                         showlegend=False), 4, 1)
    fig.add_trace(go.Scatter(x=ind.index, y=ind["macd"], name="MACD",
                             line=dict(color=SERIES[0], width=1.5), showlegend=False), 4, 1)
    fig.add_trace(go.Scatter(x=ind.index, y=ind["signal"], name="Señal MACD",
                             line=dict(color=SERIES[1], width=1.5), showlegend=False), 4, 1)
    base_layout(fig, 820).update_layout(margin=dict(t=60), legend=dict(y=1.06))
    fig.update_yaxes(range=[0, 100], row=3, col=1)
    fig.update_layout(bargap=0.1)
    fig.update_annotations(font=dict(size=12, color=INK2), x=0, xanchor="left")
    st.plotly_chart(fig, width="stretch")

    # --- puntuación por bloques
    st.subheader("Puntuación por bloques")
    blocks = list(scoring.TECH_BLOCKS) + list(scoring.FUND_BLOCKS)
    vals = [a.blocks.get(b, np.nan) for b in blocks]
    bf = go.Figure(go.Bar(
        y=blocks, x=vals, orientation="h",
        marker=dict(color=[POS if (np.isfinite(v) and v >= 0) else NEG for v in vals],
                    cornerradius=4),
        text=[fmt_score(v) if np.isfinite(v) else "sin datos" for v in vals],
        textposition="outside", textfont=dict(color=INK2),
        hovertemplate="%{y}: %{x:+.2f}<extra></extra>"))
    base_layout(bf, 380).update_layout(hovermode="closest")
    bf.update_xaxes(range=[-1.25, 1.25], zeroline=True, zerolinecolor=AXIS, showspikes=False)
    bf.update_yaxes(autorange="reversed", showgrid=False)
    bf.add_hline(y=4.5, line=dict(color=GRID, width=1))
    bf.add_annotation(x=-1.22, y=-0.5, text="TÉCNICO", showarrow=False, xanchor="left",
                      font=dict(size=10, color=NEUTRAL))
    bf.add_annotation(x=-1.22, y=4.6, text="FUNDAMENTAL", showarrow=False, xanchor="left",
                      yanchor="top", font=dict(size=10, color=NEUTRAL))

    c_left, c_right = st.columns([1, 1])
    with c_left:
        st.plotly_chart(bf, width="stretch")
        st.caption(f"Técnico {fmt_score(a.technical)} (cobertura {a.coverage_tech:.0%}) · "
                   f"Fundamental {fmt_score(a.fundamental)} (cobertura {a.coverage_fund:.0%})")
    with c_right:
        st.markdown("**Qué más empuja la puntuación**")
        pos = [c for c in reversed(a.contributions) if c.impact > 0][:5]
        neg = [c for c in a.contributions if c.impact < 0][:5]
        st.markdown("A favor:\n" + "\n".join(
            f"- **{c.label}** {fmt(c.value, c.fmt)} → {c.impact:+.3f}" for c in pos) if pos
            else "A favor: —")
        st.markdown("En contra:\n" + "\n".join(
            f"- **{c.label}** {fmt(c.value, c.fmt)} → {c.impact:+.3f}" for c in neg) if neg
            else "En contra: —")

    # --- tablas de detalle
    def detail(catalog, values):
        by_key = {c.key: c for c in a.contributions}
        out = []
        rel = scoring.sectors.relative_scorers(f.get("sector"))
        for ind_ in catalog:
            if ind_.key in rel and rel[ind_.key] is None:
                continue  # múltiplo no significativo en este sector
            c = by_key.get(ind_.key)
            out.append({"Bloque": ind_.block, "Indicador": ind_.label,
                        "Valor": fmt(values.get(ind_.key, np.nan), ind_.fmt),
                        "Referencia": c.reference if c else "",
                        "Puntuación": c.score if c else np.nan,
                        "Aporte": c.impact if c else np.nan, "Lectura": ind_.help})
        dfx = pd.DataFrame(out)
        return (dfx.style.map(score_color, subset=["Puntuación"])
                .format({"Puntuación": fmt_score, "Aporte": lambda v: "—" if not np.isfinite(v)
                         else f"{v:+.3f}"}))

    d1, d2 = st.tabs(["Indicadores técnicos", "Indicadores fundamentales"])
    with d1:
        st.dataframe(detail(scoring.TECHNICAL, s), hide_index=True, width="stretch",
                     height=36 * (len(scoring.TECHNICAL) + 1) + 4)
        st.caption(f"ADX {s['adx']:.0f} (fuerza de tendencia; < 20 = lateral) · ATR "
                   f"{s['atr']:.2f} ({s['atr_pct']:.1%}) · volatilidad 3m {s['vol_63']:.0%} · "
                   f"rango 52 semanas {s['low_52w']:.2f} – {s['high_52w']:.2f}")
    with d2:
        st.caption(f"Sector: {f['sector']} — los múltiplos se comparan con su mediana sectorial.")
        st.dataframe(detail(scoring.FUNDAMENTAL, f), hide_index=True, width="stretch",
                     column_config={"Referencia": st.column_config.TextColumn(width="medium"),
                                    "Indicador": st.column_config.TextColumn(width="medium")},
                     height=36 * (len(scoring.FUNDAMENTAL) + 1) + 4)
        st.caption(f"Rentabilidad por dividendo {fmt(f['div_yield'], 'pct')} · P/VC "
                   f"{fmt(f['pb'], 'x')} · analistas {f['n_analysts']:.0f}"
                   if np.isfinite(f["n_analysts"]) else "Sin cobertura de analistas.")

# --------------------------------------------------------------------------- metodología
with tab_metodo:
    here = Path(__file__).resolve().parent
    st.markdown((here / "METODOLOGIA.md").read_text(encoding="utf-8"))

    st.markdown("### Backtests guardados")
    runs = sorted(p_ for p_ in (here / "backtest" / "resultados").glob("*/INFORME.md"))
    if not runs:
        st.caption("Aún no hay backtests. Ver dashboard/backtest/README.md.")
    else:
        names = [r.parent.name for r in runs]
        default = next((i for i, n in enumerate(names) if n != "demo"), 0)
        chosen = runs[st.selectbox("Backtest", range(len(runs)), index=default,
                                   format_func=lambda i: names[i])]
        body = [ln for ln in chosen.read_text(encoding="utf-8").splitlines()
                if not ln.startswith("![")]
        st.markdown("\n".join(body))
        for png in sorted(chosen.parent.glob("*.png")):
            st.image(str(png), width=720)
