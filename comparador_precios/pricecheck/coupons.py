"""Cupones y descuentos: extracción de códigos y porcentajes en texto libre.

Dos procedencias:
- La propia ficha del producto (texto visible) → ``verified=True``: el descuento está anunciado
  por el vendedor, aunque puede tener condiciones.
- Resultados de un buscador («cupón descuento <dominio>») → ``verified=False``: suelen venir de
  agregadores de cupones y muchos están caducados. Se muestran pero NO se restan del precio
  final recomendado.
"""

from __future__ import annotations

import re
from typing import Callable, Iterable

from .extract import parse_price
from .models import Coupon

# palabra clave (sin distinguir mayúsculas) + código en MAYÚSCULAS/dígitos
_CODE = re.compile(
    r"(?i:c[óo]digo(?:\s+(?:de\s+)?(?:descuento|promocional|promo))?|cup[óo]n|coupon|promo\s?code|code)"
    r"\s*[:\-–]?\s*[\"“'«]?([A-Z0-9][A-Z0-9_\-]{3,19})\b"
)
_PCT = re.compile(r"(?<![\d.,])(\d{1,2}(?:[.,]\d)?)\s?%\s*(?i:de\s+)?(?i:descuento|dto\.?|off|menos|rebaja)")
_PCT_PRE = re.compile(r"(?i:descuento|ahorra|rebaja)\s+(?:(?i:del?|un|el|hasta(?:\s+(?:el|un))?)\s+)?(\d{1,2}(?:[.,]\d)?)\s?%")
_AMOUNT = re.compile(r"(\d{1,4}(?:[.,]\d{1,2})?)\s?(?:€|eur(?:os)?)\s*(?i:de\s+)?(?i:descuento|dto\.?|off|menos)", re.I)
_MIN = re.compile(r"(?i:compras?\s+(?:superiores|mayores)\s+a|a\s+partir\s+de|m[ií]nimo(?:\s+de)?)\s+(\d{1,5}(?:[.,]\d{1,2})?)\s?€")

_STOPWORDS = {"DESCUENTO", "GRATIS", "ENVIO", "ENVÍO", "OFERTA", "OFERTAS", "PROMO", "CUPON", "CUPÓN",
              "CODIGO", "CÓDIGO", "COUPON", "CODE", "HTTPS", "HTTP", "WWW", "NONE", "NULL", "VALIDO",
              "ACTIVO", "COPIAR", "COPY", "VER", "AQUI", "AQUÍ", "CLICK", "HTML", "POSTAL"}


def _plausible_code(code: str) -> bool:
    if code.upper() in _STOPWORDS or code != code.upper():
        return False
    if code.isdigit():  # «10000» suele ser un número, no un código
        return False
    return len(code) >= 4


def _sentences(text: str) -> Iterable[str]:
    return (s for s in re.split(r"(?<=[.!?·|])\s+|\n+", text) if s.strip())


def extract_coupons(text: str, *, source: str, verified: bool, url: str | None = None) -> list[Coupon]:
    """Cupones encontrados en ``text``. Cada frase con un código da un cupón; los porcentajes o
    importes de la misma frase se asocian a él. Frases con descuento sin código dan un cupón sin
    código (descuento automático)."""
    out: list[Coupon] = []
    seen: set[tuple] = set()
    for sent in _sentences(text):
        pct_m = _PCT.search(sent) or _PCT_PRE.search(sent)
        amt_m = _AMOUNT.search(sent)
        min_m = _MIN.search(sent)
        pct = parse_price(pct_m.group(1)) / 100 if pct_m else None
        amt = parse_price(amt_m.group(1)) if amt_m else None
        mn = parse_price(min_m.group(1)) if min_m else None
        codes = [c for c in _CODE.findall(sent) if _plausible_code(c)]
        if not codes and pct is None and amt is None:
            continue
        for code in codes or [None]:
            key = (code, pct, amt)
            if key in seen:
                continue
            seen.add(key)
            out.append(Coupon(description=sent.strip()[:200], code=code, pct=pct, amount=amt,
                              min_purchase=mn, source=source, url=url, verified=verified))
    return out


def search_coupons(domain: str, search: Callable[[str], list], *, limit: int = 10) -> list[Coupon]:
    """Cupones NO verificados a partir de los resultados del buscador (título + fragmento)."""
    out: list[Coupon] = []
    for r in search(f"cupón descuento {domain}")[:limit]:
        text = f"{r.title}. {r.snippet}"
        if domain.split(".")[0].lower() not in text.lower():
            continue  # resultado de otra tienda
        out += extract_coupons(text, source=f"buscador ({r.domain})", verified=False, url=r.url)
    return dedupe(out)


def dedupe(coupons: list[Coupon]) -> list[Coupon]:
    best: dict[tuple, Coupon] = {}
    for c in coupons:
        key = (c.code, c.pct, c.amount)
        if key not in best or (c.verified and not best[key].verified):
            best[key] = c
    return list(best.values())
