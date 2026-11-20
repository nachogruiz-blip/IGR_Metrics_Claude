"""Reputación de la tienda: opiniones, problemas reportados y antigüedad del dominio.

Fuentes (todas sin clave de API):
- Trustpilot (``https://es.trustpilot.com/review/<dominio>``): ``aggregateRating`` y reseñas del
  JSON-LD de la página. Las reseñas con ≤ 2 estrellas se clasifican en problemas.
- Buscador: «<dominio> opiniones problemas entrega» → fragmentos clasificados como problemas.
- RDAP (``https://rdap.org/domain/<dominio>``): fecha de registro del dominio.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Callable

from bs4 import BeautifulSoup

from .extract import has_type, jsonld_nodes, parse_aggregate_rating, normalize_rating
from .http import FetchError, Fetcher
from .models import ISSUE_CATEGORIES, Issue, Reputation

TRUSTPILOT = "https://es.trustpilot.com/review/{domain}"
RDAP = "https://rdap.org/domain/{domain}"
NEGATIVE_MAX = 2.0  # estrellas: reseñas con esta nota o menos se analizan como problemas

# Palabras clave por categoría (minúsculas, sin tildes: se comparan con texto normalizado).
KEYWORDS: dict[str, tuple[str, ...]] = {
    "fraude": ("estafa", "estafadores", "fraude", "timo", "timado", "scam", "fraud", "fake shop",
               "tienda falsa", "nunca recibi", "never received", "no existe", "falsificado", "counterfeit",
               "web falsa", "phishing"),
    "entrega": ("no ha llegado", "no llego", "no me llego", "sin recibir", "retraso", "entrega",
                "envio", "paquete", "transportista", "mensajero", "seur", "correos", "mrw", "gls",
                "nacex", "dhl", "ups", "delivery", "shipping", "not delivered", "late", "tracking",
                "seguimiento", "perdido", "extraviado"),
    "devolucion": ("reembolso", "devolucion", "devolver", "devuelto", "refund", "return", "garantia",
                   "warranty", "mi dinero", "abono", "cancelar el pedido", "cancelacion"),
    "producto": ("defectuoso", "roto", "rota", "danado", "golpeado", "usado", "no funciona",
                 "broken", "damaged", "defective", "equivocado", "otro producto", "wrong item",
                 "incompleto", "precintado no"),
    "atencion": ("atencion al cliente", "no responden", "no contestan", "sin respuesta", "nadie responde",
                 "customer service", "no answer", "chat", "telefono", "ignoran"),
}


# Un fragmento de buscador sólo cuenta como problema si además suena negativo
# («envío rápido» no es una queja).
NEGATIVE_CUES = ("no ", "nunca", "problema", "queja", "reclamacion", "denuncia", "mal ", "malo",
                 "pesimo", "horrible", "estafa", "fraude", "timo", "retraso", "sin ", "never",
                 "not ", "problem", "complaint", "worst", "terrible", "avoid", "evitad", "cuidado")


def is_negative(text: str) -> bool:
    t = " " + _norm(text) + " "
    return any(c in t for c in NEGATIVE_CUES)


def _norm(s: str) -> str:
    s = s.lower()
    for a, b in zip("áéíóúüñ", "aeiouun"):
        s = s.replace(a, b)
    return s


def classify_issue(text: str) -> str | None:
    """Categoría del problema descrito en ``text`` (prioridad: orden de ``ISSUE_CATEGORIES``)."""
    t = _norm(text)
    for cat in ISSUE_CATEGORIES:
        if any(re.search(r"\b" + re.escape(k) + r"\b", t) for k in KEYWORDS[cat]):
            return cat
    return None


def _parse_date(v) -> date | None:
    if not isinstance(v, str):
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def parse_trustpilot(html: str, domain: str) -> Reputation:
    """Valoración global y problemas a partir del JSON-LD de una página de Trustpilot."""
    soup = BeautifulSoup(html, "lxml")
    rep = Reputation(domain=domain, sources=["Trustpilot"], url=TRUSTPILOT.format(domain=domain))
    reviews: list[dict] = []
    for node in jsonld_nodes(soup):
        if "aggregateRating" in node and rep.rating is None:
            rep.rating, cnt = parse_aggregate_rating(node["aggregateRating"])
            rep.review_count = cnt or 0
        if has_type(node, "AggregateRating") and rep.rating is None:
            rep.rating, cnt = parse_aggregate_rating(node)
            rep.review_count = cnt or 0
        if has_type(node, "Review"):
            reviews.append(node)
        for r in node.get("review", []) if isinstance(node.get("review"), list) else []:
            if isinstance(r, dict):
                reviews.append(r)
    seen = set()
    for r in reviews:
        body = " ".join(str(r.get(k) or "") for k in ("headline", "name", "reviewBody")).strip()
        if not body or body in seen:
            continue
        seen.add(body)
        rep.reviews_analyzed += 1
        rr = r.get("reviewRating") or {}
        stars = normalize_rating(rr.get("ratingValue"), rr.get("bestRating")) if isinstance(rr, dict) else None
        if stars is not None and stars > NEGATIVE_MAX:
            continue
        cat = classify_issue(body)
        if cat:
            rep.issues.append(Issue(cat, body[:300], "Trustpilot", _parse_date(r.get("datePublished")), stars))
    return rep


def parse_rdap_age(data: dict, today: date | None = None) -> int | None:
    """Días desde el evento «registration» de una respuesta RDAP."""
    today = today or date.today()
    for ev in data.get("events", []) if isinstance(data, dict) else []:
        if ev.get("eventAction") == "registration":
            d = _parse_date(ev.get("eventDate"))
            if d:
                return (today - d).days
    return None


def search_issues(domain: str, search: Callable[[str], list], limit: int = 10) -> tuple[list[Issue], int]:
    """Problemas mencionados en fragmentos del buscador. Devuelve (problemas, fragmentos leídos)."""
    issues, n = [], 0
    stem = domain.split(".")[0].lower()
    for r in search(f'"{domain}" opiniones problemas entrega estafa')[:limit]:
        text = f"{r.title}. {r.snippet}"
        if stem not in text.lower() or r.domain == domain:
            continue  # resultado de otra web o de la propia tienda
        n += 1
        cat = classify_issue(text) if is_negative(text) else None
        if cat:
            issues.append(Issue(cat, text[:300], f"buscador ({r.domain})"))
    return issues, n


def fetch_reputation(domain: str, fetcher: Fetcher, search: Callable[[str], list] | None = None,
                     https: bool | None = None) -> Reputation:
    """Combina Trustpilot + RDAP + buscador. Cada fuente que falla se omite (queda en ``sources``
    sólo lo que respondió)."""
    try:
        rep = parse_trustpilot(fetcher.get_text(TRUSTPILOT.format(domain=domain)), domain)
    except FetchError:
        rep = Reputation(domain=domain)
    rep.https = https
    try:
        rep.domain_age_days = parse_rdap_age(fetcher.get_json(RDAP.format(domain=domain)))
        if rep.domain_age_days is not None:
            rep.sources.append("RDAP")
    except (FetchError, ValueError):
        pass
    if search is not None:
        try:
            extra, n = search_issues(domain, search)
            rep.issues += extra
            rep.reviews_analyzed += n
            rep.sources.append("buscador")
        except FetchError:
            pass
    return rep
