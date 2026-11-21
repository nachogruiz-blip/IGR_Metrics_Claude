"""Comparador de precios: dónde comprar un producto, a qué precio y con qué garantías.

Ejecutar:  streamlit run comparador_precios/app.py
Modo demo (sin red, datos ficticios):  PRICECHECK_DEMO=1 streamlit run comparador_precios/app.py
Claves opcionales (variables de entorno, nunca en la interfaz): SERPAPI_KEY, BRAVE_API_KEY.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pricecheck import core, report, stats  # noqa: E402
from pricecheck.models import ISSUE_LABELS, LEVEL_STYLE, PriceReport, finite  # noqa: E402

# --------------------------------------------------------------------------- estilo
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]   # orden fijo
LEVEL_COLOR = {"alta": "#2a78d6", "media": "#1baf7a", "baja": "#eda100", "riesgo": "#e34948"}
GRID, AXIS, INK2, MUTED = "#e1e0d9", "#c3c2b7", "#52514e", "#898781"

st.set_page_config(page_title="Comparador de precios", page_icon="🏷️", layout="wide")
st.markdown("""<style>
.best {font-size:1.6rem;font-weight:700;line-height:1.2;margin:.2rem 0}
.small {color:#898781;font-size:.85rem}
div[data-testid="stMetricValue"] {font-size:1.3rem}
</style>""", unsafe_allow_html=True)

DEMO_ENV = os.environ.get("PRICECHECK_DEMO") == "1"


@st.cache_data(ttl=30 * 60, show_spinner=False)
def run_check(query: str, brand: str | None, official: tuple[str, ...], include_used: bool,
              max_shops: int, demo: bool) -> PriceReport:
    if demo:
        from pricecheck.demo import demo_sources
        sources = demo_sources()
    else:
        sources = core.live_sources(max_shops=max_shops)
    return core.check(query, sources, brand=brand, official_domains=official, include_used=include_used)


# --------------------------------------------------------------------------- barra lateral
with st.sidebar:
    st.header("Búsqueda")
    demo = st.toggle("Modo demo (datos ficticios, sin red)", value=DEMO_ENV, disabled=DEMO_ENV)
    if demo:
        from pricecheck.demo import DEMO_BRAND, DEMO_QUERY
    query = st.text_input("Producto (modelo exacto)", value=DEMO_QUERY if demo else "",
                          placeholder="p. ej. Sony WH-1000XM5")
    brand = st.text_input("Marca (opcional)", value=DEMO_BRAND if demo else "",
                          help="Sirve para reconocer la tienda oficial. Si se deja vacía se deduce de las fichas.")
    official_txt = st.text_input("Dominio oficial adicional (opcional)", placeholder="marca.es",
                                 help="Si la marca no está en la lista interna de dominios oficiales.")
    include_used = st.checkbox("Incluir reacondicionados / usados", value=False)
    max_shops = st.slider("Máximo de tiendas a visitar", 4, 25, 12, disabled=demo)
    st.button("Buscar", type="primary", width="stretch")
    keys = [n for n, k in (("SerpAPI", "SERPAPI_KEY"), ("Brave", "BRAVE_API_KEY")) if os.environ.get(k)]
    st.caption("Fuentes: " + ("datos ficticios" if demo else
               "DuckDuckGo/Brave + fichas de tienda + Trustpilot + RDAP"
               + (f" · claves activas: {', '.join(keys)}" if keys else " · sin claves de API")))

st.title(f"🏷️ Comparador de precios{': ' + query if query else ''}")
if not query:
    st.info("Escribe un producto en la barra lateral (o activa el modo demo).")
    st.stop()

with st.spinner("Buscando tiendas, opiniones y cupones…"):
    R = run_check(query.strip(), brand.strip() or None,
                  tuple(d.strip() for d in official_txt.split(",") if d.strip()),
                  include_used, max_shops, demo)

if R.demo:
    st.warning("Datos de demostración **ficticios**: marca y tiendas inventadas (dominios `.example`).")

# --------------------------------------------------------------------------- resumen
c1, c2, c3, c4 = st.columns(4)
if R.recommended:
    a = R.recommended
    c1.metric("Mejor opción fiable", report.eur(a.final_price))
    c1.caption(report.seller_label(a.offer))
else:
    c1.metric("Mejor opción fiable", "—")
c2.metric("Más barata (sin filtrar)", report.eur(R.cheapest.final_price) if R.cheapest else "—")
if R.cheapest:
    c2.caption(f"{report.seller_label(R.cheapest.offer)} · {R.cheapest.reliability.label}")
c3.metric("Mediana (con envío)", report.eur(R.median_total))
c4.metric("Ofertas encontradas", len(R.assessments))

if R.recommended:
    a = R.recommended
    st.markdown(f"<div class='best'>{a.reliability.label} · {a.offer.seller}: {report.eur(a.final_price)}</div>"
                f"<span class='small'>{a.official.label} · opiniones de la tienda {report.rating_txt(a)} · "
                f"<a href='{a.offer.url}' target='_blank'>ir a la oferta</a></span>", unsafe_allow_html=True)
if R.cheapest and R.recommended is not R.cheapest and R.cheapest.reliability.level in ("baja", "riesgo"):
    ch = R.cheapest
    st.error(f"La más barata ({ch.offer.seller}, {report.eur(ch.final_price)}) tiene fiabilidad "
             f"{ch.reliability.label}: " + "; ".join(ch.reliability.warnings[:3]))
for n in R.notes:
    st.caption("ℹ️ " + n)

tab_cmp, tab_det, tab_met = st.tabs(["Comparativa", "Detalle por tienda", "Metodología"])

# --------------------------------------------------------------------------- comparativa
with tab_cmp:
    if R.assessments:
        AS = R.assessments
        st.markdown("Marca en **Incluir** las ofertas que quieres comparar y elige los estadísticos: "
                    "todo se recalcula al momento. Por defecto quedan fuera las que exigen contratar un "
                    "servicio y las de segunda mano.")
        k1, k2 = st.columns([3, 1])
        chosen = k1.multiselect("Estadísticos", list(stats.STATS), default=list(stats.DEFAULT_STATS))
        base = k2.selectbox("Calcular sobre", list(stats.BASES), index=0,
                            help="Precio final = precio + envío − cupón verificado que no esté ya aplicado")
        rows = []
        for a, inc in zip(AS, stats.default_selection(AS)):
            o = a.offer
            rows.append({
                "Incluir": inc,
                "Tienda": report.seller_label(o),
                "Precio": o.price,
                "Antes": o.list_price,
                "Envío": o.shipping,
                "Precio final": a.final_price,
                "Fiabilidad": a.reliability.score if finite(a.reliability.score) else None,
                "Nivel": a.reliability.label,
                "Condiciones": report.conditions_txt(a),
                "Opiniones tienda": report.rating_txt(a),
                "Problemas reportados": report.issues_txt(a),
                "Vendedor": a.official.label,
                "Cupones": report.coupon_txt(a),
                "Stock": {True: "Sí", False: "No", None: "¿?"}[o.in_stock],
                "Enlace": o.url,
            })
        df = pd.DataFrame(rows)
        edited = st.data_editor(
            df, hide_index=True, width="stretch", key=f"sel::{R.query}::{len(AS)}",
            disabled=[c for c in df.columns if c != "Incluir"],
            column_config={
                "Incluir": st.column_config.CheckboxColumn(help="¿Entra en los estadísticos?"),
                "Precio": st.column_config.NumberColumn(format="%.2f €"),
                "Antes": st.column_config.NumberColumn(format="%.2f €", help="Precio tachado / de referencia de la ficha"),
                "Envío": st.column_config.NumberColumn(format="%.2f €", help="vacío = desconocido"),
                "Precio final": st.column_config.NumberColumn(
                    format="%.2f €", help="Precio + envío − cupón con código visto en la web y no aplicado ya"),
                "Fiabilidad": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f"),
                "Enlace": st.column_config.LinkColumn(display_text="abrir"),
            })
        mask = [bool(x) for x in edited["Incluir"]]
        sel = [a for a, m in zip(AS, mask) if m]
        values = stats.describe_offers(sel, chosen, base)

        st.markdown(f"**Estadísticos de «{base}» sobre {len(sel)} de {len(AS)} ofertas**")
        if not sel:
            st.info("No hay ninguna oferta marcada en «Incluir».")
        elif values:
            cols = st.columns(min(len(values), 5))
            for i, (name, v) in enumerate(values.items()):
                cols[i % len(cols)].metric(name, report.eur(v) if v is not None else "—")
        best_sel = core.recommend(sel)
        st.caption("Mejor opción fiable entre las marcadas: " + (
            f"{report.seller_label(best_sel.offer)} · {report.eur(best_sel.final_price)}"
            if best_sel else "ninguna (ninguna marcada con fiabilidad Alta/Media y en stock)"))

        # precio por tienda; color = nivel de fiabilidad (con icono); atenuadas las no incluidas
        pick = stats.BASES[base]
        order = list(reversed(range(len(AS))))
        fig = go.Figure(go.Bar(
            x=[pick(AS[i]) for i in order],
            y=[f"{LEVEL_STYLE[AS[i].reliability.level][0]} {report.seller_label(AS[i].offer)}"
               + (" ⚠️" if AS[i].requires_service else "") for i in order],
            orientation="h", marker_color=[LEVEL_COLOR[AS[i].reliability.level] for i in order],
            marker_opacity=[1.0 if mask[i] else 0.3 for i in order],
            text=[report.eur(pick(AS[i])) for i in order], textposition="outside", cliponaxis=False,
            hovertemplate="%{y}<br>%{x:.2f} €<extra></extra>"))
        lines = [(n, v) for n, v in values.items() if n in stats.LOCATION_STATS and v is not None]
        for j, (name, v) in enumerate(lines):
            fig.add_vline(x=v, line_dash="dot", line_color=SERIES[j % len(SERIES)],
                          annotation_text=name.lower(), annotation_position="top" if j % 2 == 0 else "bottom",
                          annotation_font_color=SERIES[j % len(SERIES)])
        fig.update_layout(height=80 + 42 * len(AS), margin=dict(l=8, r=60, t=40, b=24), template="none",
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False,
                          font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color=INK2, size=12),
                          title=dict(text=f"{base} por tienda (color = fiabilidad; atenuadas = no incluidas)",
                                     font=dict(size=14)))
        fig.update_xaxes(gridcolor=GRID, linecolor=AXIS, zeroline=False, ticksuffix=" €")
        st.plotly_chart(fig, width="stretch")
        st.caption("Leyenda: " + " · ".join(f"{i} {t}" for i, t in LEVEL_STYLE.values())
                   + " · ⚠️ exige contratar un servicio · líneas = estadísticos de posición elegidos")
    st.download_button("Descargar informe (Markdown)", report.to_markdown(R),
                       file_name="comparativa_precios.md", mime="text/markdown")

# --------------------------------------------------------------------------- detalle
with tab_det:
    for a in R.assessments:
        o, rep = a.offer, a.reputation
        with st.expander(f"{a.reliability.label} — {o.seller} · {report.eur(a.final_price)}"):
            l, r = st.columns(2)
            l.markdown(f"**Vendedor:** {a.official.label}  \n<span class='small'>{a.official.reason}</span>",
                       unsafe_allow_html=True)
            l.markdown(f"**Opiniones de la tienda:** {report.rating_txt(a)} · fuentes: "
                       f"{', '.join(rep.sources) or 'ninguna'}")
            if rep.domain_age_days is not None:
                l.markdown(f"**Antigüedad del dominio:** {rep.domain_age_days / 365:.1f} años")
            if o.list_price is not None:
                l.markdown(f"**Precio de referencia en la ficha:** {report.eur(o.list_price)} "
                           f"(rebaja visible {1 - o.price / o.list_price:.0%})")
            if o.page_rating is not None:
                l.markdown(f"**Valoración del producto en la ficha:** {o.page_rating:.1f}/5 "
                           f"({o.page_rating_count or 0} opiniones)")
            comps = {k: (f"{v:.2f}" if finite(v) else "sin dato") for k, v in a.reliability.components.items()}
            r.markdown("**Componentes de la fiabilidad** (0–1):")
            r.dataframe(pd.DataFrame({"Componente": list(comps), "Valor": list(comps.values())}),
                        hide_index=True, width="stretch")
            for w in a.reliability.warnings:
                st.markdown(f"⚠️ {w}")
            if rep.issues:
                st.markdown("**Problemas reportados**")
                st.dataframe(pd.DataFrame([{"Tipo": ISSUE_LABELS[i.category], "Texto": i.text, "Fuente": i.source,
                                            "Fecha": i.date} for i in rep.issues]),
                             hide_index=True, width="stretch")
            if a.coupons:
                st.markdown("**Cupones y descuentos**")
                st.dataframe(pd.DataFrame([{"Código": c.code or "—", "Descuento": f"{c.pct:.0%}" if finite(c.pct)
                                            else report.eur(c.amount), "Verificado": "Sí" if c.verified else "No",
                                            "Cómo se trata": report.coupon_status(c),
                                            "Detalle": c.description, "Fuente": c.source} for c in a.coupons]),
                             hide_index=True, width="stretch")
            st.markdown(f"[Abrir la oferta]({o.url}) · fuente de la oferta: {o.source}")
    if R.errors:
        with st.expander(f"Fuentes que fallaron ({len(R.errors)})"):
            for e in R.errors:
                st.markdown(f"- {e}")

with tab_met:
    st.markdown((HERE / "METODOLOGIA.md").read_text(encoding="utf-8"))
