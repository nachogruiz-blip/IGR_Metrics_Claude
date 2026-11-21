"""Ofertas cuyo precio exige contratar otro servicio (telefonía, fibra, suscripción…).

Caso típico: «Galaxy S25 por 99 €» en la web de una operadora, que sólo vale dando de alta una
tarifa con permanencia. Ese precio no es comparable con el de una tienda: la oferta se marca
(``Offer.tied_service``), se excluye de la mediana, de la recomendación y de «la más barata», y
se avisa. También se marcan los cupones que exigen contratar algo (``Coupon.requires_service``).

Señales (ver METODOLOGIA.md §1):
- El dominio es de una operadora (``TELCO_DOMAINS``).
- El título, o una frase de la ficha que habla de precio (contiene «€» o «precio»), dice que el
  precio va ligado a contratar: «con tarifa», «al contratar fibra», «permanencia», «portabilidad»…

Las frases de financiación («3 plazos de 83 €/mes») y de newsletter («suscríbete y llévate un
10 %») NO cuentan: son habituales en tiendas normales y no cambian el precio del producto.
"""

from __future__ import annotations

import re

from .official import registrable_domain

# Operadoras de telefonía/fibra con tienda de móviles (España). Editable.
TELCO_DOMAINS: frozenset[str] = frozenset({
    "movistar.es", "vodafone.es", "orange.es", "yoigo.com", "masmovil.es", "jazztel.com",
    "digimobil.es", "simyo.es", "lowi.es", "pepephone.com", "o2online.es", "euskaltel.com",
    "telecable.es", "finetwork.com", "amena.com", "avatel.es", "republicamovil.es", "virgintelco.es",
    "adamo.es", "r.cat",
})

_SERVICE = (r"tarifas?|fibra(?!\s+(?:de|y)\b)|l[ií]neas?\s+(?:m[oó]vil|telef[oó]nica)|portabilidad|"
            r"contratos?\s+(?:de\s+)?(?:permanencia|servicios?|telefon[ií]a|m[oó]vil)|"
            r"planes?\s+(?:de\s+)?(?:datos|m[oó]vil|fibra|precios?)|convergentes?|"
            r"(?:fibra|internet)\s*\+\s*m[oó]vil|suscripci[oó]n|cuota\s+mensual\s+de\s+servicio")
_EXCLUDE = re.compile(r"newsletter|bolet[ií]n|suscr[ií]bete\s+(?:a\s+)?(?:nuestr|al?\s+)", re.I)
_PATTERNS = [
    # «con (tu|una) tarifa», «al contratar fibra», «junto con una línea»
    re.compile(r"\b(?:con|al\s+contratar|contratando|si\s+contratas|junto\s+(?:a|con)|asociad[oa]\s+a)\s+"
               r"(?:(?:una?|tu|la|el|cualquier|nuestra|nuestro)\s+)?(?:nueva\s+)?(?:" + _SERVICE + r")\b", re.I),
    re.compile(r"\bpermanencia\b", re.I),
    re.compile(r"\b(?:alta\s+(?:nueva|de\s+l[ií]nea)|nuevas?\s+altas?)\b", re.I),
    re.compile(r"\bs[oó]lo\s+(?:para\s+)?clientes\s+(?:de|con)\s+(?:fibra|tarifa|l[ií]nea|contrato)", re.I),
    re.compile(r"\b(?:precio|oferta)\s+(?:exclusiv[oa]\s+)?(?:para|con)\s+(?:clientes\s+(?:de\s+)?)?(?:" + _SERVICE + r")\b", re.I),
]
_PRICEY = re.compile(r"€|\beur\b|\bprecio\b|\bpor\s+\d", re.I)


def _sentences(text: str):
    return (s for s in re.split(r"(?<=[.!?·|])\s+|\n+", text) if s.strip())


def service_condition(text: str) -> str | None:
    """Primera frase de ``text`` que liga un precio a contratar un servicio, o ``None``."""
    for sent in _sentences(text):
        if _PRICEY.search(sent) and mentions_service(sent):
            return sent.strip()[:200]
    return None


def mentions_service(sentence: str) -> bool:
    """La frase (p. ej. la de un cupón) exige contratar algo."""
    return not _EXCLUDE.search(sentence) and any(p.search(sentence) for p in _PATTERNS)


def tied_service(domain: str, title: str = "", page_text: str = "",
                 telco_domains: frozenset[str] = TELCO_DOMAINS) -> str | None:
    """Motivo por el que el precio de la oferta exige contratar un servicio, o ``None``."""
    if registrable_domain(domain) in telco_domains:
        return f"{registrable_domain(domain)} es una operadora: el precio suele exigir contratar una tarifa"
    if title and mentions_service(title):
        return f"Condición en el título: «{title.strip()[:200]}»"
    hit = service_condition(page_text) if page_text else None
    return f"Condición en la ficha: «{hit}»" if hit else None
