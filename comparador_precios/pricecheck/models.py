"""Tipos de datos compartidos. Sin lógica de red ni de puntuación.

Convenciones: precios en unidades monetarias (float, no céntimos), puntuaciones de fiabilidad en
[0, 100], valoraciones normalizadas a escala 0–5, porcentajes como fracción (0.10 = 10 %).
``None`` significa «dato no disponible», nunca cero.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

# Categorías de problemas reportados (orden = prioridad al clasificar).
ISSUE_CATEGORIES = ("fraude", "entrega", "devolucion", "producto", "atencion")
ISSUE_LABELS = {
    "fraude": "Fraude / estafa",
    "entrega": "Entrega / envío",
    "devolucion": "Devolución / reembolso",
    "producto": "Producto defectuoso o distinto",
    "atencion": "Atención al cliente",
}

# Estado de «vendedor oficial».
OFFICIAL_LABELS = {
    "oficial": "Tienda oficial de la marca",
    "minorista": "Minorista conocido",
    "marketplace_directo": "Marketplace (vendido por la plataforma)",
    "marketplace_tercero": "Marketplace (vendedor externo)",
    "desconocido": "Tienda no catalogada",
}

LEVELS = ("alta", "media", "baja", "riesgo")
LEVEL_STYLE = {  # icono + texto: el color nunca va solo
    "alta": ("✅", "Alta"),
    "media": ("🟡", "Media"),
    "baja": ("🟠", "Baja"),
    "riesgo": ("⛔", "Riesgo"),
}


def finite(x) -> bool:
    return x is not None and isinstance(x, (int, float)) and math.isfinite(x)


@dataclass
class Offer:
    """Una oferta concreta del producto en una tienda."""

    seller: str                      # nombre comercial («MegaStore»)
    domain: str                      # dominio registrable («megastore.es»)
    url: str
    price: float                     # precio del artículo, sin envío
    currency: str = "EUR"
    shipping: float | None = None    # None = desconocido; 0.0 = gratis
    in_stock: bool | None = None
    condition: str = "nuevo"         # nuevo | reacondicionado | usado
    title: str = ""
    brand: str | None = None
    marketplace_seller: str | None = None   # vendedor real dentro de un marketplace
    page_rating: float | None = None        # valoración del PRODUCTO en la ficha (0–5)
    page_rating_count: int | None = None
    source: str = ""                 # de dónde salió la oferta (proveedor)
    list_price: float | None = None  # precio de referencia/tachado («antes 239,99 €»), si consta
    tied_service: str | None = None  # el precio exige contratar algo (tarifa, fibra…): motivo

    @property
    def total(self) -> float:
        return self.price + (self.shipping or 0.0)


@dataclass
class Coupon:
    """Cupón o descuento. ``verified`` = visto en la propia web del vendedor."""

    description: str
    code: str | None = None
    pct: float | None = None         # fracción: 0.10 = 10 %
    amount: float | None = None      # descuento fijo en moneda
    min_purchase: float | None = None
    source: str = ""
    url: str | None = None
    verified: bool = False
    applied: bool = False            # el precio mostrado YA incluye este descuento (no restar)
    requires_service: bool = False   # exige contratar un servicio (tarifa, fibra…): no se resta

    @property
    def usable(self) -> bool:
        """Puede restarse del precio: tiene código, no está ya aplicado y no exige contratar nada."""
        return bool(self.code) and not self.applied and not self.requires_service

    def saving(self, price: float) -> float:
        if self.min_purchase is not None and price < self.min_purchase:
            return 0.0
        s = 0.0
        if finite(self.pct):
            s = max(s, price * self.pct)
        if finite(self.amount):
            s = max(s, self.amount)
        return min(s, price)


@dataclass
class Issue:
    """Problema reportado por un cliente (reseña negativa clasificada)."""

    category: str                    # una de ISSUE_CATEGORIES
    text: str
    source: str
    date: date | None = None
    rating: float | None = None


@dataclass
class Reputation:
    """Reputación de la TIENDA (no del producto)."""

    domain: str
    rating: float | None = None      # 0–5
    review_count: int = 0
    reviews_analyzed: int = 0        # reseñas leídas para buscar problemas
    issues: list[Issue] = field(default_factory=list)
    domain_age_days: int | None = None
    https: bool | None = None
    sources: list[str] = field(default_factory=list)
    url: str | None = None

    def issue_counts(self) -> dict[str, int]:
        out = {c: 0 for c in ISSUE_CATEGORIES}
        for i in self.issues:
            out[i.category] = out.get(i.category, 0) + 1
        return out


@dataclass
class OfficialStatus:
    status: str                      # clave de OFFICIAL_LABELS
    reason: str

    @property
    def label(self) -> str:
        return OFFICIAL_LABELS[self.status]


@dataclass
class Reliability:
    score: float                     # 0–100 (NaN si no hay ningún dato)
    level: str                       # uno de LEVELS
    components: dict[str, float]     # componente → valor en [0, 1] (NaN = sin dato)
    warnings: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        icon, text = LEVEL_STYLE[self.level]
        return f"{icon} {text}"


@dataclass
class Assessment:
    """Una oferta con todo lo averiguado sobre ella."""

    offer: Offer
    reputation: Reputation
    official: OfficialStatus
    coupons: list[Coupon]
    reliability: Reliability
    price_anomaly: bool = False

    @property
    def requires_service(self) -> bool:
        """El precio sólo vale contratando otro servicio (telefonía, fibra, suscripción…)."""
        return self.offer.tied_service is not None

    def best_coupon(self, verified_only: bool = False) -> Coupon | None:
        """Mejor cupón CON CÓDIGO que se pueda restar. Los descuentos sin código anunciados en la
        ficha, y los cupones cuyo efecto ya se ve en el precio (``applied``), se consideran
        incluidos en el precio mostrado: no se restan dos veces. Los que exigen contratar un
        servicio tampoco se restan."""
        cands = [c for c in self.coupons if c.usable and (c.verified or not verified_only)]
        cands = [c for c in cands if c.saving(self.offer.price) > 0]
        return max(cands, key=lambda c: c.saving(self.offer.price), default=None)

    @property
    def final_price(self) -> float:
        """Total (precio + envío) menos el mejor descuento VERIFICADO."""
        c = self.best_coupon(verified_only=True)
        return self.offer.total - (c.saving(self.offer.price) if c else 0.0)

    @property
    def price_with_any_coupon(self) -> float:
        """Total menos el mejor cupón, verificado o no (optimista)."""
        c = self.best_coupon()
        return self.offer.total - (c.saving(self.offer.price) if c else 0.0)


@dataclass
class PriceReport:
    query: str
    brand: str | None
    assessments: list[Assessment]    # ordenadas por final_price ascendente
    median_total: float | None
    recommended: Assessment | None   # la más barata con fiabilidad ≥ media y en stock
    cheapest: Assessment | None
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    demo: bool = False
