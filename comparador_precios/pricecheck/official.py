"""¿Es vendedor oficial? Dominios registrables y clasificación de la tienda.

Las listas son deliberadamente cortas y editables: ``Registry`` agrupa marcas → dominios
oficiales, marketplaces y minoristas conocidos. La app y los tests pueden pasar uno propio
(la demo usa dominios ficticios ``.example``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from .models import OfficialStatus

# Sufijos de dos niveles más comunes (subconjunto de la Public Suffix List).
_TWO_LEVEL = {"co.uk", "org.uk", "com.es", "org.es", "nom.es", "com.mx", "com.ar", "com.br",
              "com.au", "co.jp", "com.co", "com.pe", "com.tr", "co.za"}

BRAND_DOMAINS: dict[str, tuple[str, ...]] = {
    "apple": ("apple.com",), "samsung": ("samsung.com",), "sony": ("sony.es", "sony.com"),
    "lg": ("lg.com",), "xiaomi": ("mi.com", "xiaomi.com"), "huawei": ("huawei.com",),
    "google": ("store.google.com", "google.com"), "microsoft": ("microsoft.com", "xbox.com"),
    "nintendo": ("nintendo.es", "nintendo.com"), "playstation": ("playstation.com",),
    "lenovo": ("lenovo.com",), "hp": ("hp.com",), "dell": ("dell.com",), "asus": ("asus.com",),
    "acer": ("acer.com",), "msi": ("msi.com",), "logitech": ("logitech.com", "logitechg.com"),
    "bose": ("bose.es", "bose.com"), "jbl": ("jbl.com",), "sonos": ("sonos.com",),
    "garmin": ("garmin.com",), "dyson": ("dyson.es", "dyson.com"), "philips": ("philips.es", "philips.com"),
    "bosch": ("bosch-home.es", "bosch.com"), "rowenta": ("rowenta.es",), "cecotec": ("storececotec.com", "cecotec.es"),
    "lego": ("lego.com",), "nike": ("nike.com",), "adidas": ("adidas.es", "adidas.com"),
    "canon": ("canon.es", "canon.com"), "nikon": ("nikon.es",), "gopro": ("gopro.com",),
    "oneplus": ("oneplus.com",), "oppo": ("oppo.com",), "realme": ("realme.com",),
}

# Plataformas donde venden terceros. Valor: nombres con los que la propia plataforma aparece
# como vendedor («Vendido por Amazon»).
MARKETPLACES: dict[str, tuple[str, ...]] = {
    "amazon.es": ("amazon",), "amazon.com": ("amazon",), "amazon.de": ("amazon",),
    "amazon.fr": ("amazon",), "amazon.it": ("amazon",), "amazon.co.uk": ("amazon",),
    "ebay.es": (), "ebay.com": (), "aliexpress.com": ("aliexpress",), "miravia.es": (),
    "carrefour.es": ("carrefour",), "worten.es": ("worten",), "pccomponentes.com": ("pccomponentes",),
    "mediamarkt.es": ("mediamarkt", "media markt"), "fnac.es": ("fnac",),
    "elcorteingles.es": ("el corte ingles", "el corte inglés"), "backmarket.es": (),
    "wallapop.com": (), "temu.com": (), "shein.com": (),
}

KNOWN_RETAILERS: frozenset[str] = frozenset({
    "coolmod.com", "alternate.es", "ldlc.com", "beep.es", "app-informatica.com", "phonehouse.es",
    "eci.es", "decathlon.es", "leroymerlin.es", "ikea.com", "lidl.es", "alcampo.es",
    "boulanger.com", "currys.co.uk", "bestbuy.com", "game.es", "xtralife.com", "k-tuin.com",
    "macnificos.com", "tiendaazul.com", "redcoon.es", "electrocosto.com", "costco.es",
})


def registrable_domain(url_or_host: str) -> str:
    """«https://www.tienda.co.uk/x» → «tienda.co.uk»; «m.amazon.es» → «amazon.es»."""
    host = urlsplit(url_or_host).netloc if "//" in url_or_host else url_or_host.split("/")[0]
    host = host.lower().split("@")[-1].split(":")[0].strip(".")
    parts = host.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in _TWO_LEVEL:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


@dataclass
class Registry:
    brand_domains: dict[str, tuple[str, ...]] = field(default_factory=lambda: dict(BRAND_DOMAINS))
    marketplaces: dict[str, tuple[str, ...]] = field(default_factory=lambda: dict(MARKETPLACES))
    retailers: frozenset[str] = KNOWN_RETAILERS

    def official_domains(self, brand: str | None, extra: tuple[str, ...] = ()) -> set[str]:
        out = {registrable_domain(d) for d in extra if d}
        if brand:
            out |= {registrable_domain(d) for d in self.brand_domains.get(slug(brand), ())}
        return out

    def guess_brand(self, text: str) -> str | None:
        words = re.findall(r"[a-z0-9]+", text.lower())
        return next((w for w in words if w in self.brand_domains), None)


def classify(domain: str, brand: str | None, marketplace_seller: str | None = None, *,
             registry: Registry | None = None, official_domains: tuple[str, ...] = ()) -> OfficialStatus:
    """Clasifica la tienda respecto a la marca del producto (ver METODOLOGIA.md §3)."""
    reg = registry or Registry()
    dom = registrable_domain(domain)
    official = reg.official_domains(brand, official_domains)
    if dom in official:
        return OfficialStatus("oficial", f"{dom} es el dominio oficial de {brand or 'la marca'}")
    if dom in reg.marketplaces:
        own = reg.marketplaces[dom]
        seller = (marketplace_seller or "").strip()
        if not seller:
            return OfficialStatus("marketplace_tercero",
                                  f"{dom} es un marketplace y no consta quién vende: compruébalo en la ficha")
        s = seller.lower()
        if brand and slug(brand) and slug(brand) in slug(seller):
            return OfficialStatus("oficial", f"Tienda oficial de {brand} dentro de {dom} (vendedor «{seller}»)")
        if any(name in s for name in own):
            return OfficialStatus("marketplace_directo", f"Vendido por la propia plataforma ({seller})")
        return OfficialStatus("marketplace_tercero", f"Vendedor externo «{seller}» dentro de {dom}")
    if dom in reg.retailers:
        return OfficialStatus("minorista", f"{dom} es un minorista conocido")
    if brand and slug(brand) and slug(dom.split(".")[0]).startswith(slug(brand)) and len(slug(brand)) >= 3:
        return OfficialStatus("desconocido",
                              f"El dominio contiene «{brand}» pero no está en la lista de dominios oficiales: "
                              "podría ser oficial o una imitación")
    return OfficialStatus("desconocido", f"{dom} no está en ninguna lista")
