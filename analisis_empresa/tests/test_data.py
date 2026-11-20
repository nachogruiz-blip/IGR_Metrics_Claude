"""El camino «datos reales» con un ``yfinance`` simulado (los tests no usan la red)."""

import sys
import types

import numpy as np
import pandas as pd

from analyst import core, data


def _fake_yfinance(prices: pd.DataFrame, bench: pd.DataFrame) -> types.ModuleType:
    cols = [pd.Timestamp("2025-12-31"), pd.Timestamp("2024-12-31")]   # Yahoo: más reciente primero
    income = pd.DataFrame({cols[0]: [1100e6, 450e6, 150e6, 200e6, 10e6, 140e6, 35e6, 105e6, 1.05, 100e6],
                           cols[1]: [1000e6, 400e6, 130e6, 180e6, 11e6, 119e6, 30e6, 89e6, 0.89, 100e6]},
                          index=["Total Revenue", "Gross Profit", "Operating Income", "EBITDA",
                                 "Interest Expense", "Pretax Income", "Tax Provision", "Net Income",
                                 "Diluted EPS", "Diluted Average Shares"])
    balance = pd.DataFrame({cols[0]: [2000e6, 600e6, 300e6, 900e6, 1100e6, 150e6, 300e6, 250e6, 500e6, 100e6],
                            cols[1]: [1900e6, 550e6, 300e6, 900e6, 1000e6, 120e6, 320e6, 260e6, 420e6, 100e6]},
                           index=["Total Assets", "Current Assets", "Current Liabilities",
                                  "Total Liabilities Net Minority Interest", "Stockholders Equity",
                                  "Cash And Cash Equivalents", "Total Debt", "Long Term Debt",
                                  "Retained Earnings", "Ordinary Shares Number"])
    cash = pd.DataFrame({cols[0]: [160e6, -40e6, 120e6, -40e6], cols[1]: [140e6, -35e6, 105e6, -35e6]},
                        index=["Operating Cash Flow", "Capital Expenditure", "Free Cash Flow",
                               "Cash Dividends Paid"])

    class Ticker:
        def __init__(self, t):
            self.t = t
            self.info = {"shortName": "Prueba S.A.", "currency": "EUR", "sector": "Industrials",
                         "marketCap": 2e9, "sharesOutstanding": 100e6, "trailingPE": 19.0,
                         "beta": 1.1}
            self.income_stmt, self.balance_sheet, self.cashflow = income, balance, cash
            self.calendar = {"Earnings Date": [pd.Timestamp("2026-11-25").date()]}

        def history(self, period, auto_adjust=True):
            df = bench if self.t.startswith("^") else prices
            return df.assign(Dividends=0.0).tz_localize("Europe/Madrid")

    return types.SimpleNamespace(Ticker=Ticker)


def test_fetch_with_fake_yahoo(monkeypatch):
    demo = data.demo("DEMO-COMPRA")
    bench = demo.prices.copy()
    bench["Close"] = demo.bench
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yfinance(demo.prices, bench))
    cd = data.fetch("pru.mc")
    assert cd.ticker == "PRU.MC" and cd.bench_ticker == "^IBEX" and cd.prices.index.tz is None
    assert list(cd.income.index.year) == [2024, 2025]
    assert cd.income["revenue"].iloc[-1] == 1100e6 and cd.balance["equity"].iloc[0] == 1000e6
    assert cd.earnings_date == pd.Timestamp("2026-11-25")
    assert cd.risk_free == data.RISK_FREE_FALLBACK["EUR"]
    a = core.analyze(cd)
    assert np.isfinite(a.balance.score) and np.isfinite(a.valuation.fair_value)
    assert a.verdict.action in {"COMPRAR", "ESPERAR", "MANTENER", "VENDER"}


def test_benchmark_by_suffix():
    assert data.benchmark_for("SAN.MC") == "^IBEX"
    assert data.benchmark_for("SAP.DE") == "^GDAXI"
    assert data.benchmark_for("AAPL") == "^GSPC"
