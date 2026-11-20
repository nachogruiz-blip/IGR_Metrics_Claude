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
