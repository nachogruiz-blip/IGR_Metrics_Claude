"""Orquestación: ``CompanyData`` → ``Analysis`` (todos los pilares y el veredicto)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import statements, technical, timeseries, valuation, verdict
from .common import Pillar, finite
from .data import CompanyData


@dataclass
class Analysis:
    data: CompanyData
    ratios: object                  # pd.DataFrame de ratios por ejercicio
    piotroski: statements.Piotroski
    balance: Pillar
    profitability: Pillar
    valuation: valuation.Valuation
    technical: technical.Technical
    timeseries: timeseries.TimeSeries
    verdict: verdict.Verdict

    @property
    def pillars(self) -> list[Pillar]:
        return [self.balance, self.profitability, self.valuation.pillar,
                self.technical.pillar, self.timeseries.pillar]


def analyze(cd: CompanyData) -> Analysis:
    inc, bal, cf, info = cd.income, cd.balance, cd.cashflow, cd.info
    ts = timeseries.analyze(cd.prices["Close"], cd.bench, cd.risk_free)
    tech = technical.analyze(cd.prices, cd.bench)
    beta = info.get("beta")
    if not finite(beta):
        beta = ts.stats.get("beta", np.nan)
    val = valuation.analyze(info, inc, bal, cf, cd.price, cd.risk_free, beta)
    bp = statements.balance_pillar(inc, bal, cf, info)
    pp = statements.profitability_pillar(inc, bal, cf, info)
    last = tech.frame.iloc[-1]
    s = ts.stats
    vol_trend = s.get("garch_vol_1m", np.nan) / s.get("garch_long_run_vol", np.nan) - 1
    v = verdict.decide(
        bp, pp, val.pillar, tech.pillar, ts.pillar, price=cd.price, atr=tech.atr,
        sma20=float(last["sma20"]), sma50=float(last["sma50"]), support=tech.support,
        resistance=tech.resistance, flags=tech.flags, fair_value=val.fair_value,
        analyst_target=float(info.get("targetMeanPrice") or np.nan),
        vol_pct=s.get("vol21_percentile", np.nan), vol_trend=vol_trend, asof=cd.asof,
        earnings_date=cd.earnings_date, ex_dividend_date=cd.ex_dividend_date)
    rat = statements.ratios(inc, bal, cf) if len(inc) else None
    return Analysis(cd, rat, statements.piotroski(inc, bal, cf), bp, pp, val, tech, ts, v)
