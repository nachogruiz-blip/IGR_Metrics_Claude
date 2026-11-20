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
