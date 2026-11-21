import json

from conftest import fixture

from pricecheck.search import parse_ddg, parse_serpapi_shopping, shop_candidates


def test_parse_ddg_decodes_redirects_and_skips_ads():
    res = parse_ddg(fixture("ddg.html"))
    assert res[0].url == "https://www.tiendauno.example/sony-wh1000xm5"
    assert res[0].domain == "tiendauno.example" and "mejor precio" in res[0].snippet
    assert all("y.js" not in r.url for r in res)


def test_shop_candidates_one_per_domain_without_non_shops():
    c = shop_candidates(parse_ddg(fixture("ddg.html")), max_shops=10)
    doms = [r.domain for r in c]
    assert doms[:3] == ["tiendauno.example", "tiendados.co.uk", "tiendatres.example"]
    assert "youtube.com" not in doms and len(doms) == len(set(doms))
    assert len(shop_candidates(parse_ddg(fixture("ddg.html")), max_shops=2)) == 2


def test_parse_serpapi_shopping():
    offers = parse_serpapi_shopping(json.loads(fixture("serpapi_shopping.json")))
    assert len(offers) == 2                                     # el que no tiene precio se descarta
    o = offers[0]
    assert (o.domain, o.price, o.shipping, o.seller) == ("tiendacuatro.example", 289.0, 0.0, "TiendaCuatro")
    assert offers[1].condition == "reacondicionado"


def test_candidate_groups_keep_fallback_url_and_skip_articles():
    from pricecheck.search import SearchResult, candidate_groups, search_queries, url_kind
    res = [SearchResult("x", "https://t.example/buscar?q=xm5"), SearchResult("x", "https://t.example/p/xm5"),
           SearchResult("x", "https://t.example/blog/review-xm5"), SearchResult("x", "https://u.example/xm5"),
           SearchResult("x", "https://t.example/p/xm5")]
    g = candidate_groups(res, max_shops=5)
    assert [r.url for r in g[0]] == ["https://t.example/p/xm5", "https://t.example/buscar?q=xm5"]  # ficha primero
    assert [r.url for r in g[1]] == ["https://u.example/xm5"]
    assert url_kind("https://t.example/blog/a") == "article" and url_kind("https://t.example/c/audio") == "listing"
    assert search_queries("Sony  WH-1000XM5")[-1] == '"Sony WH-1000XM5" precio'


def test_discover_offers_falls_back_to_second_url():
    from pricecheck.http import FakeFetcher
    from pricecheck.search import SearchResult, discover_offers
    res = [SearchResult("a", "https://t.example/listado"), SearchResult("b", "https://t.example/ficha")]
    f = FakeFetcher({"https://t.example/listado": fixture("no_price.html"),
                     "https://t.example/ficha": fixture("product_jsonld.html")})
    out = discover_offers("Sony WH-1000XM5", lambda q: res, f)
    assert len(out) == 1 and out[0][0].url == "https://t.example/ficha"


def test_serpapi_old_price():
    data = {"shopping_results": [{"title": "ghd chronos max", "source": "T", "link": "https://t.example/g",
                                  "extracted_price": 215.2, "extracted_old_price": 269.0}]}
    assert parse_serpapi_shopping(data)[0].list_price == 269.0
