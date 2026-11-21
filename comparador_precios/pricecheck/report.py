"""Informe en Markdown (CLI, descarga desde la app y ``ejemplos/``)."""

from __future__ import annotations

from .models import ISSUE_LABELS, Assessment, PriceReport, finite


def eur(x: float | None) -> str:
    if not finite(x):
        return "—"
    s = f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s} €"


def seller_label(o) -> str:
    """«Plataforma · vendedor» cuando el vendedor real difiere del nombre de la tienda."""
    ms = o.marketplace_seller
    return o.seller + (f" · {ms}" if ms and ms.strip().lower() != o.seller.strip().lower() else "")


def rating_txt(a: Assessment) -> str:
    r = a.reputation
    return f"{r.rating:.1f}/5 ({r.review_count:,})".replace(",", ".") if r.rating is not None else "sin datos"


def issues_txt(a: Assessment) -> str:
    c = {k: v for k, v in a.reputation.issue_counts().items() if v}
    if not c:
        return "ninguno" if a.reputation.reviews_analyzed else "sin datos"
    return ", ".join(f"{ISSUE_LABELS[k].split(' /')[0].split(' o ')[0]} ×{v}" for k, v in c.items())


def coupon_status(c) -> str:
    """Qué se hace con el cupón al calcular el precio final."""
    if c.requires_service:
        return "exige contratar un servicio (no se resta)"
    if not c.code:
        return "sin código (ya incluida en el precio)"
    if c.applied:
        return "ya aplicado en el precio mostrado (no se resta otra vez)"
    return "se resta del precio final" if c.verified else "sin verificar (no se resta)"


def coupon_txt(a: Assessment) -> str:
    out = []
    for c in a.coupons:
        what = f"{c.pct:.0%}" if finite(c.pct) else eur(c.amount) if finite(c.amount) else "descuento"
        tag = "✔ en la web" if c.verified else "sin verificar"
        if c.code and (c.applied or c.requires_service):
            out.append(f"{c.code} ({what}, {coupon_status(c)})")
        elif c.code:
            out.append(f"{c.code} ({what}, {tag})")
        else:
            out.append(f"promoción anunciada {what}, {coupon_status(c)}")
    return "; ".join(out) or "—"


def conditions_txt(a: Assessment) -> str:
    return "⚠️ exige contratar un servicio" if a.requires_service else ""


def to_markdown(rep: PriceReport) -> str:
    L = [f"# Comparativa de precios: {rep.query}", ""]
    if rep.demo:
        L += ["> **Datos de demostración ficticios** (tiendas `.example`).", ""]
    if rep.brand:
        L += [f"Marca detectada: **{rep.brand}**", ""]
    if rep.recommended:
        a = rep.recommended
        L += [f"**Mejor opción fiable:** {a.offer.seller} — **{eur(a.final_price)}** "
              f"(fiabilidad {a.reliability.label}, {a.reliability.score:.0f}/100) · {a.offer.url}", ""]
    if rep.cheapest and rep.cheapest is not rep.recommended:
        a = rep.cheapest
        L += [f"Más barata sin filtrar: {a.offer.seller} — {eur(a.final_price)} "
              f"(fiabilidad {a.reliability.label}).", ""]
    if rep.median_total is not None:
        L += [f"Mediana del precio con envío: {eur(rep.median_total)} · {len(rep.assessments)} ofertas", ""]

    L += ["| Tienda | Precio | Envío | Final | Fiabilidad | Opiniones tienda | Problemas | Vendedor | Cupones | Condiciones |",
          "|---|---:|---:|---:|---|---|---|---|---|---|"]
    for a in rep.assessments:
        o = a.offer
        seller = seller_label(o)
        ship = "gratis" if o.shipping == 0 else eur(o.shipping) if o.shipping is not None else "¿?"
        score = f"{a.reliability.score:.0f}" if finite(a.reliability.score) else "—"
        L.append(f"| [{seller}]({o.url}) | {eur(o.price)} | {ship} | {eur(a.final_price)} | "
                 f"{a.reliability.label} ({score}) | {rating_txt(a)} | {issues_txt(a)} | "
                 f"{a.official.label} | {coupon_txt(a)} | {conditions_txt(a) or '—'} |")
    L.append("")

    L += ["## Avisos por tienda", ""]
    for a in rep.assessments:
        if a.reliability.warnings:
            L.append(f"- **{a.offer.seller}** ({a.offer.domain}): " + "; ".join(a.reliability.warnings) + ".")
    L.append("")
    if rep.notes or rep.errors:
        L += ["## Notas y fuentes que fallaron", ""] + [f"- {n}" for n in rep.notes + rep.errors] + [""]
    L += ["---", "Precio final = precio + envío − cupón con código visto en la web del vendedor. Los cupones "
          "«sin verificar» proceden de agregadores y no se restan; tampoco los que ya se ven aplicados en el "
          "precio de la ficha ni los que exigen contratar un servicio. Las ofertas ligadas a una tarifa o "
          "contrato no cuentan para la mediana ni la recomendación. La fiabilidad es una estimación "
          "automática (ver METODOLOGIA.md): compruébala antes de pagar.", ""]
    return "\n".join(L)
