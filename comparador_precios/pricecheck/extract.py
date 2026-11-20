"""Extracción de datos de producto de una página HTML de tienda.

Orden de preferencia (el primero que da precio gana):
1. JSON-LD schema.org ``Product`` → ``offers`` (``Offer`` o ``AggregateOffer``) y
   ``aggregateRating``. Lo publican casi todas las tiendas por SEO.
2. Microdatos ``itemprop="price"`` / ``priceCurrency``.
3. Meta OpenGraph ``product:price:amount`` / ``og:price:amount``.

También se devuelve el texto visible de la página para buscar cupones (``coupons``).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Iterator

from bs4 import BeautifulSoup

_NUM = re.compile(r"\d[\d.,\s  ]*")


def parse_price(text: Any) -> float | None:
    """Convierte «1.299,99 €», «€1,299.99», «19,90», «19.9» o un número en float.

    Regla del separador: si aparecen «.» y «,», el último es el decimal. Si sólo aparece uno y
    va seguido de exactamente 3 dígitos (y nada más), es separador de miles («1.299» = 1299);
    en otro caso es decimal.
    """
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text) if text >= 0 else None
    m = _NUM.search(str(text))
    if not m:
        return None
    s = re.sub(r"[\s  ]", "", m.group(0)).rstrip(".,")
    if "." in s and "," in s:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        thou = "," if dec == "." else "."
        s = s.replace(thou, "").replace(dec, ".")
    elif "," in s or "." in s:
        sep = "," if "," in s else "."
        head, _, tail = s.rpartition(sep)
        if len(tail) == 3 and (s.count(sep) > 1 or head.isdigit()):
            s = s.replace(sep, "")
        else:
            s = s.replace(sep, "", s.count(sep) - 1).replace(sep, ".")
    try:
        return float(s)
    except ValueError:
        return None


@dataclass
class PageProduct:
    name: str | None = None
    brand: str | None = None
    price: float | None = None
    currency: str | None = None
    in_stock: bool | None = None
    shipping: float | None = None
    seller: str | None = None        # «offers.seller.name» (vendedor real en marketplaces)
    condition: str | None = None
    rating: float | None = None      # producto, normalizado a 0–5
    rating_count: int | None = None
    method: str | None = None        # jsonld | microdata | opengraph
    text: str = ""
    extra: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- JSON-LD
def jsonld_nodes(soup: BeautifulSoup) -> Iterator[dict]:
    """Todos los objetos JSON-LD de la página, aplanando listas y ``@graph``."""
    for tag in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        raw = tag.string or tag.get_text() or ""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            try:  # comas finales: error habitual en webs reales
                data = json.loads(re.sub(r",\s*([}\]])", r"\1", raw))
            except json.JSONDecodeError:
                continue
        yield from _walk(data)


def _walk(obj: Any) -> Iterator[dict]:
    if isinstance(obj, list):
        for o in obj:
            yield from _walk(o)
    elif isinstance(obj, dict):
        yield obj
        if "@graph" in obj:
            yield from _walk(obj["@graph"])


def has_type(node: dict, name: str) -> bool:
    t = node.get("@type")
    types = t if isinstance(t, list) else [t]
    return any(isinstance(x, str) and x.split("/")[-1].lower() == name.lower() for x in types)


def _name(v: Any) -> str | None:
    if isinstance(v, dict):
        return v.get("name")
    if isinstance(v, list) and v:
        return _name(v[0])
    return v if isinstance(v, str) else None


def normalize_rating(value: Any, best: Any = None) -> float | None:
    v, b = parse_price(value), parse_price(best) if best is not None else None
    if v is None:
        return None
    b = b or 5.0
    return round(v * 5.0 / b, 3) if b > 0 else None


def parse_aggregate_rating(ar: Any) -> tuple[float | None, int | None]:
    if not isinstance(ar, dict):
        return None, None
    rating = normalize_rating(ar.get("ratingValue"), ar.get("bestRating"))
    count = ar.get("reviewCount") or ar.get("ratingCount")
    try:
        count = int(str(count).replace(".", "").replace(",", "")) if count is not None else None
    except ValueError:
        count = None
    return rating, count


def _availability(v: Any) -> bool | None:
    if not isinstance(v, str):
        return None
    v = v.lower()
    if any(k in v for k in ("instock", "limitedavailability", "onlineonly", "presale", "preorder")):
        return True
    if any(k in v for k in ("outofstock", "soldout", "discontinued")):
        return False
    return None


def _condition(v: Any) -> str | None:
    if not isinstance(v, str):
        return None
    v = v.lower()
    return "reacondicionado" if "refurb" in v else "usado" if "used" in v else "nuevo" if "new" in v else None


def _from_offer(prod: PageProduct, off: dict) -> None:
    price = off.get("price")
    if price is None and isinstance(off.get("priceSpecification"), dict):
        price = off["priceSpecification"].get("price")
    if price is None:
        price = off.get("lowPrice")  # AggregateOffer
    prod.price = parse_price(price)
    prod.currency = off.get("priceCurrency") or (off.get("priceSpecification") or {}).get("priceCurrency")
    prod.in_stock = _availability(off.get("availability"))
    prod.condition = _condition(off.get("itemCondition"))
    prod.seller = _name(off.get("seller"))
    sd = off.get("shippingDetails")
    sd = sd[0] if isinstance(sd, list) and sd else sd
    if isinstance(sd, dict) and isinstance(sd.get("shippingRate"), dict):
        prod.shipping = parse_price(sd["shippingRate"].get("value"))
    if has_type(off, "AggregateOffer"):
        prod.extra["offer_count"] = off.get("offerCount")
        prod.extra["high_price"] = parse_price(off.get("highPrice"))


def from_jsonld(soup: BeautifulSoup) -> PageProduct | None:
    for node in jsonld_nodes(soup):
        if not (has_type(node, "Product") or has_type(node, "ProductGroup")):
            continue
        prod = PageProduct(name=node.get("name"), brand=_name(node.get("brand")), method="jsonld")
        offers = node.get("offers")
        offers = offers if isinstance(offers, list) else [offers] if offers else []
        # la oferta más barata con precio (algunas fichas listan varias condiciones)
        cands = []
        for off in offers:
            if isinstance(off, dict):
                p = PageProduct()
                _from_offer(p, off)
                if p.price is not None:
                    cands.append(p)
        if cands:
            new = [p for p in cands if p.condition in (None, "nuevo")]
            best = min(new or cands, key=lambda p: p.price)  # se prefiere el producto nuevo
            for k in ("price", "currency", "in_stock", "shipping", "seller", "condition"):
                setattr(prod, k, getattr(best, k))
            prod.extra.update(best.extra)
        prod.rating, prod.rating_count = parse_aggregate_rating(node.get("aggregateRating"))
        if prod.price is not None:
            return prod
    return None


# --------------------------------------------------------------------------- respaldos
def from_microdata(soup: BeautifulSoup) -> PageProduct | None:
    tag = soup.find(attrs={"itemprop": "price"})
    if tag is None:
        return None
    price = parse_price(tag.get("content") or tag.get_text())
    if price is None:
        return None
    cur = soup.find(attrs={"itemprop": "priceCurrency"})
    name = soup.find(attrs={"itemprop": "name"})
    avail = soup.find(attrs={"itemprop": "availability"})
    return PageProduct(
        name=(name.get("content") or name.get_text(strip=True)) if name else None,
        price=price,
        currency=(cur.get("content") or cur.get_text(strip=True)) if cur else None,
        in_stock=_availability((avail.get("href") or avail.get("content")) if avail else None),
        method="microdata",
    )


def _meta(soup: BeautifulSoup, *names: str) -> str | None:
    for n in names:
        tag = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
        if tag and tag.get("content"):
            return tag["content"]
    return None


def from_opengraph(soup: BeautifulSoup) -> PageProduct | None:
    price = parse_price(_meta(soup, "product:price:amount", "og:price:amount"))
    if price is None:
        return None
    return PageProduct(
        name=_meta(soup, "og:title"), brand=_meta(soup, "product:brand"), price=price,
        currency=_meta(soup, "product:price:currency", "og:price:currency"),
        in_stock=_availability(_meta(soup, "product:availability", "og:availability")),
        method="opengraph",
    )


def visible_text(soup: BeautifulSoup, limit: int = 40_000) -> str:
    for t in soup(["script", "style", "noscript", "svg"]):
        t.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ")).strip()[:limit]


def extract_product(html: str) -> PageProduct | None:
    """Producto de la página o ``None`` si no se encuentra ningún precio."""
    soup = BeautifulSoup(html, "lxml")
    prod = from_jsonld(soup) or from_microdata(soup) or from_opengraph(soup)
    if prod is None:
        return None
    prod.name = prod.name or _meta(soup, "og:title") or (soup.title.string.strip() if soup.title and soup.title.string else None)
    prod.text = visible_text(soup)
    return prod


# --------------------------------------------------------------------------- coincidencia
_STOP = {"de", "la", "el", "los", "las", "y", "con", "para", "en", "the", "for", "and", "with", "precio", "comprar"}


def tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", s.lower()) if t not in _STOP and len(t) > 1}


def match_score(query: str, title: str | None) -> float:
    """Fracción de palabras de la búsqueda presentes en el título del producto (0–1).
    Los tokens con dígitos (modelos: «xm5», «128gb») son obligatorios: si falta uno ⇒ 0."""
    q, t = tokens(query), tokens(title or "")
    if not q:
        return 0.0
    joined = re.sub(r"[^a-z0-9]", "", (title or "").lower())   # «WH-1000 XM5» → «wh1000xm5»

    def present(tok: str) -> bool:
        return tok in t or (len(tok) >= 2 and tok in joined)

    if any(any(c.isdigit() for c in tok) and not present(tok) for tok in q):
        return 0.0
    return sum(present(tok) for tok in q) / len(q)
