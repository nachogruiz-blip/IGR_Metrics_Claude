"""Funciones de puntuación, agregación y señales sobre escenarios sintéticos."""

from math import erf, sqrt

import numpy as np
import pytest

from stockdash import data, fundamental, scoring, technical


def test_ramp_and_inverse():
    f = scoring.ramp(0.0, 0.2)
    assert f(-1) == -1 and f(0.1) == pytest.approx(0.0) and f(1) == 1
    g = scoring.ramp(4.0, 0.0)  # menor es mejor
    assert g(0.0) == 1 and g(4.0) == -1 and g(2.0) == pytest.approx(0.0)
    assert np.isnan(f(np.nan))


def test_positive_multiple_penalises_losses():
    f = scoring.positive_multiple(35, 10)
    assert f(-5) == -1 and f(10) == 1 and f(35) == -1


def test_aggregate_renormalises_missing():
    vals = {"roe": 0.25, "op_margin": 0.25}  # sólo bloque Calidad con +1
    total, blocks, cov, eff = scoring._aggregate(vals, scoring.FUNDAMENTAL, scoring.FUND_BLOCKS)
    assert total == pytest.approx(1.0) and set(blocks) == {"Calidad"}
    assert sum(w for _, w in eff.values()) == pytest.approx(1.0)
    assert cov == pytest.approx(2 / len(scoring.FUNDAMENTAL))


def test_contributions_sum_to_composite():
    px = data.demo_prices(["A", "^X"])
    snap = technical.snapshot(px["A"], px["^X"]["Close"])
    fund = fundamental.extract(data.demo_info("A", snap["price"]), snap["price"])
    a = scoring.assess(snap, fund, w_tech=0.7)
    assert sum(c.impact for c in a.contributions) == pytest.approx(a.composite)
    assert a.composite == pytest.approx(0.7 * a.technical + 0.3 * a.fundamental)


def test_signal_thresholds():
    assert scoring.classify_signal(0.6) == "Compra fuerte"
    assert scoring.classify_signal(0.2) == "Comprar"
    assert scoring.classify_signal(0.0) == "Mantener"
    assert scoring.classify_signal(-0.2) == "Vender"
    assert scoring.classify_signal(-0.9) == "Venta fuerte"


@pytest.fixture(scope="module")
def regimes():
    px = data.demo_prices(["UP", "DOWN", "SIDE", "REV", "^IDX"])
    return {t: scoring.assess(technical.snapshot(px[t], px["^IDX"]["Close"]), None)
            for t in ("UP", "DOWN", "SIDE", "REV")}


def test_regimes_are_recognised(regimes):
    assert regimes["UP"].outlook == "Alcista" and regimes["UP"].signal.startswith("Compra")
    assert regimes["DOWN"].outlook == "Bajista" and regimes["DOWN"].signal.startswith("Vend")
    assert regimes["SIDE"].outlook == "Lateral" and regimes["SIDE"].signal == "Mantener"
    assert regimes["REV"].outlook == "Bajista"  # el giro reciente pesa más que el año alcista


def test_probability_and_range(regimes):
    for a in regimes.values():
        phi = 0.5 * (1 + erf(scoring.KAPPA * a.outlook_score / sqrt(2)))
        assert a.prob_up == pytest.approx(phi)
        lo1, hi1 = a.range_1m
        lo3, hi3 = a.range_3m
        assert lo3 < lo1 < hi1 < hi3  # la incertidumbre crece con el horizonte
    assert regimes["UP"].prob_up > 0.5 > regimes["DOWN"].prob_up


def test_fundamental_extract_conventions():
    info = {"debtToEquity": 150.0, "trailingEps": -2.0, "currentPrice": 10.0,
            "dividendRate": 0.5, "targetMeanPrice": 12.0, "numberOfAnalystOpinions": 1,
            "totalDebt": 100.0, "totalCash": 40.0, "ebitda": 30.0}
    f = fundamental.extract(info)
    assert f["debt_equity"] == pytest.approx(1.5)
    assert f["pe_trailing"] == -1.0
    assert f["div_yield"] == pytest.approx(0.05)
    assert f["net_debt_ebitda"] == pytest.approx(2.0)
    assert f["target_upside"] == pytest.approx(0.2)
    # con < 3 analistas el consenso no puntúa
    px = data.demo_prices(["A"])["A"]
    a = scoring.assess(technical.snapshot(px), f)
    assert "target_upside" not in {c.key for c in a.contributions}


def test_watchlist_helpers():
    assert data.parse_tickers("aapl, msft\nSAN.MC aapl") == ["AAPL", "MSFT", "SAN.MC"]
    b = data.DEFAULT_CONFIG["benchmarks"]
    assert data.benchmark_for("SAN.MC", b) == "^IBEX"
    assert data.benchmark_for("AAPL", b) == "^GSPC"
