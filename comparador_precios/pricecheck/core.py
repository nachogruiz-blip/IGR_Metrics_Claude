"""Orquestación: búsqueda → ofertas → reputación/cupones por tienda → fiabilidad → informe.

``check`` no sabe de red: recibe un ``Sources`` con tres funciones (ofertas, reputación,
cupones). ``live_sources`` construye las reales; ``demo.demo_sources`` las sintéticas.
"""

from __future__ import annotations

import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable

from .coupons import dedupe, extract_coupons, search_coupons
from .http import FetchError, Fetcher, HttpFetcher
from .models import Assessment, Coupon, Offer, PriceReport, Reputation, finite
from .official import Registry, classify
from .reputation import fetch_reputation
from .scoring import anomalies, reliability
from .search import SerpApiShopping, default_search, discover_offers

OffersFn = Callable[[str, list], list[tuple[Offer, str]]]   # (búsqueda, errores) → [(oferta, texto ficha)]


@dataclass
class Sources:
    offers: OffersFn
    reputation: Callable[[str, bool | None], Reputation]       # (dominio, https) → reputación
    coupons: Callable[[str], list[Coupon]]                     # dominio → cupones no verificados
    registry: Registry = field(default_factory=Registry)
    names: tuple[str, ...] = ()
    demo: bool = False


def live_sources(fetcher: Fetcher | None = None, max_shops: int = 12) -> Sources:
    """Fuentes reales. Usa SerpAPI (Google Shopping) si hay ``SERPAPI_KEY`` y Brave si hay
    ``BRAVE_API_KEY``; si no, DuckDuckGo + visita de fichas."""
    fetcher = fetcher or HttpFetcher()
    search = default_search(fetcher)
    serp_key = os.environ.get("SERPAPI_KEY")
    shopping = SerpApiShopping(fetcher, serp_key) if serp_key else None

    def offers(query: str, errors: list) -> list[tuple[Offer, str]]:
        out = discover_offers(query, search, fetcher, max_shops=max_shops, errors=errors)
        if shopping is not None:
            try:
                out += [(o, "") for o in shopping(query)]
            except FetchError as e:
                errors.append(f"Google Shopping: {e}")
        return out

    def safe_search(q: str):
        try:
            return search(q)
        except FetchError:
            return []

    names = (search.name, "Trustpilot", "RDAP") + ((shopping.name,) if shopping else ())
    return Sources(offers=offers,
                   reputation=lambda d, https: fetch_reputation(d, fetcher, safe_search, https),
                   coupons=lambda d: search_coupons(d, safe_search),
                   names=names)


def _dedupe_offers(pairs: list[tuple[Offer, str]]) -> list[tuple[Offer, str]]:
    """Una oferta por (dominio, vendedor de marketplace): la de menor total."""
    best: dict[tuple, tuple[Offer, str]] = {}
    for o, t in pairs:
        key = (o.domain, (o.marketplace_seller or "").lower())
        if key not in best or o.total < best[key][0].total:
            best[key] = (o, t or best.get(key, (None, ""))[1])
    return list(best.values())


def check(query: str, sources: Sources, *, brand: str | None = None,
          official_domains: tuple[str, ...] = (), include_used: bool = False,
          currency: str = "EUR") -> PriceReport:
    errors: list[str] = []
    notes: list[str] = []
    pairs = sources.offers(query, errors)

    kept = []
    for o, t in pairs:
        if o.currency.upper() != currency:
            notes.append(f"{o.domain}: precio en {o.currency}, excluido (no se convierten divisas)")
        elif o.condition != "nuevo" and not include_used:
            notes.append(f"{o.domain}: producto {o.condition}, excluido (activa «incluir usados»)")
        else:
            kept.append((o, t))
    pairs = _dedupe_offers(kept)
    offers = [o for o, _ in pairs]

    if brand is None:
        brands = Counter(o.brand.strip().lower() for o in offers if o.brand)
        brand = brands.most_common(1)[0][0] if brands else sources.registry.guess_brand(query)

    med, flags = anomalies([o.total for o in offers])
    domains = sorted({o.domain for o in offers})
    https_by_dom = {o.domain: o.url.startswith("https://") for o in offers}

    def per_domain(d: str):
        try:
            rep = sources.reputation(d, https_by_dom.get(d))
        except Exception as e:  # noqa: BLE001 — una fuente rota no tumba el informe
            errors.append(f"Reputación de {d}: {e}")
            rep = Reputation(domain=d, https=https_by_dom.get(d))
        try:
            cps = sources.coupons(d)
        except Exception as e:  # noqa: BLE001
            errors.append(f"Cupones de {d}: {e}")
            cps = []
        return d, rep, cps

    with ThreadPoolExecutor(max_workers=6) as ex:
        info = {d: (rep, cps) for d, rep, cps in ex.map(per_domain, domains)}

    assessments = []
    for (o, text), anomalous in zip(pairs, flags):
        rep, cps = info[o.domain]
        page_cps = extract_coupons(text, source="ficha del vendedor", verified=True, url=o.url) if text else []
        status = classify(o.domain, brand, o.marketplace_seller, registry=sources.registry,
                          official_domains=official_domains)
        rel = reliability(rep, status, price_anomaly=anomalous)
        assessments.append(Assessment(offer=o, reputation=rep, official=status,
                                      coupons=dedupe(page_cps + cps), reliability=rel,
                                      price_anomaly=anomalous))
    assessments.sort(key=lambda a: (a.final_price, -a.reliability.score if finite(a.reliability.score) else 0.0))

    trusted = [a for a in assessments if a.reliability.level in ("alta", "media") and a.offer.in_stock is not False]
    recommended = min(trusted, key=lambda a: a.final_price, default=None)
    cheapest = assessments[0] if assessments else None
    if not offers:
        notes.append("No se encontró ninguna oferta del producto. Prueba con el modelo exacto "
                     "(p. ej. «Sony WH-1000XM5») o revisa los errores de las fuentes.")
    elif recommended is None:
        notes.append("Ninguna tienda alcanza fiabilidad media: revisa los avisos antes de comprar.")
    return PriceReport(query=query, brand=brand, assessments=assessments, median_total=med,
                       recommended=recommended, cheapest=cheapest, errors=errors, notes=notes,
                       demo=sources.demo)
