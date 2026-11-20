import numpy as np
import pandas as pd
import pytest

from analyst import statements as st
from analyst.data import ALIASES, normalize_statement


def _frames(n=2, **cols):
    idx = pd.to_datetime([f"{2024 + k}-12-31" for k in range(n)])
    out = {}
    for kind in ("income", "balance", "cashflow"):
        out[kind] = pd.DataFrame({k: cols.get(k, [np.nan] * n) for k in ALIASES[kind]}, index=idx, dtype=float)
    return out["income"], out["balance"], out["cashflow"]


def test_normalize_statement_resolves_aliases_and_orders_years():
    raw = pd.DataFrame({pd.Timestamp("2025-12-31"): [200.0, 20.0, np.nan],
                        pd.Timestamp("2024-12-31"): [100.0, 10.0, np.nan]},
                       index=["Operating Revenue", "Net Income Common Stockholders", "EBIT"])
    out = normalize_statement(raw, "income")
    assert list(out.index.year) == [2024, 2025]
    assert out["revenue"].tolist() == [100.0, 200.0]
    assert out["net_income"].tolist() == [10.0, 20.0]
    assert out["ebit"].isna().all()


def test_piotroski_perfect_and_zero():
    good = _frames(net_income=[50, 80], total_assets=[1000, 1000], ocf=[60, 120],
                   long_term_debt=[300, 200], current_assets=[300, 400], current_liabilities=[200, 200],
                   shares_out=[100, 99], gross_profit=[300, 400], revenue=[1000, 1100])
    p = st.piotroski(*good)
    assert p.score == 9 and p.available == 9
    bad = _frames(net_income=[50, -10], total_assets=[1000, 1000], ocf=[60, -20],
                  long_term_debt=[200, 300], current_assets=[400, 300], current_liabilities=[200, 200],
                  shares_out=[100, 110], gross_profit=[400, 300], revenue=[1100, 1000])
    assert st.piotroski(*bad).score == 0


def test_altman_closed_form():
    inc, bal, _ = _frames(1, revenue=[1500], ebit=[150], current_assets=[400], current_liabilities=[250],
                          retained_earnings=[300], total_assets=[1000], total_liabilities=[600])
    z = st.altman_z(inc, bal, market_cap=900.0)
    assert z == pytest.approx(1.2 * 0.15 + 1.4 * 0.3 + 3.3 * 0.15 + 0.6 * 1.5 + 1.0 * 1.5)
    assert st.altman_zone(z) == "segura" and st.altman_zone(1.0) == "de riesgo de insolvencia"


def test_ratios_basic_identities():
    inc, bal, cf = _frames(2, revenue=[1000, 1100], ebit=[100, 132], ebitda=[150, 180],
                           net_income=[70, 88], total_debt=[400, 400], cash=[100, 130],
                           equity=[500, 600], total_assets=[1500, 1700], ocf=[90, 110], capex=[-30, -40])
    r = st.ratios(inc, bal, cf)
    assert r["revenue_growth"].iloc[-1] == pytest.approx(0.1)
    assert r["ebit_margin"].iloc[-1] == pytest.approx(0.12)
    assert r["net_debt_ebitda"].iloc[-1] == pytest.approx(270 / 180)
    assert r["roe"].iloc[-1] == pytest.approx(88 / 550)            # sobre patrimonio medio
    assert r["fcf"].iloc[-1] == pytest.approx(70)                  # FCF = OCF + capex si falta


def test_cagr():
    s = pd.Series([100.0, 121.0], index=pd.to_datetime(["2023-12-31", "2025-12-31"]))
    assert st.cagr(s) == pytest.approx(0.1, abs=2e-3)
    assert np.isnan(st.cagr(pd.Series([-1.0, 5.0], index=s.index)))


def test_bank_skips_industrial_ratios():
    from analyst import data

    cd = data.demo("DEMO-COMPRA")
    p = st.balance_pillar(cd.income, cd.balance, cd.cashflow, {"sector": "Financial Services"})
    assert p.get("altman_z") is None and p.get("current_ratio") is None
