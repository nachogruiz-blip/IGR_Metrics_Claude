"""Orquestación: ``CompanyData`` → ``Analysis`` (todos los pilares y el veredicto).

Acciones: balance, rentabilidad, valoración, técnico y riesgo. Materias primas y divisas
(``cd.is_equity`` falso): factores macro, técnico y riesgo (``valuation`` es ``None`` y los
pilares de balance y rentabilidad quedan vacíos).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import macro as macro_mod
from . import statements, technical, timeseries, valuation, verdict
from .common import Pillar, finite
from .data import MACRO_DRIVERS, CompanyData, driver_set


@dataclass
class Analysis:
    data: CompanyData
    ratios: object                  # pd.DataFrame de ratios por ejercicio (None si no hay)
    piotroski: statements.Piotroski
    balance: Pillar
    profitability: Pillar
    valuation: valuation.Valuation | None
    technical: technical.Technical
    timeseries: timeseries.TimeSeries
    verdict: verdict.Verdict
    macro: macro_mod.Macro | None = None

    @property
    def pillars(self) -> list[Pillar]:
        if self.macro is not None:
            return [self.macro.pillar, self.technical.pillar, self.timeseries.pillar]
        return [self.balance, self.profitability, self.valuation.pillar,
                self.technical.pillar, self.timeseries.pillar]


def analyze(cd: CompanyData) -> Analysis:
    inc, bal, cf, info = cd.income, cd.balance, cd.cashflow, cd.info
    ts = timeseries.analyze(cd.prices["Close"], cd.bench, cd.risk_free)
    tech = technical.analyze(cd.prices, cd.bench)
    last = tech.frame.iloc[-1]
    s = ts.stats
    vol_trend = s.get("garch_vol_1m", np.nan) / s.get("garch_long_run_vol", np.nan) - 1
    common = dict(price=cd.price, atr=tech.atr, sma20=float(last["sma20"]),
                  sma50=float(last["sma50"]), support=tech.support, resistance=tech.resistance,
                  flags=tech.flags, vol_pct=s.get("vol21_percentile", np.nan),
                  vol_trend=vol_trend, asof=cd.asof)

    if not cd.is_equity:
        key = driver_set(cd.ticker, cd.asset_type)
        mac = macro_mod.analyze(cd.prices["Close"], cd.drivers, MACRO_DRIVERS[key], key == "gold")
        empty = (Pillar("Balance y solvencia"), Pillar("Rentabilidad y crecimiento"), Pillar("Valoración"))
        # Sin objetivo de analistas: se usa el percentil 84 % del cono a 3 meses como referencia.
        target = float(ts.cone.loc["3 meses", "p84"])
        v = verdict.decide(*empty, tech.pillar, ts.pillar, fair_value=np.nan, analyst_target=target,
                           earnings_date=None, macro=mac.pillar, **common)
        return Analysis(cd, None, statements.Piotroski(0, 0, {}), empty[0], empty[1], None,
                        tech, ts, v, mac)

    beta = info.get("beta")
    if not finite(beta):
        beta = ts.stats.get("beta", np.nan)
    val = valuation.analyze(info, inc, bal, cf, cd.price, cd.risk_free, beta)
    bp = statements.balance_pillar(inc, bal, cf, info)
    pp = statements.profitability_pillar(inc, bal, cf, info)
    v = verdict.decide(
        bp, pp, val.pillar, tech.pillar, ts.pillar, fair_value=val.fair_value,
        analyst_target=float(info.get("targetMeanPrice") or np.nan),
        earnings_date=cd.earnings_date, ex_dividend_date=cd.ex_dividend_date, **common)
    rat = statements.ratios(inc, bal, cf) if len(inc) else None
    return Analysis(cd, rat, statements.piotroski(inc, bal, cf), bp, pp, val, tech, ts, v)
