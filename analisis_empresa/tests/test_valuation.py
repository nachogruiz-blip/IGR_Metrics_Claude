import numpy as np
import pytest

from analyst import valuation as v


def test_dcf_reduces_to_gordon_with_constant_growth():
    fcf0, g, rate = 100.0, 0.02, 0.08
    assert np.isclose(v.dcf_ev(fcf0, g, g, rate), fcf0 * (1 + g) / (rate - g), rtol=1e-12)


def test_dcf_increases_with_growth_and_decreases_with_rate():
    assert v.dcf_ev(100, 0.10, 0.02, 0.08) > v.dcf_ev(100, 0.05, 0.02, 0.08)
    assert v.dcf_ev(100, 0.05, 0.02, 0.09) < v.dcf_ev(100, 0.05, 0.02, 0.08)
    assert np.isnan(v.dcf_ev(100, 0.05, 0.03, 0.03))


def test_implied_growth_inverts_dcf():
    fcf0, gT, rate, shares, nd = 500.0, 0.02, 0.085, 100.0, 1000.0
    price = (v.dcf_ev(fcf0, 0.07, gT, rate) - nd) / shares
    assert np.isclose(v.implied_growth(price, shares, nd, fcf0, gT, rate), 0.07, atol=1e-8)


def test_wacc_without_debt_is_cost_of_equity():
    w, ke = v.wacc(0.03, 1.2, 1e9, 0.0, 0.0)
    assert w == ke == pytest.approx(0.03 + 1.2 * v.ERP)


def test_wacc_with_debt_is_weighted():
    w, ke = v.wacc(0.03, 1.0, 600.0, 400.0, 20.0)       # k_d = 5 %
    assert w == pytest.approx(0.6 * ke + 0.4 * 0.05 * (1 - v.TAX))


def test_justified_pb_for_bank():
    import pandas as pd

    from analyst.data import ALIASES

    idx = pd.to_datetime(["2023-12-31", "2024-12-31", "2025-12-31"])
    inc = pd.DataFrame({k: np.nan for k in ALIASES["income"]}, index=idx)
    bal = pd.DataFrame({k: np.nan for k in ALIASES["balance"]}, index=idx)
    cf = pd.DataFrame({k: np.nan for k in ALIASES["cashflow"]}, index=idx)
    bal["equity"] = 1000.0
    bal["total_assets"] = 12_000.0
    inc["net_income"] = 120.0                              # ROE 12 %
    info = {"sector": "Financial Services", "sharesOutstanding": 100.0, "beta": 1.0,
            "currency": "EUR", "marketCap": 1000.0}
    out = v.analyze(info, inc, bal, cf, price=10.0, rf=0.03)
    ke, g = 0.03 + v.ERP, v.terminal_growth("EUR", 0.03)
    assert out.method == "P/VC justificado"
    assert out.fair_value == pytest.approx(10.0 * (0.12 - g) / (ke - g))
