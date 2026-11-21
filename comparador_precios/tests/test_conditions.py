"""Ofertas y cupones ligados a contratar un servicio (telefonía, fibra, suscripción…)."""

import pytest

from pricecheck.conditions import mentions_service, service_condition, tied_service


@pytest.mark.parametrize("txt", [
    "Samsung Galaxy S25 por 99 € con tarifa Fibra + Móvil",
    "Precio 199 € al contratar fibra",
    "Llévatelo por 0 € con tu línea móvil",
    "Precio exclusivo para clientes de fibra: 49 €",
    "1 € con permanencia de 24 meses",
    "Por 9 € con suscripción anual",
])
def test_service_condition_detects_tied_prices(txt):
    assert service_condition(txt)


@pytest.mark.parametrize("txt", [
    "Paga en 3 plazos de 83 €/mes",                                   # financiación de tienda
    "Suscríbete a nuestra newsletter y llévate un 10% en tu precio",  # newsletter
    "Bicicleta con fibra de carbono por 999 €",                       # material, no servicio
    "Envío gratis por compras de 30€",
    "Permanencia de 24 meses",                                         # no habla de precio
])
def test_service_condition_ignores_normal_shop_text(txt):
    assert service_condition(txt) is None


def test_tied_service_by_domain_title_or_page():
    assert "operadora" in tied_service("https://www.movistar.es/moviles/x")
    assert "título" in tied_service("tienda.example", "iPhone 16 128GB con tarifa ilimitada")
    assert "ficha" in tied_service("tienda.example", "iPhone 16", "Precio 1 € al contratar fibra 1Gb.")
    assert tied_service("tienda.example", "iPhone 16", "Precio 899 €. Envío gratis.") is None


def test_coupon_requiring_service():
    assert mentions_service("10% de descuento con el código FIBRA10 al contratar fibra")
    assert not mentions_service("10% de descuento con el código BF10")
