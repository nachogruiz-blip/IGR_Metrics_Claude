import pytest
from conftest import fixture

from pricecheck.extract import extract_product, match_score, parse_price


@pytest.mark.parametrize("txt,val", [
    ("1.299,99 €", 1299.99), ("€1,299.99", 1299.99), ("19,90", 19.9), ("19.9", 19.9),
    ("1.299", 1299.0), ("1,299", 1299.0), ("299", 299.0), ("Precio: 2 499,00 €", 2499.0),
    ("1.234.567", 1234567.0), (49, 49.0), ("gratis", None), (None, None), ("12,5", 12.5),
])
def test_parse_price(txt, val):
    assert parse_price(txt) == val


def test_jsonld_graph_prefers_new_condition_and_reads_everything():
    p = extract_product(fixture("product_jsonld.html"))
    assert p.method == "jsonld"
    assert p.price == 299.0 and p.currency == "EUR" and p.condition == "nuevo"  # no el reacondicionado de 249
    assert p.in_stock is True and p.shipping == 4.99 and p.seller == "TiendaUno"
    assert p.brand == "Sony"
    assert p.rating == pytest.approx(4.6) and p.rating_count == 1234          # 9,2/10 → 4,6/5
    assert "BLACK15" in p.text and "FAKE999" not in p.text                     # sólo texto visible


def test_aggregate_offer_with_trailing_commas():
    p = extract_product(fixture("product_aggregate_trailing_comma.html"))
    assert p.price == 1199.5 and p.extra["high_price"] == 1299.0


def test_microdata_and_opengraph_fallbacks():
    m = extract_product(fixture("product_microdata.html"))
    assert (m.method, m.price, m.in_stock) == ("microdata", 319.9, False)
    o = extract_product(fixture("product_opengraph.html"))
    assert (o.method, o.price, o.currency) == ("opengraph", 305.0, "EUR")
    assert extract_product(fixture("no_price.html")) is None


def test_match_score_requires_model_tokens():
    assert match_score("Sony WH-1000XM5", "Auriculares Sony WH-1000XM5 Negro") == 1.0
    assert match_score("Sony WH-1000XM5", "Sony WH-1000XM4") == 0.0          # otro modelo
    assert match_score("Sony WH-1000XM5", "Funda rígida para auriculares Sony") == 0.0
    assert match_score("Sony WH-1000XM5", "SONY WH1000XM5 Auriculares") == 1.0   # sin guion
    assert match_score("Sony WH-1000XM5", "Sony WH-1000 XM5") == 1.0


def test_strikethrough_price_from_jsonld():
    p = extract_product(fixture("product_precio_ya_rebajado.html"))
    assert p.price == 215.2 and p.list_price == 269.0 and p.currency == "EUR"


def test_reference_price_from_text():
    from pricecheck.extract import reference_price
    assert reference_price("Antes 239,99 € Ahora 191,99 €", 191.99) == 239.99
    assert reference_price("PVP: 1.299,00 €", 999.0) == 1299.0
    assert reference_price("Antes 50 €", 191.99) is None                  # menor que el precio
    assert reference_price("Era 9.999 €", 191.99) is None                 # demasiado alejado


def test_accessories_for_the_product_are_rejected():
    from pricecheck.extract import is_accessory
    assert match_score("ghd chronos max", "Funda termorresistente compatible con ghd chronos max") == 0.0
    assert match_score("ghd chronos max", "Soporte para plancha ghd chronos max") == 0.0
    assert match_score("ghd chronos max", "Plancha ghd chronos max con funda") == 1.0   # incluye funda
    assert not is_accessory("funda iphone 16", "Funda iPhone 16 transparente")         # se busca la funda
