"""Obtención de datos de una empresa: precios, índice de referencia, ``info``, estados
financieros anuales y calendario (resultados, dividendo).

Fuente real: Yahoo Finance vía ``yfinance`` (importado de forma perezosa para que los tests no
lo necesiten). Modo demo: empresas sintéticas con perfiles conocidos (``DEMO_PROFILES``).

Convenciones:
- Precios: ``DataFrame`` OHLCV diario, índice de fechas ascendente sin zona horaria.
- Estados financieros: ``DataFrame`` con **una fila por ejercicio** (índice = fecha de cierre,
  ascendente) y columnas canónicas (``revenue``, ``net_income``…). Las claves de Yahoo cambian
  con el tiempo; ``ALIASES`` recoge las variantes conocidas y ``normalize_statement`` las
  resuelve. Una partida ausente queda como NaN.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- partidas contables
ALIASES: dict[str, dict[str, list[str]]] = {
    "income": {
        "revenue": ["Total Revenue", "Operating Revenue"],
        "gross_profit": ["Gross Profit"],
        "ebit": ["EBIT", "Operating Income"],
        "ebitda": ["EBITDA", "Normalized EBITDA"],
        "interest_expense": ["Interest Expense", "Interest Expense Non Operating"],
        "pretax_income": ["Pretax Income"],
        "tax_provision": ["Tax Provision"],
        "net_income": ["Net Income", "Net Income Common Stockholders",
                       "Net Income From Continuing Operation Net Minority Interest"],
        "eps": ["Diluted EPS", "Basic EPS"],
        "shares": ["Diluted Average Shares", "Basic Average Shares"],
    },
    "balance": {
        "total_assets": ["Total Assets"],
        "current_assets": ["Current Assets"],
        "current_liabilities": ["Current Liabilities"],
        "total_liabilities": ["Total Liabilities Net Minority Interest", "Total Liabilities"],
        "equity": ["Stockholders Equity", "Common Stock Equity",
                   "Total Equity Gross Minority Interest"],
        "cash": ["Cash And Cash Equivalents",
                 "Cash Cash Equivalents And Short Term Investments"],
        "inventory": ["Inventory"],
        "receivables": ["Accounts Receivable", "Receivables"],
        "total_debt": ["Total Debt"],
        "long_term_debt": ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"],
        "retained_earnings": ["Retained Earnings"],
        "shares_out": ["Ordinary Shares Number", "Share Issued"],
    },
    "cashflow": {
        "ocf": ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
        "capex": ["Capital Expenditure"],
        "fcf": ["Free Cash Flow"],
        "dividends": ["Cash Dividends Paid", "Common Stock Dividend Paid"],
        "buybacks": ["Repurchase Of Capital Stock", "Common Stock Payments"],
        "sbc": ["Stock Based Compensation"],
    },
}

BENCHMARKS = {".MC": "^IBEX", ".AS": "^AEX", ".PA": "^FCHI", ".DE": "^GDAXI", ".MI": "FTSEMIB.MI",
              ".L": "^FTSE", ".SW": "^SSMI", ".LS": "PSI20.LS", "default": "^GSPC"}

# Tipo libre de riesgo de respaldo (bono a 10 años) si no se puede descargar; editable en la app.
RISK_FREE_FALLBACK = {"USD": 0.042, "EUR": 0.027, "GBP": 0.045, "CHF": 0.007}


def benchmark_for(ticker: str) -> str:
    for suffix, bench in BENCHMARKS.items():
        if suffix != "default" and ticker.upper().endswith(suffix):
            return bench
    return BENCHMARKS["default"]


def normalize_statement(raw: pd.DataFrame | None, kind: str) -> pd.DataFrame:
    """Estado de Yahoo (partidas × fechas, más reciente primero) → ejercicios × claves canónicas.

    Para cada clave canónica toma el primer alias presente con algún dato. Las columnas sin
    ningún dato (ejercicios vacíos que Yahoo a veces añade) se descartan.
    """
    keys = list(ALIASES[kind])
    if raw is None or raw.empty:
        return pd.DataFrame(columns=keys, dtype=float)
    raw = raw.apply(pd.to_numeric, errors="coerce")
    out = pd.DataFrame(index=pd.to_datetime(raw.columns), columns=keys, dtype=float)
    for key, names in ALIASES[kind].items():
        for name in names:
            if name in raw.index and raw.loc[name].notna().any():
                row = raw.loc[name]
                if isinstance(row, pd.DataFrame):  # partida duplicada
                    row = row.iloc[0]
                out[key] = row.to_numpy(dtype=float)
                break
    out = out.dropna(how="all").sort_index()
    out.index = out.index.tz_localize(None) if out.index.tz is not None else out.index
    return out


# --------------------------------------------------------------------------- contenedor
@dataclass
class CompanyData:
    """Todo lo que necesita el análisis de una empresa."""

    ticker: str
    prices: pd.DataFrame
    info: dict[str, Any]
    income: pd.DataFrame
    balance: pd.DataFrame
    cashflow: pd.DataFrame
    bench_ticker: str = ""
    bench: pd.Series | None = None
    earnings_date: pd.Timestamp | None = None
    ex_dividend_date: pd.Timestamp | None = None
    risk_free: float = 0.03
    demo: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return str(self.info.get("longName") or self.info.get("shortName") or self.ticker)

    @property
    def currency(self) -> str:
        return str(self.info.get("currency") or "")

    @property
    def price(self) -> float:
        return float(self.prices["Close"].iloc[-1])

    @property
    def asof(self) -> pd.Timestamp:
        return pd.Timestamp(self.prices.index[-1])


# --------------------------------------------------------------------------- descarga real
def _clean_prices(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.droplevel(1, axis=1) if df.columns.nlevels > 1 else df
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"]).astype(float)
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df.sort_index()


def _first_date(v) -> pd.Timestamp | None:
    if isinstance(v, (list, tuple)):
        v = v[0] if v else None
    try:
        ts = pd.Timestamp(v)
        return None if pd.isna(ts) else ts.tz_localize(None) if ts.tz is not None else ts
    except (TypeError, ValueError):
        return None


def fetch(ticker: str, years: int = 5) -> CompanyData:
    """Descarga de Yahoo Finance. Lanza ``ValueError`` si no hay precios para el ticker."""
    import yfinance as yf

    ticker = ticker.strip().upper()
    tk = yf.Ticker(ticker)
    prices = tk.history(period=f"{years}y", auto_adjust=True)
    if prices is None or len(prices) < 60:
        raise ValueError(f"Sin precios para «{ticker}». ¿Es un ticker de Yahoo? "
                         "(p. ej. SAN.MC, ITX.MC, AAPL, ASML.AS)")
    prices = _clean_prices(prices)
    warnings: list[str] = []

    def safe(fn, default, label: str):
        try:
            v = fn()
            return default if v is None else v
        except Exception as e:  # noqa: BLE001 — Yahoo falla de muchas maneras
            warnings.append(f"No se pudo obtener {label}: {e}")
            return default

    info = dict(safe(lambda: tk.info, {}, "la ficha (info)"))
    income = normalize_statement(safe(lambda: tk.income_stmt, None, "la cuenta de resultados"), "income")
    balance = normalize_statement(safe(lambda: tk.balance_sheet, None, "el balance"), "balance")
    cashflow = normalize_statement(safe(lambda: tk.cashflow, None, "el estado de flujos"), "cashflow")
    cal = safe(lambda: tk.calendar, {}, "el calendario") or {}
    if isinstance(cal, pd.DataFrame):
        cal = {c: cal[c].iloc[0] for c in cal.columns} if not cal.empty else {}
    earnings = _first_date(cal.get("Earnings Date"))
    exdiv = _first_date(cal.get("Ex-Dividend Date"))
    if earnings is None and info.get("earningsTimestamp"):
        earnings = pd.Timestamp(int(info["earningsTimestamp"]), unit="s")

    bench_ticker = benchmark_for(ticker)
    bench = safe(lambda: yf.Ticker(bench_ticker).history(period=f"{years}y", auto_adjust=True), None,
                 f"el índice {bench_ticker}")
    bench = _clean_prices(bench)["Close"] if bench is not None and len(bench) > 60 else None

    currency = str(info.get("currency") or ("EUR" if "." in ticker else "USD"))
    rf = RISK_FREE_FALLBACK.get(currency, 0.03)
    if currency == "USD":
        tnx = safe(lambda: yf.Ticker("^TNX").history(period="5d")["Close"], None, "el bono a 10 años")
        if tnx is not None and len(tnx):
            rf = float(tnx.iloc[-1]) / 100.0
    if income.empty:
        warnings.append("Yahoo no devuelve estados financieros para este valor.")
    return CompanyData(ticker, prices, info, income, balance, cashflow, bench_ticker, bench,
                       earnings, exdiv, rf, False, warnings)


# --------------------------------------------------------------------------- modo demo
# Perfil: tendencia anual del log-precio en los tramos (antiguo, último ~5 meses), volatilidad
# anual, y parámetros contables (crecimiento de ventas, margen EBIT, deuda/EBITDA, PER objetivo).
DEMO_PROFILES: dict[str, dict[str, Any]] = {
    "DEMO-COMPRA": dict(drift=(0.22, 0.30), vol=0.24, growth=0.10, margin=0.22, lev=0.8,
                        pe=13.0, sector="Industrials", name="Calidad Barata S.A."),
    "DEMO-ESPERA": dict(drift=(0.25, -0.55), vol=0.28, growth=0.09, margin=0.24, lev=1.0,
                        pe=14.0, sector="Technology", name="Buena Empresa en Corrección S.A."),
    "DEMO-VENDE": dict(drift=(-0.10, -0.45), vol=0.40, growth=-0.08, margin=0.03, lev=6.5,
                       pe=60.0, sector="Consumer Cyclical", name="Endeudada y Cara S.A."),
    "DEMO-CARA": dict(drift=(0.05, 0.0), vol=0.20, growth=0.03, margin=0.12, lev=2.0,
                      pe=38.0, sector="Consumer Defensive", name="Lateral y Cara S.A."),
}
DEMO_TODAY = pd.Timestamp("2026-11-20")


def _garch_noise(rng: np.random.Generator, n: int, vol: float) -> np.ndarray:
    """Innovaciones diarias GARCH(1,1) con t de Student (ν = 5), volatilidad media ``vol``."""
    alpha, beta = 0.08, 0.90
    var_l = (vol ** 2) / 252
    omega = var_l * (1 - alpha - beta)
    z = rng.standard_t(5, n) / np.sqrt(5 / 3)
    eps = np.empty(n)
    s2 = var_l
    for t in range(n):  # recursión temporal (una sola serie): no vectorizable
        eps[t] = np.sqrt(s2) * z[t]
        s2 = omega + alpha * eps[t] ** 2 + beta * s2
    return eps


def _demo_prices(rng: np.random.Generator, prof: dict, n: int, start: float,
                 market: np.ndarray | None = None) -> pd.DataFrame:
    """OHLCV sintético; ``market`` (log-rendimientos sin media) añade riesgo sistemático."""
    idx = pd.bdate_range(end=DEMO_TODAY, periods=n)
    old, recent = prof["drift"]
    drift = np.full(n, old)
    drift[n - 105:] = recent
    eps = _garch_noise(rng, n, prof["vol"])
    # Ruido AR(1) sobre el log-precio (φ = 0.97): el régimen elegido domina sobre el ruido.
    from scipy.signal import lfilter

    noise = lfilter([1.0], [1.0, -0.97], eps)
    logp = np.cumsum(drift / 252) + noise
    if market is not None:
        logp = logp + np.cumsum(market)
    close = start * np.exp(logp - logp[0])
    r = np.diff(np.log(close), prepend=np.log(close[0]))
    intraday = np.abs(eps) + prof["vol"] / np.sqrt(252) * 0.5 * np.abs(rng.standard_normal((2, n)))
    open_ = close * np.exp(-r * rng.uniform(0.2, 0.8, n))
    high = np.maximum(open_, close) * (1 + intraday[0])
    low = np.minimum(open_, close) * (1 - intraday[1])
    volume = rng.lognormal(14, 0.35, n) * np.where(r > 0, 1.15, 0.9)
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close,
                         "Volume": volume}, index=idx)


def _demo_statements(prof: dict, rng: np.random.Generator, years: int = 4):
    """Cuentas anuales coherentes con el perfil (cifras en millones)."""
    dates = pd.to_datetime([f"{2025 - years + 1 + k}-12-31" for k in range(years)])
    g, m, lev = prof["growth"], prof["margin"], prof["lev"]
    rev = 10_000 * (1 + g) ** np.arange(years) * rng.uniform(0.97, 1.03, years)
    # Márgenes con ligera mejora (empresas sanas) o deterioro (la endeudada).
    trend = np.linspace(-0.01, 0.01, years) * (1 if g > 0 else -3)
    ebit = rev * (m + trend)
    ebitda = ebit + rev * 0.05
    debt = np.full(years, lev * ebitda.mean()) * np.linspace(1.05, 0.95 if g > 0 else 1.2, years)
    rate = 0.04 if lev < 3 else 0.08
    interest = debt * rate
    pretax = ebit - interest
    tax = np.maximum(pretax, 0) * 0.25
    ni = pretax - tax
    shares = 1_000 * np.linspace(1.02, 1.0, years) if g > 0 else 1_000 * np.linspace(1.0, 1.08, years)
    ta = rev * 1.2
    cur_l = rev * 0.25
    cur_a = cur_l * (1.6 if lev < 3 else 0.85)
    cash = cur_a * 0.3
    tl = debt + cur_l + rev * 0.1
    equity = ta - tl
    ocf = ni * (1.25 if g > 0 else 0.6) + rev * 0.05
    capex = -rev * 0.05
    income = pd.DataFrame({
        "revenue": rev, "gross_profit": rev * (m + 0.25), "ebit": ebit, "ebitda": ebitda,
        "interest_expense": interest, "pretax_income": pretax, "tax_provision": tax,
        "net_income": ni, "eps": ni / shares, "shares": shares}, index=dates)
    balance = pd.DataFrame({
        "total_assets": ta, "current_assets": cur_a, "current_liabilities": cur_l,
        "total_liabilities": tl, "equity": equity, "cash": cash, "inventory": cur_a * 0.3,
        "receivables": cur_a * 0.3, "total_debt": debt, "long_term_debt": debt * 0.8,
        "retained_earnings": equity * 0.6, "shares_out": shares}, index=dates)
    cashflow = pd.DataFrame({
        "ocf": ocf, "capex": capex, "fcf": ocf + capex, "dividends": -np.maximum(ni, 0) * 0.4,
        "buybacks": -rev * (0.01 if g > 0 else 0.0), "sbc": rev * 0.005}, index=dates)
    for df, kind in ((income, "income"), (balance, "balance"), (cashflow, "cashflow")):
        for k in ALIASES[kind]:
            if k not in df:
                df[k] = np.nan
    # Yahoo da las cifras en unidades monetarias: se pasan de millones a unidades (BPA aparte).
    scale = [c for c in income.columns if c != "eps"]
    income[scale] *= 1e6
    return income, balance * 1e6, cashflow * 1e6


def demo(ticker: str = "DEMO-COMPRA", n_days: int = 1260, seed: int = 11) -> CompanyData:
    """Empresa sintética. Los tickers de ``DEMO_PROFILES`` tienen un perfil conocido (útil para
    tests); cualquier otro recibe uno de ellos según un hash del nombre."""
    key = ticker.upper()
    if key not in DEMO_PROFILES:
        key = list(DEMO_PROFILES)[zlib.crc32(key.encode()) % len(DEMO_PROFILES)]
    prof = DEMO_PROFILES[key]
    rng = np.random.default_rng(seed + zlib.crc32(key.encode()) % 1000)
    income, balance, cashflow = _demo_statements(prof, rng)
    eps = income["eps"].iloc[-1]
    sales_ps = income["revenue"].iloc[-1] / income["shares"].iloc[-1]
    target_price = prof["pe"] * eps if eps > 0 else 0.5 * sales_ps  # con pérdidas: P/V = 0.5
    beta = {"DEMO-VENDE": 1.5, "DEMO-CARA": 0.7}.get(key, 1.05)
    bench_df = _demo_prices(np.random.default_rng(seed), dict(drift=(0.07, 0.07), vol=0.16),
                            n_days, 10_000.0)
    m = np.log(bench_df["Close"]).diff().fillna(0.0).to_numpy()
    prices = _demo_prices(rng, prof, n_days, start=1.0, market=beta * (m - m.mean()))
    prices[["Open", "High", "Low", "Close"]] *= target_price / prices["Close"].iloc[-1]
    price = float(prices["Close"].iloc[-1])
    shares = income["shares"].iloc[-1]
    mcap = price * shares
    debt, cash = balance["total_debt"].iloc[-1], balance["cash"].iloc[-1]
    fwd_eps = eps * (1 + prof["growth"])
    info = {
        "shortName": prof["name"], "longName": f"{prof['name']} (demo)",
        "sector": prof["sector"], "industry": "—", "currency": "EUR", "country": "Spain",
        "currentPrice": price, "marketCap": mcap, "sharesOutstanding": shares,
        "trailingEps": float(eps), "trailingPE": price / eps if eps > 0 else None, "forwardPE": price / fwd_eps if fwd_eps > 0 else None,
        "enterpriseValue": mcap + debt - cash,
        "enterpriseToEbitda": (mcap + debt - cash) / income["ebitda"].iloc[-1],
        "priceToSalesTrailing12Months": mcap / income["revenue"].iloc[-1],
        "priceToBook": mcap / balance["equity"].iloc[-1],
        "beta": beta,
        "dividendRate": float(-cashflow["dividends"].iloc[-1] / shares),
        "targetMeanPrice": price * {"DEMO-COMPRA": 1.25, "DEMO-ESPERA": 1.35,
                                    "DEMO-VENDE": 0.85, "DEMO-CARA": 0.97}[key],
        "recommendationMean": {"DEMO-COMPRA": 1.9, "DEMO-ESPERA": 2.0, "DEMO-VENDE": 3.6,
                               "DEMO-CARA": 3.0}[key],
        "numberOfAnalystOpinions": 18, "fiftyTwoWeekHigh": float(prices["High"].iloc[-252:].max()),
        "fiftyTwoWeekLow": float(prices["Low"].iloc[-252:].min()),
    }
    bench = bench_df["Close"]
    earnings = DEMO_TODAY + pd.Timedelta(days=9 if key == "DEMO-CARA" else 75)
    return CompanyData(ticker.upper(), prices, info, income, balance, cashflow, "DEMO-INDEX",
                       bench, earnings, DEMO_TODAY + pd.Timedelta(days=40), 0.027, True, [])
