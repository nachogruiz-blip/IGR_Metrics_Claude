"""Catálogo de commodities y nomenclatura de contratos de futuros (Yahoo Finance).

Un contrato se identifica por su **mes de entrega** (``pd.Period`` mensual). En Yahoo, el ticker
de cada vencimiento es ``<raíz><código de mes><aa>.<mercado>``: ``CLF27.NYM`` = WTI entrega
enero-2027 en NYMEX.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

MONTH_CODES = "FGHJKMNQUVXZ"  # enero … diciembre
ALL_MONTHS = tuple(range(1, 13))


@dataclass(frozen=True)
class Commodity:
    key: str
    name: str
    root: str            # raíz del ticker en Yahoo
    exchange: str        # sufijo de mercado en Yahoo (NYM, CMX, CBT, NYB…)
    unit: str
    group: str
    months: tuple[int, ...] = ALL_MONTHS  # meses de entrega cotizados
    weighting: str = "equal"  # "equal" (media simple) o "days" (por días de entrega)

    def ticker(self, month: pd.Period) -> str:
        return f"{self.root}{MONTH_CODES[month.month - 1]}{month.year % 100:02d}.{self.exchange}"

    def continuous(self) -> str:
        return f"{self.root}=F"


CATALOG: dict[str, Commodity] = {c.key: c for c in [
    Commodity("brent", "Brent", "BZ", "NYM", "USD/bbl", "Energía"),
    Commodity("wti", "WTI", "CL", "NYM", "USD/bbl", "Energía"),
    Commodity("natgas", "Gas natural Henry Hub", "NG", "NYM", "USD/MMBtu", "Energía",
              weighting="days"),
    Commodity("heating_oil", "Gasóleo (heating oil)", "HO", "NYM", "USD/gal", "Energía"),
    Commodity("rbob", "Gasolina RBOB", "RB", "NYM", "USD/gal", "Energía"),
    Commodity("gold", "Oro", "GC", "CMX", "USD/oz", "Metales", months=(2, 4, 6, 8, 10, 12)),
    Commodity("silver", "Plata", "SI", "CMX", "USD/oz", "Metales", months=(3, 5, 7, 9, 12)),
    Commodity("copper", "Cobre", "HG", "CMX", "USD/lb", "Metales"),
    Commodity("corn", "Maíz", "ZC", "CBT", "USc/bu", "Agrícolas", months=(3, 5, 7, 9, 12)),
    Commodity("wheat", "Trigo", "ZW", "CBT", "USc/bu", "Agrícolas", months=(3, 5, 7, 9, 12)),
    Commodity("soybeans", "Soja", "ZS", "CBT", "USc/bu", "Agrícolas",
              months=(1, 3, 5, 7, 8, 9, 11)),
]}


def custom(key: str) -> Commodity:
    """Entrada genérica para commodities que sólo llegan por CSV (TTF, electricidad, CO2…)."""
    return CATALOG.get(key) or Commodity(key, key, "", "", "", "CSV")


def delivery_months(first: pd.Period, last: pd.Period, commodity: Commodity) -> list[pd.Period]:
    """Meses de entrega cotizados entre ``first`` y ``last`` (incluidos)."""
    return [p for p in pd.period_range(first, last, freq="M") if p.month in commodity.months]
