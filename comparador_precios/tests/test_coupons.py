import pytest

from pricecheck.coupons import dedupe, extract_coupons, search_coupons
from pricecheck.models import Coupon
from pricecheck.search import SearchResult


def test_code_with_percentage():
    c = extract_coupons("Usa el código AURORA10 y obtén un 10% de descuento.", source="t", verified=True)
    assert len(c) == 1 and c[0].code == "AURORA10" and c[0].pct == pytest.approx(0.10) and c[0].verified


def test_amount_and_minimum_purchase():
    c = extract_coupons("Cupón ENVIO5: 5 € de descuento en compras superiores a 50 €", source="t", verified=False)
    assert c[0].code == "ENVIO5" and c[0].amount == 5.0 and c[0].min_purchase == 50.0
    assert c[0].saving(40.0) == 0.0 and c[0].saving(60.0) == 5.0


def test_keyword_must_be_a_whole_word():
    assert extract_coupons("Barcode ABC1234 en la caja", source="t", verified=True) == []


def test_stopwords_and_lowercase_are_not_codes():
    assert extract_coupons("Código postal 28001 y cupón DESCUENTO para todos", source="t", verified=True) == []
    assert extract_coupons("introduce tu code aquí", source="t", verified=True) == []


def test_discount_without_code():
    c = extract_coupons("Liquidación: 30% de descuento sólo hoy.", source="t", verified=True)
    assert c[0].code is None and c[0].pct == pytest.approx(0.30)
    c = extract_coupons("Ahorra un 12% en tu pedido", source="t", verified=True)
    assert c[0].pct == pytest.approx(0.12)


def test_saving_never_exceeds_price():
    assert Coupon("x", "X", amount=500.0).saving(100.0) == 100.0
    assert Coupon("x", "X", pct=0.1, amount=5.0).saving(100.0) == 10.0  # el mayor de los dos


def test_search_coupons_filters_other_shops():
    res = [SearchResult("Cupones tiendauno", "https://cupones.example/a",
                        "Código TIENDA10: 10% de descuento en tiendauno."),
           SearchResult("Cupones OtraTienda", "https://cupones.example/b", "Código OTRA20 20% de descuento.")]
    c = search_coupons("tiendauno.example", lambda q: res)
    assert [x.code for x in c] == ["TIENDA10"] and not c[0].verified


def test_dedupe_prefers_verified():
    a = Coupon("a", "X10", pct=0.1, verified=False)
    b = Coupon("b", "X10", pct=0.1, verified=True)
    assert dedupe([a, b]) == [b]


# --------------------------------------------------------------------------- doble descuento
from pricecheck.coupons import already_applied, mark_applied  # noqa: E402
from pricecheck.models import Coupon  # noqa: E402


def _c(desc, code="BF20", pct=0.20, amount=None, min_purchase=None):
    return Coupon(desc, code, pct=pct, amount=amount, min_purchase=min_purchase, verified=True)


def test_coupon_already_in_strikethrough_price():
    """Caso GHD Chronos Max: 269 € tachado, 215,20 € mostrado y código del 20 %: ya aplicado."""
    assert already_applied(_c("20% de descuento con el código BF20"), 215.20, list_price=269.0)


def test_coupon_with_sale_price_in_sentence():
    assert already_applied(_c("Ahora 215,20 € con el código BF20"), 215.20)          # precio rebajado citado
    assert already_applied(_c("269,00 € −20% con el código BF20"), 215.20)          # precio original citado
    assert already_applied(_c("Precio con el código BF20 aplicado"), 215.20)        # lo dice la frase


def test_coupon_not_applied_when_no_evidence():
    assert not already_applied(_c("20% de descuento con el código BF20"), 269.0)
    assert not already_applied(_c("20% de descuento con el código BF20"), 269.0, list_price=279.0)  # rebaja pequeña
    # el mínimo de compra no se confunde con un precio
    assert not already_applied(_c("BF20: 20% en compras superiores a 269 €", min_purchase=269.0), 269.0)
    # el importe del cupón tampoco
    assert not already_applied(_c("20 € de descuento con el código BF20", pct=None, amount=20.0), 200.0)


def test_mark_applied_only_touches_codes():
    cs = mark_applied([_c("Ahora 215,20 € con el código BF20"), _c("20% de descuento", code=None)], 215.20)
    assert [c.applied for c in cs] == [True, False]
