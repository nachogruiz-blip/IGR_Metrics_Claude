import re

import pandas as pd
import pytest

from analyst import core, data, report, verdict
from analyst.common import Item, Pillar


def _pillar(name, score, **values):
    p = Pillar(name, [Item("x", "x", score, score)])
    for k, v in values.items():
        p.items.append(Item(k, k, v, float("nan")))
    return p


def _decide(q, val, t, flags=(), earnings=None, z=3.5):
    asof = pd.Timestamp("2026-11-20")
    return verdict.decide(
        _pillar("Balance y solvencia", q, altman_z=z), _pillar("Rentabilidad y crecimiento", q),
        _pillar("Valoración", val), _pillar("Técnico", t), _pillar("Riesgo", 0.0),
        price=100, atr=2, sma20=97, sma50=95, support=92, resistance=110, flags=list(flags),
        fair_value=130, analyst_target=120, vol_pct=0.5, vol_trend=0.0, asof=asof,
        earnings_date=None if earnings is None else asof + pd.Timedelta(days=earnings))


@pytest.mark.parametrize("q,val,t,expected", [
    (0.7, 0.6, 0.6, "COMPRAR"), (0.7, 0.6, -0.6, "ESPERAR"), (-0.6, -0.6, -0.5, "VENDER"),
    (-0.6, -0.6, 0.6, "VENDER"), (0.0, 0.0, 0.0, "MANTENER"), (0.0, 0.1, 0.6, "COMPRAR"),
    (0.0, 0.0, -0.6, "VENDER"),
])
def test_decision_matrix(q, val, t, expected):
    assert _decide(q, val, t).action == expected


def test_overbought_turns_buy_into_wait_for_pullback():
    out = _decide(0.7, 0.6, 0.6, flags=["RSI en sobrecompra (78)"])
    assert out.action == "ESPERAR" and out.bias == "compra"
    assert "entrada_desde" in out.levels and any("Retroceso" in w for w in out.wait_for)


def test_earnings_soon_turns_buy_into_wait():
    out = _decide(0.7, 0.6, 0.6, earnings=5)
    assert out.action == "ESPERAR" and "Resultados" in out.wait_for[0]
    assert _decide(0.7, 0.6, 0.6, earnings=40).action == "COMPRAR"


def test_distress_vetoes_buy():
    out = _decide(0.7, 0.6, 0.6, z=1.2)
    assert out.action == "ESPERAR" and any("Altman" in w for w in out.warnings)


def test_buy_levels_are_ordered():
    lv = _decide(0.7, 0.6, 0.6).levels
    assert lv["stop"] < lv["precio"] < lv["objetivo_1"] <= lv["objetivo_2"]


@pytest.mark.parametrize("ticker,action", [
    ("DEMO-COMPRA", "COMPRAR"), ("DEMO-ESPERA", "ESPERAR"), ("DEMO-VENDE", "VENDER"),
    ("DEMO-CARA", "ESPERAR"),
])
def test_demo_profiles_end_to_end(ticker, action):
    a = core.analyze(data.demo(ticker))
    assert a.verdict.action == action
    for p in a.pillars:
        assert -1 <= p.score <= 1
    md = report.to_markdown(a)
    assert ticker in md and action in md and not re.search(r"\bnan\b", md, re.I)


def test_cli_demo(tmp_path, capsys):
    from analyst.__main__ import main

    out = tmp_path / "x.md"
    assert main(["DEMO-ESPERA", "--demo", "--out", str(out)]) == 0
    assert "ESPERAR" in out.read_text(encoding="utf-8")
