"""Series temporales de rendimientos: distribución, dependencia, volatilidad (EWMA y GARCH),
riesgo de cola (VaR/CVaR), caídas, beta y ratios de rentabilidad-riesgo; pilar «Riesgo».

Notación: rₜ = ln(Pₜ/Pₜ₋₁) (log-rendimiento diario); anualización con 252 sesiones.

- Ljung-Box: Q = n(n+2) Σₖ ρ̂ₖ²/(n−k) ~ χ²(m) bajo independencia (sobre r y sobre r²: esta
  última detecta agrupamiento de volatilidad).
- Ratio de varianzas de Lo-MacKinlay: VR(q) = Var(r⁽q⁾)/(q·Var(r)); z = (VR−1)/√(2(2q−1)(q−1)/(3qn)).
  VR > 1 ⇒ persistencia (tendencia); VR < 1 ⇒ reversión a la media.
- Exponente de Hurst por varianza de incrementos: Std(ln P_{t+τ} − ln P_t) ∝ τᴴ (H = ½ paseo
  aleatorio).
- GARCH(1,1): σ²ₜ = ω + α ε²ₜ₋₁ + β σ²ₜ₋₁, máxima verosimilitud gaussiana. Varianza a largo
  plazo V_L = ω/(1−α−β); previsión E[σ²ₜ₊ₕ] = V_L + (α+β)^{h−1}(σ²ₜ₊₁ − V_L).
- VaR Cornish-Fisher: z_cf = z + (z²−1)S/6 + (z³−3z)K/24 − (2z³−5z)S²/36.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import optimize, stats
from scipy.signal import lfilter

from .common import TRADING_DAYS, Item, Pillar, finite, piecewise, ramp


def log_returns(close: pd.Series) -> pd.Series:
    return np.log(close).diff().dropna()


# --------------------------------------------------------------------------- dependencia
def ljung_box(x: np.ndarray, lags: int = 10) -> tuple[float, float]:
    """(Q, p-valor) del contraste de Ljung-Box con ``lags`` retardos."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)] - np.nanmean(x)
    n = x.size
    denom = (x ** 2).sum()
    rho = np.array([(x[k:] * x[:-k]).sum() / denom for k in range(1, lags + 1)])
    q = n * (n + 2) * np.sum(rho ** 2 / (n - np.arange(1, lags + 1)))
    return float(q), float(stats.chi2.sf(q, lags))


def variance_ratio(r: np.ndarray, q: int = 5) -> tuple[float, float]:
    """(VR(q), z) de Lo-MacKinlay (1988) bajo homocedasticidad, con solapamiento."""
    r = np.asarray(r, float)
    n = r.size
    mu = r.mean()
    var1 = ((r - mu) ** 2).sum() / (n - 1)
    rq = np.convolve(r, np.ones(q), mode="valid")
    m = q * (n - q + 1) * (1 - q / n)
    varq = ((rq - q * mu) ** 2).sum() / m
    vr = varq / var1
    z = (vr - 1) / np.sqrt(2 * (2 * q - 1) * (q - 1) / (3 * q * n))
    return float(vr), float(z)


def hurst(close: pd.Series, max_lag: int = 100) -> float:
    """Exponente de Hurst: pendiente de log Std(ln P_{t+τ} − ln P_t) frente a log τ."""
    lp = np.log(close.to_numpy(float))
    lags = np.unique(np.geomspace(2, min(max_lag, lp.size // 4), 20).astype(int))
    if lags.size < 3:
        return float("nan")
    sd = np.array([np.std(lp[k:] - lp[:-k]) for k in lags])
    return float(np.polyfit(np.log(lags), np.log(sd), 1)[0])


# --------------------------------------------------------------------------- volatilidad
def ewma_vol(r: pd.Series, lam: float = 0.94) -> pd.Series:
    """Volatilidad EWMA de RiskMetrics (anualizada)."""
    return np.sqrt((r ** 2).ewm(alpha=1 - lam, adjust=False).mean() * TRADING_DAYS)


def garch_filter(eps: np.ndarray, omega: float, alpha: float, beta: float,
                 s0: float | None = None) -> np.ndarray:
    """Varianzas condicionales σ²ₜ (t = 0..n): σ²₀ = ``s0`` (varianza muestral por defecto) y
    σ²ₜ = ω + α ε²ₜ₋₁ + β σ²ₜ₋₁. Devuelve n+1 valores (el último es la previsión a un día).

    La recursión es un filtro lineal IIR sobre ε², así que se resuelve con ``lfilter``.
    """
    e2 = np.asarray(eps, float) ** 2
    s0 = float(e2.mean()) if s0 is None else s0
    u = omega + alpha * e2
    rest, _ = lfilter([1.0], [1.0, -beta], u, zi=[beta * s0])
    return np.concatenate([[s0], rest])


@dataclass
class Garch:
    omega: float
    alpha: float
    beta: float
    mu: float
    sigma2: np.ndarray          # varianzas condicionales (n+1; la última es la previsión)
    loglik: float
    converged: bool

    @property
    def persistence(self) -> float:
        return self.alpha + self.beta

    @property
    def long_run_vol(self) -> float:
        """Volatilidad anual a largo plazo √(252·V_L)."""
        p = self.persistence
        return float(np.sqrt(TRADING_DAYS * self.omega / (1 - p))) if p < 1 else float("nan")

    @property
    def half_life(self) -> float:
        """Sesiones para que un choque de volatilidad se reduzca a la mitad."""
        p = self.persistence
        return float(np.log(0.5) / np.log(p)) if 0 < p < 1 else float("nan")

    def forecast_vol(self, horizon: int) -> float:
        """Volatilidad anualizada media prevista para las próximas ``horizon`` sesiones."""
        p = self.persistence
        vl = self.omega / (1 - p) if p < 1 else self.sigma2[-1]
        h = np.arange(horizon)
        path = vl + p ** h * (self.sigma2[-1] - vl)
        return float(np.sqrt(path.mean() * TRADING_DAYS))


def fit_garch(r: np.ndarray) -> Garch:
    """GARCH(1,1) por máxima verosimilitud gaussiana (cuasi-MV, robusta a colas gruesas).

    Parametrización: ω = exp(θ₀)·Var(r), (α, β) vía logística con α + β < 0.9999.
    """
    r = np.asarray(r, float)
    mu = float(r.mean())
    eps = r - mu
    v = float(eps.var())

    def unpack(th):
        omega = np.exp(th[0]) * v
        p = 0.9999 / (1 + np.exp(-th[1]))            # persistencia α+β
        a = p / (1 + np.exp(-th[2]))                  # reparto entre α y β
        return omega, a, p - a

    def nll(th):
        o, a, b = unpack(th)
        s2 = garch_filter(eps, o, a, b, v)[:-1]
        return 0.5 * np.sum(np.log(2 * np.pi * s2) + eps ** 2 / s2)

    best = None
    for start in ([np.log(0.02), 3.0, -2.0], [np.log(0.05), 2.0, -1.5], [np.log(0.01), 4.5, -2.5]):
        res = optimize.minimize(nll, start, method="Nelder-Mead",
                                options=dict(xatol=1e-7, fatol=1e-9, maxiter=4000))
        if best is None or res.fun < best.fun:
            best = res
    o, a, b = unpack(best.x)
    return Garch(float(o), float(a), float(b), mu, garch_filter(eps, o, a, b, v),
                 float(-best.fun), bool(best.success))


# --------------------------------------------------------------------------- riesgo
def var_cvar(r: np.ndarray, level: float = 0.95) -> dict[str, float]:
    """VaR y CVaR diarios (como pérdidas positivas): histórico, normal y Cornish-Fisher."""
    r = np.asarray(r, float)
    mu, sd = r.mean(), r.std(ddof=1)
    q = 1 - level
    hist_var = -np.quantile(r, q)
    hist_cvar = -r[r <= -hist_var].mean()
    z = stats.norm.ppf(q)
    s, k = stats.skew(r), stats.kurtosis(r)
    zcf = z + (z ** 2 - 1) * s / 6 + (z ** 3 - 3 * z) * k / 24 - (2 * z ** 3 - 5 * z) * s ** 2 / 36
    return {"hist_var": float(hist_var), "hist_cvar": float(hist_cvar),
            "normal_var": float(-(mu + z * sd)),
            "normal_cvar": float(-(mu - sd * stats.norm.pdf(z) / q)),
            "cf_var": float(-(mu + zcf * sd))}


def drawdown(close: pd.Series) -> pd.Series:
    """Caída desde el máximo previo (≤ 0)."""
    return close / close.cummax() - 1


def beta_alpha(r: pd.Series, rb: pd.Series, freq: str = "W-FRI") -> dict[str, float]:
    """β, correlación, α anual y R² frente al índice con rendimientos **semanales** (evita el
    desfase horario entre mercados)."""
    px = pd.concat([np.exp(r.cumsum()), np.exp(rb.cumsum())], axis=1, keys=["s", "b"]).ffill().dropna()
    w = np.log(px.resample(freq).last()).diff().dropna()
    if len(w) < 26:
        return {"beta": float("nan"), "corr": float("nan"), "alpha": float("nan"), "r2": float("nan")}
    cov = np.cov(w["s"], w["b"])
    beta = cov[0, 1] / cov[1, 1]
    corr = cov[0, 1] / np.sqrt(cov[0, 0] * cov[1, 1])
    alpha = (w["s"].mean() - beta * w["b"].mean()) * 52
    return {"beta": float(beta), "corr": float(corr), "alpha": float(alpha), "r2": float(corr ** 2)}


# --------------------------------------------------------------------------- resumen y pilar
@dataclass
class TimeSeries:
    returns: pd.Series
    stats: dict[str, float]
    garch: Garch | None
    rolling_vol: pd.DataFrame          # realizada 21/63 y EWMA, anualizadas
    drawdown: pd.Series
    annual: pd.Series                  # rentabilidad por año natural
    monthly_seasonality: pd.Series     # media del rendimiento por mes del año
    cone: pd.DataFrame                 # rango de precio previsto (1 y 3 meses)
    pillar: Pillar
    notes: list[str] = field(default_factory=list)


def analyze(close: pd.Series, bench: pd.Series | None = None, rf: float = 0.03) -> TimeSeries:
    r = log_returns(close)
    a = r.to_numpy()
    n = a.size
    mu_a, vol_a = a.mean() * TRADING_DAYS, a.std(ddof=1) * np.sqrt(TRADING_DAYS)
    downside = np.sqrt(np.mean(np.minimum(a, 0) ** 2)) * np.sqrt(TRADING_DAYS)
    dd = drawdown(close)
    jb = stats.jarque_bera(a)
    q_r, p_r = ljung_box(a)
    q_r2, p_r2 = ljung_box(a ** 2)
    vr, vrz = variance_ratio(a)
    years = n / TRADING_DAYS
    cagr = float((close.iloc[-1] / close.iloc[0]) ** (1 / years) - 1) if years > 0 else float("nan")

    s: dict[str, float] = {
        "n": n, "cagr": cagr, "mean_annual": mu_a, "vol_annual": vol_a,
        "skew": float(stats.skew(a)), "excess_kurtosis": float(stats.kurtosis(a)),
        "jb_pvalue": float(jb.pvalue), "lb_pvalue": p_r, "lb2_pvalue": p_r2,
        "variance_ratio": vr, "vr_z": vrz, "hurst": hurst(close),
        "sharpe": (mu_a - rf) / vol_a if vol_a > 0 else float("nan"),
        "sortino": (mu_a - rf) / downside if downside > 0 else float("nan"),
        "max_drawdown": float(dd.min()), "current_drawdown": float(dd.iloc[-1]),
        "calmar": cagr / abs(dd.min()) if dd.min() < 0 else float("nan"),
        "best_day": float(a.max()), "worst_day": float(a.min()),
    }
    # Rentabilidad-riesgo de los últimos 3 años (lo más relevante para hoy).
    a3 = a[-3 * TRADING_DAYS:]
    v3 = a3.std(ddof=1) * np.sqrt(TRADING_DAYS)
    s["sharpe_3y"] = (a3.mean() * TRADING_DAYS - rf) / v3 if v3 > 0 else float("nan")
    s["max_drawdown_3y"] = float(drawdown(close.iloc[-3 * TRADING_DAYS:]).min())
    s.update({f"{k}_95": v for k, v in var_cvar(a, 0.95).items()})
    s.update({f"{k}_99": v for k, v in var_cvar(a, 0.99).items() if k in ("hist_var", "cf_var")})

    rv = pd.DataFrame({
        "vol21": r.rolling(21).std() * np.sqrt(TRADING_DAYS),
        "vol63": r.rolling(63).std() * np.sqrt(TRADING_DAYS),
        "ewma": ewma_vol(r),
    })
    v21 = rv["vol21"].dropna()
    s["vol21"] = float(v21.iloc[-1])
    s["vol21_percentile"] = float((v21 <= v21.iloc[-1]).mean())

    g = None
    if n >= 250:
        g = fit_garch(a[-min(n, 5 * TRADING_DAYS):])
        s.update({"garch_alpha": g.alpha, "garch_beta": g.beta, "garch_persistence": g.persistence,
                  "garch_long_run_vol": g.long_run_vol, "garch_half_life": g.half_life,
                  "garch_vol_1m": g.forecast_vol(21), "garch_vol_3m": g.forecast_vol(63),
                  "garch_vol_now": float(np.sqrt(g.sigma2[-1] * TRADING_DAYS))})
    if bench is not None and len(bench) > 60:
        s.update(beta_alpha(r, log_returns(bench)))

    annual = close.resample("YE").last().pct_change()
    annual.iloc[0] = close.resample("YE").last().iloc[0] / close.iloc[0] - 1
    annual.index = annual.index.year
    mret = close.resample("ME").last().pct_change().dropna()
    season = mret.groupby(mret.index.month).mean()

    # Cono de precios: log-normal con la vol GARCH prevista (o la histórica) y deriva nula.
    p0 = float(close.iloc[-1])
    rows = []
    for label, h in (("1 mes", 21), ("3 meses", 63)):
        vol = g.forecast_vol(h) if g is not None else vol_a
        sd = vol * np.sqrt(h / TRADING_DAYS)
        rows.append({"horizonte": label, "vol_anual": vol,
                     "p05": p0 * np.exp(-1.645 * sd - sd ** 2 / 2),
                     "p16": p0 * np.exp(-sd - sd ** 2 / 2), "p50": p0 * np.exp(-sd ** 2 / 2),
                     "p84": p0 * np.exp(sd - sd ** 2 / 2), "p95": p0 * np.exp(1.645 * sd - sd ** 2 / 2)})
    cone = pd.DataFrame(rows).set_index("horizonte")

    notes = _notes(s)
    pil = Pillar("Riesgo y comportamiento del precio")
    vol_trend = s.get("garch_vol_1m", np.nan) / s.get("garch_long_run_vol", np.nan) - 1
    pil.items += [
        Item("sharpe_3y", "Sharpe 3 años", s["sharpe_3y"], ramp(s["sharpe_3y"], -0.5, 1.0), "num",
             "Rentabilidad sobre el bono por unidad de volatilidad", 1.0),
        Item("max_drawdown_3y", "Caída máxima 3 años", s["max_drawdown_3y"],
             ramp(s["max_drawdown_3y"], -0.6, -0.15), "pct", "", 0.7),
        Item("vol_annual", "Volatilidad anual (5 años)", vol_a,
             piecewise(vol_a, [0.15, 0.25, 0.40, 0.60], [0.6, 0.2, -0.4, -1]), "pct0", "", 0.6),
        Item("vol_regime", "Percentil de la volatilidad actual (21 s.)", s["vol21_percentile"],
             piecewise(s["vol21_percentile"], [0.2, 0.5, 0.8, 0.95], [0.4, 0.2, -0.4, -1]), "pct0",
             "Alto = mercado nervioso con este valor", 0.8),
        Item("garch_vol_trend", "Vol. GARCH prevista 1 mes vs largo plazo", vol_trend,
             ramp(vol_trend, 0.4, -0.2), "pct", "> 0: se espera más volatilidad de la habitual", 0.6),
        Item("cf_var_95", "VaR diario 95 % (Cornish-Fisher)", s["cf_var_95"],
             ramp(s["cf_var_95"], 0.045, 0.015), "pct0", "Pérdida diaria superada 1 de cada 20 días", 0.5),
    ]
    return TimeSeries(r, s, g, rv, dd, annual, season, cone, pil, notes)


def _notes(s: dict[str, float]) -> list[str]:
    out = []
    out.append(
        f"Distribución: asimetría {s['skew']:+.2f}, curtosis en exceso {s['excess_kurtosis']:.1f} "
        f"({'colas gruesas: los movimientos extremos son más frecuentes que en una normal' if s['jb_pvalue'] < 0.05 else 'compatible con normalidad'}).")
    out.append("Rendimientos " + ("con autocorrelación significativa" if s["lb_pvalue"] < 0.05
                                  else "sin autocorrelación significativa (difíciles de predecir con su propio pasado)")
               + f" (Ljung-Box p = {s['lb_pvalue']:.3f}).")
    if s["lb2_pvalue"] < 0.05:
        out.append("La volatilidad se agrupa (Ljung-Box sobre r², p < 0.05): tras días agitados "
                   "vienen días agitados; el modelo GARCH es pertinente.")
    vr, z, h = s["variance_ratio"], s["vr_z"], s["hurst"]
    if abs(z) > 1.96:
        out.append(f"Ratio de varianzas {vr:.2f} (z = {z:+.1f}): "
                   + ("persistencia (comportamiento tendencial)." if vr > 1 else "reversión a la media a corto plazo."))
    else:
        out.append(f"Ratio de varianzas {vr:.2f} (z = {z:+.1f}) y Hurst {h:.2f}: compatible con paseo aleatorio.")
    if finite(s.get("garch_persistence")):
        out.append(f"GARCH(1,1): persistencia α+β = {s['garch_persistence']:.3f}, vida media de un "
                   f"choque {s['garch_half_life']:.0f} sesiones; vol. actual {s['garch_vol_now']:.0%}, "
                   f"prevista 1 mes {s['garch_vol_1m']:.0%}, largo plazo {s['garch_long_run_vol']:.0%}.")
    if finite(s.get("beta")):
        out.append(f"Frente al índice: β = {s['beta']:.2f}, correlación {s['corr']:.2f}, "
                   f"α anual {s['alpha']:+.1%} (rendimientos semanales).")
    return out
