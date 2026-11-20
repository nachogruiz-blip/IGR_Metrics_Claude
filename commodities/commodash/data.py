"""Fuentes de datos: Yahoo Finance (contrato a contrato), CSV propio y generador sintético (demo).

Todas devuelven un **panel**: ``DataFrame`` con fechas en el índice, un ``pd.Period`` mensual de
entrega por columna y el cierre (*settlement*) de ese contrato, NaN si no cotizó.
``yfinance`` se importa de forma perezosa: tests y modo demo no lo necesitan.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .contracts import CATALOG, Commodity, delivery_months

CONFIG_PATH = Path(__file__).resolve().parent.parent / "commodities.json"
DEFAULT_CONFIG: dict[str, Any] = {
    "selected": ["brent", "wti", "natgas", "gold", "copper", "corn"],
    "history_years": 2,
}
HORIZON_MONTHS = 37  # cubre 3A rolling (M+36) y Cal A+2 en cualquier mes


# --------------------------------------------------------------------------- configuración
def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(DEFAULT_CONFIG)
    return {**DEFAULT_CONFIG, **cfg}


def save_config(cfg: dict[str, Any], path: Path = CONFIG_PATH) -> None:
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def contract_range(asof: pd.Timestamp, history_years: float) -> tuple[pd.Period, pd.Period]:
    """Primer y último mes de entrega necesarios para el histórico y los tramos más largos."""
    start = (asof - pd.DateOffset(months=int(12 * history_years))).to_period("M") + 1
    return start, asof.to_period("M") + HORIZON_MONTHS


# --------------------------------------------------------------------------- Yahoo Finance
def fetch_panel(c: Commodity, asof: pd.Timestamp | None = None,
                history_years: float = 2) -> pd.DataFrame:
    """Cierres diarios de todos los vencimientos de ``c`` en Yahoo (los que existan)."""
    import yfinance as yf

    asof = pd.Timestamp.today().normalize() if asof is None else asof
    first, last = contract_range(asof, history_years)
    months = delivery_months(first, last, c)
    tickers = {c.ticker(m): m for m in months}
    start = asof - pd.DateOffset(years=history_years) - pd.DateOffset(days=7)
    raw = yf.download(list(tickers), start=start.strftime("%Y-%m-%d"), interval="1d",
                      auto_adjust=False, group_by="ticker", progress=False, threads=True)
    cols = {}
    for t, m in tickers.items():
        try:
            s = (raw[t] if isinstance(raw.columns, pd.MultiIndex) else raw)["Close"]
        except KeyError:
            continue
        s = s.dropna()
        if len(s):
            cols[m] = s
    if not cols:
        return pd.DataFrame()
    panel = pd.DataFrame(cols)
    panel.index = pd.to_datetime(panel.index).tz_localize(None)
    return panel.sort_index().astype(float)


# --------------------------------------------------------------------------- CSV propio
_ALIASES = {"fecha": "date", "date": "date", "commodity": "commodity", "producto": "commodity",
            "entrega": "delivery", "delivery": "delivery", "vencimiento": "delivery",
            "precio": "price", "price": "price", "settlement": "price", "cierre": "price"}


def read_csv(source: str | Path | io.IOBase | bytes) -> dict[str, pd.DataFrame]:
    """CSV largo ``fecha, commodity, entrega, precio`` → ``{commodity: panel}``.

    ``entrega`` es el mes de entrega (``2027-01``, ``ene-27`` no: usar ISO). Sirve para curvas
    que no están en Yahoo contrato a contrato: TTF, electricidad (OMIP/EEX), CO2…
    """
    if isinstance(source, bytes):
        source = io.BytesIO(source)
    df = pd.read_csv(source, sep=None, engine="python")
    df = df.rename(columns={k: _ALIASES[k.strip().lower()] for k in df.columns
                            if k.strip().lower() in _ALIASES})
    missing = {"date", "commodity", "delivery", "price"} - set(df.columns)
    if missing:
        raise ValueError(f"faltan columnas en el CSV: {sorted(missing)}")
    df["date"] = pd.to_datetime(df["date"], dayfirst=False)
    df["delivery"] = pd.PeriodIndex(pd.to_datetime(df["delivery"].astype(str)), freq="M")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    out = {}
    for name, g in df.groupby("commodity"):
        panel = g.pivot_table(index="date", columns="delivery", values="price", aggfunc="last")
        panel.columns = pd.PeriodIndex(panel.columns, freq="M")
        out[str(name)] = panel.sort_index()
    return out


# --------------------------------------------------------------------------- modo demo
# precio inicial, vol. factor corto, reversión κ, vol. factor largo, carry anual, estacionalidad
_DEMO = {
    "brent": (78, 0.30, 1.5, 0.12, -0.04, 0.00), "wti": (74, 0.32, 1.5, 0.12, -0.04, 0.00),
    "natgas": (3.2, 0.55, 2.5, 0.15, 0.04, 0.14), "heating_oil": (2.5, 0.30, 1.5, 0.12, -0.03, 0.03),
    "rbob": (2.3, 0.32, 1.5, 0.12, -0.03, -0.05), "gold": (2600, 0.14, 0.5, 0.06, 0.045, 0.0),
    "silver": (30, 0.25, 0.8, 0.08, 0.045, 0.0), "copper": (4.3, 0.22, 1.0, 0.10, 0.015, 0.0),
    "corn": (430, 0.25, 1.5, 0.10, 0.05, 0.03), "wheat": (560, 0.28, 1.5, 0.10, 0.05, 0.02),
    "soybeans": (1050, 0.20, 1.5, 0.08, 0.01, 0.02),
}


def demo_panel(c: Commodity, end: pd.Timestamp | None = None, history_years: float = 2,
               seed: int = 11) -> pd.DataFrame:
    """Curvas sintéticas con un modelo de dos factores (Schwartz–Smith simplificado):

    log F(t, T) = log S₀ + X_t·e^{−κτ} + L_t + c·τ + a·cos(2π(mes(T) − 1)/12),

    con X Ornstein–Uhlenbeck (shocks cortos que se disipan a lo largo de la curva), L paseo
    aleatorio (nivel largo), c pendiente de *carry* (contango > 0) y a estacionalidad invernal.
    Cada contrato cotiza desde 48 meses antes de su entrega hasta el día 20 del mes anterior;
    sólo los meses de ``c.months``; un 2 % de cierres faltan al azar.
    """
    end = pd.Timestamp.today().normalize() if end is None else pd.Timestamp(end)
    s0, sig_x, kappa, sig_l, carry, season = _DEMO.get(c.key, (100, 0.25, 1.5, 0.1, 0.0, 0.0))
    rng = np.random.default_rng(seed + sum(map(ord, c.key)))
    dates = pd.bdate_range(end=end, periods=int(252 * history_years) + 5)
    first, last = contract_range(end, history_years)
    months = pd.PeriodIndex(delivery_months(first, last, c), freq="M")
    n, dt = len(dates), 1 / 252
    x = np.zeros(n)
    eps = rng.standard_normal((2, n))
    for i in range(1, n):  # OU exacto en tiempo discreto (n ~ 500: bucle temporal, no por contrato)
        x[i] = x[i - 1] * np.exp(-kappa * dt) + sig_x * np.sqrt(dt) * eps[0, i]
    lvl = np.cumsum(sig_l * np.sqrt(dt) * eps[1]) - 0.5 * sig_l ** 2 * dt * np.arange(n)

    mid = (months.to_timestamp() + pd.Timedelta(days=14)).to_numpy()
    tau = (mid[None, :] - dates.to_numpy()[:, None]) / np.timedelta64(365, "D")
    seas = season * np.cos(2 * np.pi * (np.asarray(months.month) - 1) / 12)
    logf = (np.log(s0) + x[:, None] * np.exp(-kappa * np.clip(tau, 0, None)) + lvl[:, None]
            + carry * tau + seas[None, :])
    expiry = (months - 1).to_timestamp() + pd.Timedelta(days=19)
    listed = (dates.to_numpy()[:, None] < expiry.to_numpy()[None, :]) & (tau < 4.0)
    listed &= rng.random(listed.shape) > 0.02
    return pd.DataFrame(np.where(listed, np.exp(logf), np.nan), index=dates, columns=months)
