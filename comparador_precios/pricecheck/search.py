"""Búsqueda web y descubrimiento de ofertas.

Proveedores de búsqueda general (devuelven ``SearchResult``):
- ``DuckDuckGoHtml``: sin clave, interfaz HTML (``html.duckduckgo.com``). Por defecto.
- ``BraveSearch``: API oficial, requiere ``BRAVE_API_KEY``. Más estable.

Proveedor de ofertas directas (devuelve ``Offer``):
- ``SerpApiShopping``: Google Shopping vía SerpAPI, requiere ``SERPAPI_KEY``. Da muchas tiendas
  con precio sin tener que visitar cada web.

``discover_offers`` combina: buscador → URLs de tiendas → visita de cada ficha → ``extract``.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup

from .extract import extract_product, match_score, parse_price
from .http import FetchError, Fetcher
from .models import Offer
from .official import registrable_domain

MIN_MATCH = 0.6  # fracción mínima de palabras de la búsqueda en el título del producto

# Dominios que nunca son tiendas: redes, enciclopedias, foros, comparadores y webs de cupones.
NOT_SHOPS = frozenset({
    "youtube.com", "wikipedia.org", "reddit.com", "facebook.com", "instagram.com", "x.com",
    "twitter.com", "tiktok.com", "pinterest.com", "quora.com", "forocoches.com", "xataka.com",
    "trustpilot.com", "google.com", "bing.com", "duckduckgo.com", "idealo.es", "idealo.de",
    "kelkoo.es", "pricerunner.com", "chollometro.com", "mydealz.de", "hotukdeals.com",
    "cuponation.es", "groupon.es", "rtings.com", "tomsguide.com", "techradar.com", "ocu.org",
    "mediavida.com", "linkedin.com", "elmundo.es", "elpais.com", "20minutos.es", "computerhoy.com",
    "rastreator.com", "versus.com", "reclamaciones.com", "quejasonline.com",
})


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""

    @property
    def domain(self) -> str:
        return registrable_domain(self.url)


# --------------------------------------------------------------------------- buscadores
class DuckDuckGoHtml:
    URL = "https://html.duckduckgo.com/html/"
    name = "DuckDuckGo"

    def __init__(self, fetcher: Fetcher, region: str = "es-es"):
        self.fetcher, self.region = fetcher, region

    def __call__(self, query: str) -> list[SearchResult]:
        html = self.fetcher.get_text(self.URL, params={"q": query, "kl": self.region})
        return parse_ddg(html)


def parse_ddg(html: str) -> list[SearchResult]:
    soup = BeautifulSoup(html, "lxml")
    out = []
    for res in soup.select(".result"):
        a = res.select_one("a.result__a")
        if a is None or not a.get("href"):
            continue
        href = a["href"]
        if "uddg=" in href:  # enlace de redirección //duckduckgo.com/l/?uddg=<url>
            href = parse_qs(urlsplit(href).query).get("uddg", [href])[0]
        if href.startswith("//"):
            href = "https:" + href
        if "duckduckgo.com/y.js" in href:  # anuncio
            continue
        sn = res.select_one(".result__snippet")
        out.append(SearchResult(a.get_text(" ", strip=True), href, sn.get_text(" ", strip=True) if sn else ""))
    return out


class BraveSearch:
    URL = "https://api.search.brave.com/res/v1/web/search"
    name = "Brave Search"

    def __init__(self, fetcher: Fetcher, api_key: str, country: str = "es"):
        self.fetcher, self.key, self.country = fetcher, api_key, country

    def __call__(self, query: str) -> list[SearchResult]:
        data = self.fetcher.get_json(self.URL, params={"q": query, "country": self.country, "count": 20},
                                     headers={"X-Subscription-Token": self.key, "Accept": "application/json"})
        return [SearchResult(r.get("title", ""), r["url"], r.get("description", ""))
                for r in (data.get("web") or {}).get("results", []) if r.get("url")]


def default_search(fetcher: Fetcher):
    key = os.environ.get("BRAVE_API_KEY")
    return BraveSearch(fetcher, key) if key else DuckDuckGoHtml(fetcher)


# --------------------------------------------------------------------------- Google Shopping
class SerpApiShopping:
    URL = "https://serpapi.com/search.json"
    name = "Google Shopping (SerpAPI)"

    def __init__(self, fetcher: Fetcher, api_key: str, gl: str = "es", hl: str = "es"):
        self.fetcher, self.key, self.gl, self.hl = fetcher, api_key, gl, hl

    def __call__(self, query: str) -> list[Offer]:
        data = self.fetcher.get_json(self.URL, params={"engine": "google_shopping", "q": query,
                                                       "gl": self.gl, "hl": self.hl, "api_key": self.key})
        return parse_serpapi_shopping(data)


def parse_serpapi_shopping(data: dict) -> list[Offer]:
    out = []
    for r in data.get("shopping_results", []):
        price = r.get("extracted_price")
        price = float(price) if isinstance(price, (int, float)) else parse_price(r.get("price"))
        link = r.get("link") or r.get("product_link") or ""
        if price is None or not link:
            continue
        delivery = (r.get("delivery") or "").lower()
        shipping = 0.0 if "gratis" in delivery or "free" in delivery else parse_price(delivery) if delivery else None
        out.append(Offer(seller=r.get("source") or registrable_domain(link), domain=registrable_domain(link),
                         url=link, price=price, shipping=shipping, title=r.get("title", ""),
                         page_rating=r.get("rating"), page_rating_count=r.get("reviews"),
                         condition="reacondicionado" if "reacond" in (r.get("second_hand_condition") or "").lower()
                         else "usado" if r.get("second_hand_condition") else "nuevo",
                         source="Google Shopping"))
    return out


# --------------------------------------------------------------------------- descubrimiento
def shop_candidates(results: list[SearchResult], max_shops: int) -> list[SearchResult]:
    """Primer resultado de cada dominio, excluyendo los que no son tiendas."""
    seen, out = set(), []
    for r in results:
        d = r.domain
        if d in NOT_SHOPS or d in seen or not r.url.startswith("http"):
            continue
        seen.add(d)
        out.append(r)
        if len(out) >= max_shops:
            break
    return out


def offer_from_page(r: SearchResult, html: str, query: str) -> tuple[Offer | None, str]:
    """(oferta, texto visible) a partir del HTML de una ficha; oferta None si no es el producto."""
    prod = extract_product(html)
    if prod is None or prod.price is None:
        return None, ""
    if match_score(query, prod.name or r.title) < MIN_MATCH:
        return None, ""
    dom = r.domain
    seller = prod.seller or dom.split(".")[0].capitalize()
    return Offer(seller=seller, domain=dom, url=r.url, price=prod.price, currency=prod.currency or "EUR",
                 shipping=prod.shipping, in_stock=prod.in_stock, condition=prod.condition or "nuevo",
                 title=prod.name or r.title, brand=prod.brand, marketplace_seller=prod.seller,
                 page_rating=prod.rating, page_rating_count=prod.rating_count,
                 source=f"ficha ({prod.method})"), prod.text


def discover_offers(query: str, search, fetcher: Fetcher, max_shops: int = 12,
                    errors: list[str] | None = None) -> list[tuple[Offer, str]]:
    """Ofertas encontradas visitando las tiendas que devuelve el buscador.
    Devuelve pares (oferta, texto de la ficha) — el texto sirve para buscar cupones."""
    errors = errors if errors is not None else []
    results: list[SearchResult] = []
    for q in (f"{query} comprar precio", f"{query} oferta tienda"):
        try:
            results += search(q)
        except FetchError as e:
            errors.append(f"Buscador ({getattr(search, 'name', '?')}): {e}. Si persiste, define "
                          "BRAVE_API_KEY o SERPAPI_KEY (ver README)")
    cands = shop_candidates(results, max_shops)

    def visit(r: SearchResult):
        try:
            return offer_from_page(r, fetcher.get_text(r.url), query)
        except FetchError as e:
            errors.append(f"{r.domain}: {e}")
            return None, ""

    with ThreadPoolExecutor(max_workers=6) as ex:
        pages = list(ex.map(visit, cands))
    return [(o, t) for o, t in pages if o is not None]
