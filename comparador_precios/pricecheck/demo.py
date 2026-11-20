"""Datos de demostración sin red. TODO ES FICTICIO: marca «Aurora», tiendas en dominios
``.example`` (reservados, no existen). No se atribuyen problemas a empresas reales.

Resultados esperados (vigilados por ``tests/test_core.py``):
- ``aurora-audio.example`` → «oficial», cupón verificado AURORA10 (−10 %).
- ``mercadoglobal.example`` vendido por la plataforma → recomendada (la fiable más barata).
- ``chollazo-outlet.example`` → «riesgo»: precio anómalo + dominio de 45 días + fraude.
- ``tecnoprecio.example`` → «baja»: muchas quejas de entrega y devoluciones.
- ``audiofan.example`` → sin opiniones ⇒ como mucho «baja».
- Vendedor externo reacondicionado en el marketplace → excluido salvo ``include_used``.
"""

from __future__ import annotations

from datetime import date, timedelta

from .models import Coupon, Issue, Offer, Reputation
from .official import Registry
from .core import Sources

DEMO_QUERY = "Auriculares Aurora X5"
DEMO_BRAND = "Aurora"
TODAY = date(2026, 11, 1)

_REGISTRY = Registry(
    brand_domains={"aurora": ("aurora-audio.example",)},
    marketplaces={"mercadoglobal.example": ("mercadoglobal",)},
    retailers=frozenset({"megastore.example"}),
)


def _offers() -> list[tuple[Offer, str]]:
    t = "Auriculares inalámbricos Aurora X5 con cancelación de ruido"
    return [
        (Offer("Aurora (tienda oficial)", "aurora-audio.example", "https://aurora-audio.example/x5", 349.0,
               shipping=0.0, in_stock=True, title=t, brand="Aurora", page_rating=4.6, page_rating_count=812,
               source="demo"),
         "Envío gratis en 24 h. Usa el código AURORA10 y obtén un 10% de descuento en tu primer pedido."),
        (Offer("MegaStore", "megastore.example", "https://megastore.example/aurora-x5", 319.0, shipping=0.0,
               in_stock=True, title=t, brand="Aurora", page_rating=4.5, page_rating_count=2210, source="demo"),
         "Recógelo en tienda o recíbelo en casa."),
        (Offer("MercadoGlobal", "mercadoglobal.example", "https://mercadoglobal.example/dp/X5", 309.0,
               shipping=4.99, in_stock=True, title=t, brand="Aurora", marketplace_seller="MercadoGlobal",
               page_rating=4.4, page_rating_count=15400, source="demo"), ""),
        (Offer("MercadoGlobal", "mercadoglobal.example", "https://mercadoglobal.example/dp/X5?seller=adeals",
               239.0, shipping=6.99, in_stock=True, condition="reacondicionado", title=t + " (reacondicionado)",
               brand="Aurora", marketplace_seller="AudioDeals Shop", source="demo"), ""),
        (Offer("TecnoPrecio", "tecnoprecio.example", "https://tecnoprecio.example/p/aurora-x5", 329.0,
               shipping=5.95, in_stock=True, title=t, brand="Aurora", source="demo"), ""),
        (Offer("Chollazo Outlet", "chollazo-outlet.example", "https://chollazo-outlet.example/aurora-x5", 159.0,
               shipping=0.0, in_stock=True, title=t, brand="Aurora", source="demo"),
         "¡Liquidación! 55% de descuento sólo hoy."),
        (Offer("AudioFan", "audiofan.example", "https://audiofan.example/aurora-x5", 335.0, shipping=3.5,
               in_stock=None, title=t, brand="Aurora", source="demo"), ""),
    ]


def _issues(cat: str, n: int, src: str = "Trustpilot (demo)") -> list[Issue]:
    texts = {
        "entrega": "El pedido no ha llegado tras tres semanas y el seguimiento no se actualiza.",
        "devolucion": "Devolví el producto hace dos meses y sigo sin reembolso.",
        "fraude": "Estafa: pagué y nunca recibí nada, la web no responde.",
        "atencion": "Atención al cliente no contesta correos ni teléfono.",
        "producto": "Llegó con la caja golpeada y un auricular no funciona.",
    }
    return [Issue(cat, texts[cat], src, TODAY - timedelta(days=7 * i), 1.0) for i in range(n)]


_REPUTATION = {
    "aurora-audio.example": Reputation("aurora-audio.example", 4.2, 1800, 40, _issues("entrega", 1),
                                       3000, sources=["Trustpilot (demo)", "RDAP (demo)"]),
    "megastore.example": Reputation("megastore.example", 4.4, 25000, 40, _issues("entrega", 3),
                                    7000, sources=["Trustpilot (demo)", "RDAP (demo)"]),
    "mercadoglobal.example": Reputation("mercadoglobal.example", 3.9, 120000, 40,
                                        _issues("entrega", 3) + _issues("atencion", 1), 9000,
                                        sources=["Trustpilot (demo)", "RDAP (demo)"]),
    "tecnoprecio.example": Reputation("tecnoprecio.example", 2.1, 600, 40,
                                      _issues("entrega", 9) + _issues("devolucion", 5) + _issues("atencion", 3),
                                      2500, sources=["Trustpilot (demo)", "RDAP (demo)"]),
    "chollazo-outlet.example": Reputation("chollazo-outlet.example", 1.4, 38, 20,
                                          _issues("fraude", 5) + _issues("entrega", 4), 45,
                                          sources=["Trustpilot (demo)", "RDAP (demo)"]),
    "audiofan.example": Reputation("audiofan.example", None, 0, 0, [], 1200, sources=["RDAP (demo)"]),
}

_COUPONS = {
    "megastore.example": [Coupon("MEGA5: 5% de descuento en electrónica (agregador de cupones)", "MEGA5", pct=0.05,
                                 source="buscador (cupones-demo.example)", verified=False)],
    "tecnoprecio.example": [Coupon("20 € de descuento en compras superiores a 200 €", "TECNO20", amount=20.0,
                                   min_purchase=200.0, source="buscador (cupones-demo.example)", verified=False)],
}


def demo_sources() -> Sources:
    def reputation(domain: str, https: bool | None) -> Reputation:
        r = _REPUTATION[domain]
        return Reputation(r.domain, r.rating, r.review_count, r.reviews_analyzed, list(r.issues),
                          r.domain_age_days, https, list(r.sources), url=None)

    return Sources(offers=lambda q, errors: _offers(), reputation=reputation,
                   coupons=lambda d: list(_COUPONS.get(d, [])), registry=_REGISTRY,
                   names=("Datos de demostración (ficticios)",), demo=True)
