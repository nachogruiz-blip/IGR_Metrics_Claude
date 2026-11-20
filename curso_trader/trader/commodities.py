"""Materias primas (curso §9): contratos, curva de futuros, roll yield y spreads."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Contract:
    name: str
    exchange: str
    unit: str          # unidad de cotización
    multiplier: float  # dólares por 1 unidad de precio cotizado
    tick: float        # salto mínimo de precio

    @property
    def tick_value(self) -> float:
        return self.multiplier * self.tick


# Especificaciones estándar (CME/ICE). Granos cotizan en centavos/bushel.
CONTRACTS: dict[str, Contract] = {
    "CL": Contract("WTI crudo", "NYMEX", "$/bbl", 1000, 0.01),
    "BZ": Contract("Brent", "ICE", "$/bbl", 1000, 0.01),
    "NG": Contract("Gas natural Henry Hub", "NYMEX", "$/MMBtu", 10_000, 0.001),
    "RB": Contract("Gasolina RBOB", "NYMEX", "$/gal", 42_000, 0.0001),
    "HO": Contract("Gasóleo de calefacción (ULSD)", "NYMEX", "$/gal", 42_000, 0.0001),
    "GC": Contract("Oro", "COMEX", "$/oz", 100, 0.10),
    "SI": Contract("Plata", "COMEX", "$/oz", 5000, 0.005),
    "HG": Contract("Cobre", "COMEX", "$/lb", 25_000, 0.0005),
    "ZC": Contract("Maíz", "CBOT", "¢/bu", 50, 0.25),
    "ZS": Contract("Soja", "CBOT", "¢/bu", 50, 0.25),
    "ZW": Contract("Trigo", "CBOT", "¢/bu", 50, 0.25),
    "LE": Contract("Ganado vivo", "CME", "¢/lb", 400, 0.025),
}

MONTH_CODES = dict(zip("FGHJKMNQUVXZ", range(1, 13)))


def contract_value(symbol: str, price: float) -> float:
    """Nocional de un contrato en dólares."""
    return CONTRACTS[symbol].multiplier * price


def futures_position_size(symbol: str, equity: float, risk_pct: float, entry: float, stop: float) -> int:
    """Contratos enteros tales que el stop cueste ``risk_pct`` del capital."""
    per_contract = abs(entry - stop) * CONTRACTS[symbol].multiplier
    return int(equity * risk_pct // per_contract)


def cost_of_carry_forward(spot: float, r: float, storage: float, conv_yield: float, t: float) -> float:
    """F = S·e^{(r + u − y)T}: financiación + almacenamiento − rendimiento de conveniencia."""
    return spot * math.exp((r + storage - conv_yield) * t)


def implied_convenience_yield(spot: float, fut: float, r: float, storage: float, t: float) -> float:
    """y = r + u − ln(F/S)/T."""
    return r + storage - math.log(fut / spot) / t


def roll_yield(f_near: float, f_far: float, t_near: float, t_far: float) -> float:
    """Roll yield anualizado ln(F_near/F_far)/(T_far − T_near): > 0 en backwardation."""
    return math.log(f_near / f_far) / (t_far - t_near)


def curve_shape(prices) -> str:
    """«contango» si la curva sube monótonamente, «backwardation» si baja, «mixta» si no."""
    d = np.diff(np.asarray(prices, float))
    if np.all(d > 0):
        return "contango"
    if np.all(d < 0):
        return "backwardation"
    return "mixta"


def roll_yield_curve(prices, maturities) -> pd.Series:
    """Roll yield anualizado entre vencimientos consecutivos."""
    p = np.asarray(prices, float)
    t = np.asarray(maturities, float)
    vals = np.log(p[:-1] / p[1:]) / np.diff(t)
    return pd.Series(vals, index=[f"{a:.2f}→{b:.2f}" for a, b in zip(t[:-1], t[1:])])


def basis(spot: float, fut: float) -> float:
    """Base = contado − futuro (convención de los mercados agrícolas)."""
    return spot - fut


def crack_spread_321(crude: float, gasoline: float, heating_oil: float) -> float:
    """Crack 3:2:1 en $/bbl: (2·RBOB·42 + HO·42 − 3·WTI)/3, con RBOB y HO en $/gal."""
    return (2 * gasoline * 42 + heating_oil * 42 - 3 * crude) / 3


def crush_spread(soybeans: float, meal: float, oil: float) -> float:
    """Board crush en $/bu: harina($/t corta)·0,022 + aceite(¢/lb)·0,11 − soja($/bu).

    Un bushel (60 lb) rinde ≈ 44 lb de harina (0,022 t cortas) y 11 lb de aceite.
    """
    return meal * 0.022 + oil * 0.11 - soybeans


def spark_spread(power: float, gas: float, heat_rate: float = 7.0) -> float:
    """Margen de una central de gas en $/MWh: precio eléctrico − heat_rate (MMBtu/MWh)·gas ($/MMBtu)."""
    return power - heat_rate * gas


def monthly_seasonality(close: pd.Series) -> pd.DataFrame:
    """Rentabilidad media, mediana y % de meses positivos por mes del calendario."""
    m = close.resample("ME").last().pct_change().dropna()
    g = m.groupby(m.index.month)
    return pd.DataFrame({"media": g.mean(), "mediana": g.median(), "pct_positivos": g.apply(lambda x: (x > 0).mean())})


def ratio_back_adjust(front: pd.Series, roll_ratio: pd.Series) -> pd.Series:
    """Serie continua ajustada por ratio.

    ``roll_ratio`` vale F_nuevo/F_viejo el día del roll (1 los demás). Los precios anteriores a cada
    roll se multiplican por el producto de ratios posteriores, de modo que la serie no tiene saltos
    artificiales y sus rentabilidades son las de mantener el contrato vivo.
    """
    rr = roll_ratio.reindex(front.index).fillna(1.0)
    factor = rr[::-1].cumprod()[::-1].shift(-1).fillna(1.0)
    return front * factor


def synthetic_curve(spot: float, maturities, r: float, storage: float, conv_yield: float) -> np.ndarray:
    t = np.asarray(maturities, float)
    return spot * np.exp((r + storage - conv_yield) * t)
