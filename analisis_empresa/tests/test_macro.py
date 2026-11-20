import re
import sys
import types

import numpy as np
import pandas as pd
import pytest

from analyst import core, data, macro, report, verdict
from analyst.common import Item, Pillar


@pytest.mark.parametrize("ticker,info,kind", [
    ("GC=F", {}, "commodity"), ("XAUUSD=X", {}, "commodity"), ("CL=F", {}, "commodity"),
    ("EURUSD=X", {}, "fx"), ("SAN.MC", {}, "equity"), ("XYZ", {"quoteType": "FUTURE"}, "commodity"),
])
def test_asset_type(ticker, info, kind):
    assert data.asset_type(ticker, info) == kind


def test_driver_set():
    assert data.driver_set("GC=F", "commodity") == "gold"
    assert data.driver_set("CL=F", "commodity") == "commodity"
    assert data.driver_set("EURUSD=X", "fx") == "fx"


def test_regress_recovers_beta_within_4_stderr():
    rng = np.random.default_rng(0)
    x = pd.Series(rng.normal(0, 0.02, 300))
    e = rng.normal(0, 0.01, 300)
    y = -0.6 * x + e
    beta, corr = macro.regress(y, x)
    se = e.std() / (x.std() * np.sqrt(len(x)))
    assert abs(beta + 0.6) < 4 * se and corr < -0.7


def test_demo_gold_sensitivities_have_expected_sign():
    cd = data.demo("DEMO-ORO")
    m = macro.analyze(cd.prices["Close"], cd.drivers, data.MACRO_DRIVERS["gold"], True)
    d = {s.name: s for s in m.drivers}
    dollar = d["Dólar (índice DXY)"]
    rates = d["Rendimiento del bono EE. UU. a 10 años"]
    assert dollar.beta < 0 and rates.beta < 0            # simulados con −0.5 y −0.04/pp
    assert dollar.move < 0 and dollar.implied > 0        # dólar baja ⇒ viento a favor
    assert np.isclose(dollar.implied, dollar.beta * dollar.move)
    assert not dollar.unusual and not rates.unusual
    assert "gold_silver_pct" in m.relative and 0 <= m.relative["gold_silver_pct"] <= 1
    assert -1 <= m.pillar.score <= 1
    assert m.rebased.iloc[0].dropna().round(6).eq(100).all()


def test_unusual_relationship_is_flagged():
    idx = pd.bdate_range("2023-01-02", periods=800)
    rng = np.random.default_rng(1)
    dxy = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.005, 800))), idx)
    gold = pd.Series(np.exp(np.log(dxy) * 1.0 + np.cumsum(rng.normal(0, 0.003, 800))), idx)
    spec = {"Dólar (índice DXY)": ("DX-Y.NYB", "price", -1)}
    m = macro.analyze(gold, {"Dólar (índice DXY)": dxy}, spec)
    assert m.drivers[0].beta > 0 and m.drivers[0].unusual
    assert any("inusual" in n for n in m.notes)


def test_verdict_uses_macro_pillar():
    p = lambda name, s: Pillar(name, [Item("x", "x", s, s)])  # noqa: E731
    out = verdict.decide(Pillar("b"), Pillar("r"), Pillar("v"), p("Técnico", 0.5), p("Riesgo", 0.0),
                         macro=p("Factores macro", 0.6), price=100, atr=2, sma20=98, sma50=95,
                         support=94, resistance=110, flags=[], fair_value=np.nan, analyst_target=108,
                         vol_pct=0.5, vol_trend=0.0, asof=pd.Timestamp("2026-11-20"), earnings_date=None)
    assert out.action == "COMPRAR" and out.headline.startswith("Factores macro")
    assert np.isnan(out.quality) and out.fundamental == pytest.approx(0.6)


def test_gold_report_has_macro_and_no_company_sections():
    a = core.analyze(data.demo("DEMO-ORO"))
    assert a.valuation is None and a.macro is not None and len(a.pillars) == 3
    md = report.to_markdown(a)
    assert "## 1. Factores macro" in md and "Balance y cuentas" not in md and "Valoración" not in md
    assert "## 3. Series temporales" in md and not re.search(r"\bnan\b", md, re.I)


def test_fetch_gold_with_fake_yahoo(monkeypatch):
    demo = data.demo("DEMO-ORO")
    syms = {sym: name for name, (sym, _, _) in data.MACRO_DRIVERS["gold"].items()}
    calls = []

    class Ticker:
        def __init__(self, t):
            self.t = t
            self.info = {"shortName": "Gold Dec 26", "quoteType": "FUTURE", "currency": "USD"}

        @property
        def income_stmt(self):
            calls.append("income")
            raise AssertionError("no debe pedir estados financieros de una materia prima")

        def history(self, period, auto_adjust=True):
            if self.t == "GC=F":
                df = demo.prices
            else:
                c = demo.drivers[syms[self.t]] if self.t in syms else demo.bench
                df = pd.DataFrame({"Open": c, "High": c, "Low": c, "Close": c, "Volume": 0.0})
            return df.tz_localize("America/New_York")

    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(Ticker=Ticker))
    cd = data.fetch("gc=f")
    assert cd.asset_type == "commodity" and not calls and cd.income.empty
    assert set(cd.drivers) == set(data.MACRO_DRIVERS["gold"])
    assert cd.risk_free == pytest.approx(cd.drivers["Rendimiento del bono EE. UU. a 10 años"].iloc[-1] / 100)
    a = core.analyze(cd)
    assert a.verdict.action in {"COMPRAR", "ESPERAR", "MANTENER", "VENDER"}
