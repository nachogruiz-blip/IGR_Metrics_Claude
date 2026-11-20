"""Descarga de datos (Yahoo Finance vía ``yfinance``) y proveedor sintético para modo demo.

``yfinance`` se importa de forma perezosa: la lógica de indicadores y los tests no lo necesitan.
"""

from __future__ import annotations

import json
import zlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

WATCHLIST_PATH = Path(__file__).resolve().parent.parent / "watchlist.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "tickers": ["AAPL", "MSFT", "NVDA", "ASML.AS", "SAN.MC", "ITX.MC", "IBE.MC"],
    "benchmarks": {".MC": "^IBEX", ".AS": "^STOXX50E", ".PA": "^STOXX50E",
                   ".DE": "^STOXX50E", ".MI": "^STOXX50E", "default": "^GSPC"},
}


# --------------------------------------------------------------------------- watchlist
def load_config(path: Path = WATCHLIST_PATH) -> dict[str, Any]:
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(DEFAULT_CONFIG)
    return {**DEFAULT_CONFIG, **cfg}


def save_config(cfg: dict[str, Any], path: Path = WATCHLIST_PATH) -> None:
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_tickers(text: str) -> list[str]:
    """Separa por comas, espacios o saltos de línea; mayúsculas; sin duplicados (orden estable)."""
    seen: dict[str, None] = {}
    for tok in text.replace(",", " ").split():
        seen.setdefault(tok.strip().upper(), None)
    return list(seen)


def benchmark_for(ticker: str, benchmarks: dict[str, str]) -> str:
    """Índice de referencia según el sufijo de mercado de Yahoo (``.MC`` → Ibex, …)."""
    for suffix, bench in benchmarks.items():
        if suffix != "default" and ticker.upper().endswith(suffix.upper()):
            return bench
    return benchmarks.get("default", "^GSPC")


# --------------------------------------------------------------------------- Yahoo Finance
def fetch_prices(tickers: list[str], period: str = "2y") -> dict[str, pd.DataFrame]:
    """OHLCV diario ajustado. Devuelve sólo los tickers con datos."""
    import yfinance as yf

    if not tickers:
        return {}
    raw = yf.download(tickers, period=period, interval="1d", auto_adjust=True,
                      group_by="ticker", progress=False, threads=True)
    out: dict[str, pd.DataFrame] = {}
    for t in tickers:
        try:
            df = raw[t] if isinstance(raw.columns, pd.MultiIndex) else raw
        except KeyError:
            continue
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
        if len(df) > 30:
            df.index = pd.to_datetime(df.index).tz_localize(None)
            out[t] = df.astype(float)
    return out


def fetch_info(ticker: str) -> dict[str, Any]:
    """Diccionario ``info`` de Yahoo (fundamentales y consenso). Vacío si falla."""
    import yfinance as yf

    try:
        return dict(yf.Ticker(ticker).info or {})
    except Exception:  # noqa: BLE001 — Yahoo falla de muchas maneras; degradamos a "sin datos"
        return {}


# --------------------------------------------------------------------------- modo demo
_DEMO_PROFILES = {  # tendencia anual del log-precio por tramo y volatilidad diaria anualizada
    "trend_up": (0.35, 0.25), "trend_down": (-0.35, 0.30), "sideways": (0.0, 0.18),
    "reversal": (None, 0.30),
}


def demo_prices(tickers: list[str], n_days: int = 520, seed: int = 7) -> dict[str, pd.DataFrame]:
    """OHLCV sintético con regímenes distintos por ticker (para probar la app sin red).

    log P = tendencia determinista + ruido AR(1) (φ = 0.9), de modo que el régimen elegido
    (alcista, bajista, lateral o giro a la baja) domina sobre el ruido. Los índices (``^…``)
    son laterales.
    """
    from scipy.signal import lfilter

    idx = pd.bdate_range(end=pd.Timestamp("2026-11-20"), periods=n_days)
    profiles = list(_DEMO_PROFILES)
    dt = 1 / 252
    out = {}
    for i, t in enumerate(tickers):
        rng = np.random.default_rng(seed + i)
        prof = "sideways" if t.startswith("^") else profiles[i % len(profiles)]
        mu, vol = _DEMO_PROFILES[prof]
        drift = np.full(n_days, mu if mu is not None else 0.5)
        if prof == "reversal":  # sube y cae con fuerza en los últimos cuatro meses
            drift[n_days - 85:] = -0.9
        eps = vol * np.sqrt(dt) * rng.standard_normal(n_days)
        noise = lfilter([1.0], [1.0, -0.9], eps)
        logp = np.cumsum(drift * dt) + noise
        close = 50.0 * (1 + i) * np.exp(logp)
        r = np.diff(logp, prepend=logp[0])
        intraday = vol * np.sqrt(dt) * np.abs(rng.standard_normal((2, n_days)))
        open_ = close * np.exp(-r * rng.uniform(0.2, 0.8, n_days))
        high = np.maximum(open_, close) * (1 + intraday[0])
        low = np.minimum(open_, close) * (1 - intraday[1])
        volume = rng.lognormal(15, 0.3, n_days) * np.where(r > 0, 1.15, 0.9)
        out[t] = pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close,
                               "Volume": volume}, index=idx)
    return out


def demo_info(ticker: str, price: float, seed: int = 0) -> dict[str, Any]:
    """Fundamentales sintéticos plausibles (claves con el formato de ``yfinance.info``)."""
    rng = np.random.default_rng(zlib.crc32(ticker.encode()) + seed)
    pe = float(rng.uniform(8, 45))
    target = price * float(rng.uniform(0.85, 1.35))
    return {
        "shortName": f"{ticker} (demo)", "sector": rng.choice(["Tecnología", "Banca", "Consumo",
                                                                "Utilities"]),
        "industry": "—", "currency": "EUR" if "." in ticker else "USD",
        "currentPrice": price, "marketCap": 1e11, "trailingPE": pe, "forwardPE": pe * 0.85,
        "trailingPegRatio": float(rng.uniform(0.6, 3.5)),
        "enterpriseToEbitda": float(rng.uniform(5, 30)),
        "priceToSalesTrailing12Months": float(rng.uniform(1, 12)),
        "priceToBook": float(rng.uniform(0.8, 10)),
        "freeCashflow": 1e11 * float(rng.uniform(-0.01, 0.08)),
        "dividendRate": price * float(rng.uniform(0, 0.05)),
        "returnOnEquity": float(rng.uniform(-0.05, 0.40)),
        "returnOnAssets": float(rng.uniform(-0.02, 0.15)),
        "grossMargins": float(rng.uniform(0.2, 0.7)), "operatingMargins": float(rng.uniform(0, 0.4)),
        "profitMargins": float(rng.uniform(-0.05, 0.3)), "revenueGrowth": float(rng.uniform(-0.1, 0.3)),
        "earningsGrowth": float(rng.uniform(-0.2, 0.4)), "debtToEquity": float(rng.uniform(10, 250)),
        "totalDebt": 3e10, "totalCash": float(rng.uniform(0.5e10, 4e10)), "ebitda": 1.5e10,
        "currentRatio": float(rng.uniform(0.7, 2.5)), "targetMeanPrice": target,
        "recommendationMean": float(rng.uniform(1.5, 3.5)), "numberOfAnalystOpinions": 20,
    }
