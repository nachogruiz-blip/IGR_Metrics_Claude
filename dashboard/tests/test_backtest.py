"""Backtest: causalidad de las variables y proceso completo sobre datos sintéticos."""

import json

import numpy as np
import pandas as pd
import pytest

from stockdash import backtest, data, technical


@pytest.fixture(scope="module")
def prices():
    return data.demo_prices(["A", "B", "C", "D", "^GSPC"], n_days=700)


def test_features_are_causal(prices):
    # La fila i de features() calculada con todo el histórico debe coincidir con snapshot()
    # calculado con el histórico truncado en i: no hay información futura.
    df, bench = prices["A"], prices["^GSPC"]["Close"]
    full = technical.features(df, bench)
    for i in (300, 450, 699):
        snap = technical.snapshot(df.iloc[: i + 1], bench.iloc[: i + 1])
        row = full.iloc[i]
        for k, v in snap.items():
            assert row[k] == pytest.approx(v, rel=1e-9, abs=1e-12, nan_ok=True), k


def test_observations_forward_returns(prices):
    cfg = backtest.BacktestConfig(tickers=["A", "B"], benchmarks={"default": "^GSPC"})
    obs = backtest.observations(prices, cfg)
    assert set(obs["ticker"]) == {"A", "B"}
    assert (obs["session"].dt.year >= 2024).all()  # tras el calentamiento
    df = prices["A"]
    r = obs[obs["ticker"] == "A"].iloc[0]
    i = df.index.get_loc(r["session"])
    assert r["r_3m"] == pytest.approx(df["Close"].iloc[i + 63] / df["Close"].iloc[i] - 1)
    # la última observación no tiene futuro a 63 sesiones
    assert np.isnan(obs[obs["ticker"] == "A"]["r_3m"].iloc[-1])


def test_month_end_positions():
    idx = pd.bdate_range("2025-01-01", "2025-03-31")
    pos = backtest.month_end_positions(idx)
    assert [idx[p].strftime("%Y-%m-%d") for p in pos] == ["2025-01-31", "2025-02-28",
                                                          "2025-03-31"]


def test_portfolio_costs():
    obs = pd.DataFrame({
        "date": pd.to_datetime(["2025-01-31"] * 2 + ["2025-02-28"] * 2),
        "ticker": ["A", "B", "A", "B"], "score": [0.5, -0.5, -0.5, 0.5],
        "signal": ["Comprar", "Vender", "Vender", "Comprar"],
        "r_next": [0.10, 0.0, 0.0, 0.05]})
    p = backtest.portfolios(obs, cost_bps=100)
    # mes 1: entra en A (rotación 1); mes 2: sale de A y entra en B (rotación 2)
    assert p["senal"].tolist() == pytest.approx([0.10 - 0.01, 0.05 - 0.02])
    assert p["dif_q"].tolist() == pytest.approx([0.10, 0.05])


def test_run_writes_reproducible_outputs(prices, tmp_path):
    cfg = backtest.BacktestConfig(tickers=["A", "B", "C", "D"],
                                  benchmarks={"default": "^GSPC"}, name="t")
    s1 = backtest.run(prices, cfg, tmp_path / "1", {"origen_datos": "sintéticos"})
    s2 = backtest.run(prices, cfg, tmp_path / "2", {"origen_datos": "sintéticos"})
    for f in ("INFORME.md", "resumen.json", "observaciones.csv", "carteras.png"):
        assert (tmp_path / "1" / f).exists()
    assert json.dumps(s1, default=str) == json.dumps(s2, default=str)
    assert (tmp_path / "1" / "observaciones.csv").read_bytes() == \
        (tmp_path / "2" / "observaciones.csv").read_bytes()
    assert "Datos sintéticos" in (tmp_path / "1" / "INFORME.md").read_text()


def test_csv_roundtrip(prices, tmp_path):
    path = tmp_path / "p.csv.gz"
    backtest.to_long(prices).to_csv(path, index=False)
    back = backtest.from_long(pd.read_csv(path))
    pd.testing.assert_frame_equal(back["A"], prices["A"].rename_axis("date"),
                                  check_freq=False)
