import pytest

from pricecheck.official import Registry, classify, registrable_domain


@pytest.mark.parametrize("u,d", [
    ("https://www.tienda.co.uk/x", "tienda.co.uk"), ("m.amazon.es", "amazon.es"),
    ("https://store.google.com/es/product", "google.com"), ("HTTPS://WWW.Sony.ES:443/a", "sony.es"),
    ("tienda.com.es", "tienda.com.es"),
])
def test_registrable_domain(u, d):
    assert registrable_domain(u) == d


def test_official_brand_store():
    s = classify("www.sony.es", "Sony")
    assert s.status == "oficial"
    assert classify("tienda.example", "Sony", official_domains=("tienda.example",)).status == "oficial"


def test_marketplace_seller_variants():
    assert classify("amazon.es", "Sony", None).status == "marketplace_tercero"
    assert classify("amazon.es", "Sony", "Amazon EU S.à r.l.").status == "marketplace_directo"
    assert classify("amazon.es", "Sony", "Sony Official Store").status == "oficial"
    assert classify("amazon.es", "Sony", "GadgetsXYZ").status == "marketplace_tercero"


def test_retailer_unknown_and_lookalike():
    assert classify("coolmod.com", "Sony").status == "minorista"
    assert classify("tienda.example", "Sony").status == "desconocido"
    s = classify("sony-outlet-ofertas.com", "Sony")
    assert s.status == "desconocido" and "imitación" in s.reason


def test_guess_brand():
    assert Registry().guess_brand("Auriculares Sony WH-1000XM5") == "sony"
    assert Registry().guess_brand("Algo sin marca") is None
