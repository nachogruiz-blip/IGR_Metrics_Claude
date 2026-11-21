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
    # prensa, blogs de reseñas y comparadores
    "hipertextual.com", "elespanol.com", "abc.es", "lavanguardia.com", "elconfidencial.com",
    "eldiario.es", "huffingtonpost.es", "marca.com", "as.com", "trendencias.com", "vogue.es",
    "elle.com", "telva.com", "glamour.es", "cosmopolitan.com", "mujerhoy.com", "businessinsider.es",
    "genbeta.com", "applesfera.com", "andro4all.com", "androidphoria.com", "topesdegama.com",
    "muycomputer.com", "profesionalreview.com", "geektopia.es", "kimovil.com", "tiendeo.es",
    "ofertia.com", "promodescuentos.com", "cupones.es", "descuentos.es", "chollos.es",
    "shopalike.es", "ciao.es", "twenga.es", "preciosmundi.com", "amazon-affiliate.com",
    # anuncios de particulares (segunda mano)
    "milanuncios.com", "vinted.es", "todocoleccion.net",
})

# Rutas que suelen ser listados, búsquedas internas o artículos, no fichas de producto.
LISTING_HINTS = ("/search", "/buscar", "/busqueda", "/resultados", "?q=", "&q=", "/s?", "/categoria",
                 "/category", "/categorias", "/c/", "/tag/", "/marca/", "/brand/", "/listado")
ARTICLE_HINTS = ("/blog/", "/noticias/", "/news/", "/articulo", "/review", "/opiniones/", "/foro/",
                 "/comparativa", "/mejores-", "/guia-", "/vs-")


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


def _old_price(r: dict, price: float) -> float | None:
    old = r.get("extracted_old_price")
    old = float(old) if isinstance(old, (int, float)) else parse_price(r.get("old_price"))
    return old if old and old > price else None


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
                         list_price=_old_price(r, price),
                         condition="reacondicionado" if "reacond" in (r.get("second_hand_condition") or "").lower()
                         else "usado" if r.get("second_hand_condition") else "nuevo",
                         source="Google Shopping"))
    return out


# --------------------------------------------------------------------------- descubrimiento
def url_kind(url: str) -> str:
    """«article» (blog, reseña, comparativa), «listing» (búsqueda o categoría) o «product»."""
    u = url.lower()
    if any(h in u for h in ARTICLE_HINTS):
        return "article"
    if any(h in u for h in LISTING_HINTS):
        return "listing"
    return "product"


def candidate_groups(results: list[SearchResult], max_shops: int, per_domain: int = 2) -> list[list[SearchResult]]:
    """Hasta ``per_domain`` URLs por dominio (fichas primero, listados al final, sin artículos),
    excluyendo los que no son tiendas. Si la primera URL no da el producto se prueba la siguiente."""
    groups: dict[str, list[SearchResult]] = {}
    seen_urls: set[str] = set()
    for r in results:
        d = r.domain
        if d in NOT_SHOPS or not r.url.startswith("http") or r.url in seen_urls or url_kind(r.url) == "article":
            continue
        seen_urls.add(r.url)
        if d not in groups and len(groups) >= max_shops:
            continue
        groups.setdefault(d, []).append(r)
    rank = {"product": 0, "listing": 1}
    return [sorted(g, key=lambda r: rank[url_kind(r.url)])[:per_domain] for g in groups.values()]


def shop_candidates(results: list[SearchResult], max_shops: int) -> list[SearchResult]:
    """Mejor resultado de cada dominio (ver ``candidate_groups``)."""
    return [g[0] for g in candidate_groups(results, max_shops, per_domain=1)]


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
                 page_rating=prod.rating, page_rating_count=prod.rating_count, list_price=prod.list_price,
                 source=f"ficha ({prod.method})"), prod.text


def search_queries(query: str) -> list[str]:
    """Consultas al buscador: intención de compra, de oferta y la frase exacta del modelo."""
    q = " ".join(query.split())
    return [f"{q} comprar precio", f"{q} oferta tienda", f'"{q}" precio']


def discover_offers(query: str, search, fetcher: Fetcher, max_shops: int = 12,
                    errors: list[str] | None = None) -> list[tuple[Offer, str]]:
    """Ofertas encontradas visitando las tiendas que devuelve el buscador.
    Devuelve pares (oferta, texto de la ficha) — el texto sirve para buscar cupones."""
    errors = errors if errors is not None else []
    results: list[SearchResult] = []
    for q in search_queries(query):
        try:
            results += search(q)
        except FetchError as e:
            errors.append(f"Buscador ({getattr(search, 'name', '?')}): {e}. Si persiste, define "
                          "BRAVE_API_KEY o SERPAPI_KEY (ver README)")
    groups = candidate_groups(results, max_shops)

    def visit(group: list[SearchResult]):
        """Prueba las URLs del dominio en orden hasta que una sea la ficha del producto."""
        fail = None
        for r in group:
            try:
                o, t = offer_from_page(r, fetcher.get_text(r.url), query)
            except FetchError as e:
                fail = f"{r.domain}: {e}"
                if "robots" in str(e) or "403" in str(e):
                    break           # el dominio no deja leer: no insistir
                continue
            if o is not None:
                return o, t
        if fail:
            errors.append(fail)
        return None, ""

    with ThreadPoolExecutor(max_workers=6) as ex:
        pages = list(ex.map(visit, groups))
    return [(o, t) for o, t in pages if o is not None]
