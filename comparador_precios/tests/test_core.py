"""Orquestación: resultados de la demo y canalización real completa con FakeFetcher."""

import pytest
from conftest import fixture

from pricecheck import core
from pricecheck.demo import DEMO_BRAND, DEMO_QUERY, demo_sources
from pricecheck.http import FakeFetcher, FetchError
from pricecheck.models import Offer, Reputation
from pricecheck.report import to_markdown


@pytest.fixture(scope="module")
def demo():
    return core.check(DEMO_QUERY, demo_sources(), brand=DEMO_BRAND)


def by_dom(rep, dom, seller=None):
    return next(a for a in rep.assessments if a.offer.domain == dom
                and (seller is None or a.offer.marketplace_seller == seller))


def test_demo_expected_outcomes(demo):
    assert demo.recommended.offer.domain == "mercadoglobal.example"
    assert demo.recommended.official.status == "marketplace_directo"
    assert demo.cheapest.offer.domain == "chollazo-outlet.example"
    scam = by_dom(demo, "chollazo-outlet.example")
    assert scam.reliability.level == "riesgo" and scam.price_anomaly
    off = by_dom(demo, "aurora-audio.example")
    assert off.official.status == "oficial" and off.final_price == pytest.approx(349 * 0.9)
    assert by_dom(demo, "tecnoprecio.example").reliability.level == "baja"
    assert by_dom(demo, "audiofan.example").reliability.level == "baja"
    # cupones sin verificar no se restan del precio final
    mega = by_dom(demo, "megastore.example")
    assert mega.final_price == 319.0 and mega.price_with_any_coupon == pytest.approx(319 * 0.95)
    # descuento sin código anunciado en la ficha: no se resta dos veces
    assert scam.final_price == 159.0
    # orden ascendente por precio final (las ligadas a un servicio, al final)
    finals = [a.final_price for a in demo.assessments if not a.requires_service]
    assert finals == sorted(finals)
    assert all(a.offer.condition == "nuevo" for a in demo.assessments)


def test_demo_coupon_already_in_price_is_not_subtracted_twice(demo):
    fan = by_dom(demo, "audiofan.example")
    assert fan.offer.list_price is None                              # sólo en el texto de la ficha
    assert [(c.code, c.applied) for c in fan.coupons] == [("FAN10", True)]
    assert fan.final_price == pytest.approx(335.0 + 3.5)


def test_demo_offer_tied_to_service(demo):
    tel = by_dom(demo, "telered.example")
    assert tel.requires_service and "contratar" in tel.reliability.warnings[0]
    assert demo.assessments[-1] is tel                               # al final de la lista
    assert demo.recommended is not tel and demo.cheapest is not tel
    assert not tel.price_anomaly                                     # no entra en la mediana
    assert any("contratar" in n for n in demo.notes)


def test_ghd_like_page_does_not_double_discount():
    """Ficha con precio ya rebajado (JSON-LD + tachado) y el código anunciado: final = precio mostrado."""
    from pricecheck.http import FakeFetcher
    from pricecheck.search import SearchResult, discover_offers
    f = FakeFetcher({"https://tiendacinco.example/ghd": fixture("product_precio_ya_rebajado.html")})
    pairs = discover_offers("ghd chronos max", lambda q: [SearchResult("ghd", "https://tiendacinco.example/ghd")], f)
    s = core.Sources(offers=lambda q, e: pairs, reputation=lambda d, h: Reputation(d), coupons=lambda d: [])
    a = core.check("ghd chronos max", s).assessments[0]
    assert a.offer.price == 215.2 and a.offer.list_price == 269.0
    assert [(c.code, c.applied) for c in a.coupons] == [("BF20", True)]
    assert a.final_price == pytest.approx(215.2)                    # antes: 215,20 × 0,8 = 172,16 €


def test_demo_include_used():
    r = core.check(DEMO_QUERY, demo_sources(), brand=DEMO_BRAND, include_used=True)
    used = by_dom(r, "mercadoglobal.example", "AudioDeals Shop")
    assert used.official.status == "marketplace_tercero"
    assert any("externo" in w for w in used.reliability.warnings)


def test_used_offers_are_not_price_anomalies():
    r = core.check(DEMO_QUERY, demo_sources(), brand=DEMO_BRAND, include_used=True)
    assert not by_dom(r, "mercadoglobal.example", "AudioDeals Shop").price_anomaly
    assert by_dom(r, "chollazo-outlet.example").price_anomaly


def test_markdown_report(demo):
    md = to_markdown(demo)
    assert "Mejor opción fiable" in md and "ficticios" in md and "AURORA10" in md


def test_failing_sources_do_not_crash():
    def boom(*a):
        raise RuntimeError("caído")
    s = core.Sources(offers=lambda q, e: [(Offer("A", "a.example", "https://a.example/p", 10.0), "")],
                     reputation=boom, coupons=boom)
    r = core.check("x", s)
    assert len(r.assessments) == 1 and len(r.errors) == 2
    assert r.recommended is None and r.notes                       # sin datos ⇒ no se recomienda


def test_no_offers():
    s = core.Sources(offers=lambda q, e: [], reputation=lambda d, h: Reputation(d), coupons=lambda d: [])
    r = core.check("nada", s)
    assert r.assessments == [] and r.recommended is None and "No se encontró" in r.notes[0]


def test_currency_filter_and_dedupe():
    offers = [(Offer("A", "a.example", "https://a.example/1", 20.0), ""),
              (Offer("A", "a.example", "https://a.example/2", 15.0), ""),
              (Offer("B", "b.example", "https://b.example/1", 10.0, currency="USD"), "")]
    s = core.Sources(offers=lambda q, e: offers, reputation=lambda d, h: Reputation(d), coupons=lambda d: [])
    r = core.check("x", s)
    assert [a.offer.price for a in r.assessments] == [15.0]
    assert any("USD" in n for n in r.notes)


def test_live_pipeline_with_fake_fetcher(monkeypatch):
    """Toda la canalización real (DuckDuckGo → fichas → Trustpilot/RDAP → cupones) sin red."""
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    ddg = "https://html.duckduckgo.com/html/?q="
    f = FakeFetcher({
        ddg: fixture("ddg.html"),
        ddg + "%22tiendauno.example%22": fixture("ddg_issues.html"),
        ddg + "cup%C3%B3n+descuento+tiendauno.example": fixture("ddg_coupons.html"),
        "https://www.tiendauno.example/sony-wh1000xm5": fixture("product_jsonld.html"),
        "https://shop.tiendados.co.uk/": FetchError("HTTP 403"),
        "https://tiendatres.example/xm5": fixture("product_opengraph.html"),
        "https://blog.example/": fixture("no_price.html"),
        "https://fundas.example/": fixture("accessory.html"),
        "https://es.trustpilot.com/review/tiendauno.example": fixture("trustpilot.html"),
        "https://rdap.org/domain/tiendauno.example": fixture("rdap.json"),
    })
    r = core.check("Sony WH-1000XM5", core.live_sources(f))
    doms = [a.offer.domain for a in r.assessments]
    assert sorted(doms) == ["tiendatres.example", "tiendauno.example"]   # sin blog, funda ni 403
    assert r.brand == "sony"
    uno = by_dom(r, "tiendauno.example")
    assert uno.offer.total == pytest.approx(303.99)
    assert uno.final_price == pytest.approx(303.99 - 0.15 * 299)          # BLACK15 de la ficha
    assert {c.code for c in uno.coupons} >= {"BLACK15", "TIENDA10", "ENVIO5"}
    assert uno.reputation.rating == 3.8 and uno.reputation.domain_age_days > 3000
    cats = [i.category for i in uno.reputation.issues]
    assert cats.count("entrega") == 2 and "fraude" in cats                # Trustpilot + buscador
    assert uno.official.status == "desconocido"
    assert any("tiendados" in e for e in r.errors)
    assert by_dom(r, "tiendatres.example").reliability.level == "baja"    # sin opiniones


def test_http_fetcher_skips_robots_for_apis(monkeypatch):
    """robots.txt se consulta para páginas, no para APIs (SerpAPI, Brave, RDAP)."""
    from pricecheck.http import HttpFetcher

    f = HttpFetcher()
    seen = []

    class Resp:
        status_code, text = 200, '{"ok": 1}'

    monkeypatch.setattr(f._s, "get", lambda url, **kw: seen.append(url) or Resp())
    monkeypatch.setattr(f, "_allowed", lambda url: False)       # robots.txt lo prohíbe todo
    monkeypatch.setattr("pricecheck.http.MIN_INTERVAL", 0.0)
    assert f.get_json("https://api.example/x") == {"ok": 1}
    with pytest.raises(FetchError, match="robots"):
        f.get_text("https://tienda.example/p")
