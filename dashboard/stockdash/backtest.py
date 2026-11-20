"""Backtest replicable de la puntuación técnica, la señal y la perspectiva a 1–3 meses.

Qué se evalúa
-------------
En cada **cierre de mes** y para cada valor se calcula, con datos hasta ese día
(``technical.features`` es causal), lo mismo que muestra el dashboard: puntuación técnica,
recomendación, perspectiva, P(subida) y rangos ±1σ. Después se mide lo que pasó a 21 y 63
sesiones. Sólo se evalúa el **bloque técnico**: Yahoo no da fundamentales históricos
*point-in-time* y usar los actuales introduciría sesgo de anticipación. Sin fundamentales,
la puntuación total del dashboard es la técnica, así que el backtest evalúa exactamente
esa configuración.

Métricas (``summarize``)
------------------------
* **IC** (information coefficient): correlación de rangos de Spearman, en cada fecha, entre la
  puntuación y la rentabilidad futura de los valores; media, desviación y t = media/σ·√n.
* **Por señal / por perspectiva**: nº de casos, rentabilidad media a 21 y 63 sesiones, exceso
  sobre el índice y tasa de acierto (Alcista: r₆₃ > 0; Bajista: r₆₃ < 0;
  Lateral: |log(1+r₆₃)| < ½·s₆₃, con s₆₃ = σ₆₃·√(63/252)).
* **Calibración** de P(subida): frecuencia observada de r₆₃ > 0 por tramo de probabilidad.
* **Cobertura** de los rangos ±1σ a 1 y 3 meses (lo ideal es ≈ 68 %).
* **Carteras mensuales** (rentabilidades no solapadas, de cierre de mes a cierre de mes):
  - *Señal*: equiponderada en los valores con «Comprar»/«Compra fuerte», liquidez si no hay;
  - *Universo*: equiponderada en todos los valores (referencia);
  - *Quintiles*: por puntuación (o terciles si hay < 10 valores) y diferencial superior − inferior.
  Se descuenta un coste de ``cost_bps`` puntos básicos por unidad de rotación.

Replicabilidad
--------------
``python -m stockdash.backtest`` (ejecutar desde ``dashboard/``) descarga los precios con
yfinance, los **guarda** en ``backtest/datos/<nombre>.csv.gz`` y escribe en
``backtest/resultados/<nombre>/``: ``observaciones.csv``, ``resumen.json`` (métricas,
configuración, versiones y SHA-256 de los datos), ``INFORME.md`` y figuras. Con ``--offline``
se reutiliza el CSV guardado, de modo que cualquiera reproduce exactamente el mismo resultado.
Ver ``backtest/README.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import data, scoring, technical

ROOT = Path(__file__).resolve().parent.parent
BACKTEST_DIR = ROOT / "backtest"
BUY = ("Comprar", "Compra fuerte")
SIGNAL_ORDER = ["Compra fuerte", "Comprar", "Mantener", "Vender", "Venta fuerte"]
OUTLOOK_ORDER = ["Alcista", "Lateral", "Bajista"]


@dataclass
class BacktestConfig:
    tickers: list[str]
    benchmarks: dict[str, str] = field(default_factory=lambda: dict(
        data.DEFAULT_CONFIG["benchmarks"]))
    start: str = "2012-01-01"
    end: str | None = None
    warmup: int = 260          # sesiones mínimas antes de la primera señal (SMA200, 12−1)
    horizons: tuple[int, int] = (21, 63)
    cost_bps: float = 10.0     # coste por unidad de rotación de la cartera
    name: str = "watchlist"


# --------------------------------------------------------------------------- datos
def to_long(prices: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = [df.assign(ticker=t) for t, df in prices.items()]
    out = pd.concat(frames).rename_axis("date").reset_index()
    return out[["date", "ticker", "Open", "High", "Low", "Close", "Volume"]]


def from_long(long: pd.DataFrame) -> dict[str, pd.DataFrame]:
    long = long.copy()
    long["date"] = pd.to_datetime(long["date"])
    return {t: g.set_index("date").drop(columns="ticker").sort_index().astype(float)
            for t, g in long.groupby("ticker")}


def load_or_download(cfg: BacktestConfig, cache: Path, offline: bool) -> dict[str, pd.DataFrame]:
    """Precios OHLCV ajustados de valores e índices; se guardan en ``cache`` (CSV comprimido)."""
    if offline:
        if not cache.exists():
            raise SystemExit(f"--offline: no existe {cache}")
        return from_long(pd.read_csv(cache))
    import yfinance as yf

    symbols = list(dict.fromkeys(cfg.tickers + [data.benchmark_for(t, cfg.benchmarks)
                                                for t in cfg.tickers]))
    raw = yf.download(symbols, start=cfg.start, end=cfg.end, interval="1d", auto_adjust=True,
                      group_by="ticker", progress=False, threads=True)
    prices = {}
    for s in symbols:
        try:
            df = raw[s] if isinstance(raw.columns, pd.MultiIndex) else raw
        except KeyError:
            continue
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
        if len(df):
            df.index = pd.to_datetime(df.index).tz_localize(None)
            prices[s] = df.astype(float)
    cache.parent.mkdir(parents=True, exist_ok=True)
    to_long(prices).to_csv(cache, index=False, float_format="%.6g")
    return prices


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


# --------------------------------------------------------------------------- observaciones
def month_end_positions(index: pd.DatetimeIndex) -> np.ndarray:
    """Posiciones (enteras) de la última sesión de cada mes."""
    s = pd.Series(np.arange(len(index)), index=index)
    return s.groupby(index.to_period("M")).max().to_numpy()


def observations(prices: dict[str, pd.DataFrame], cfg: BacktestConfig) -> pd.DataFrame:
    """Una fila por (cierre de mes, valor) con la evaluación y las rentabilidades futuras."""
    h1, h3 = cfg.horizons
    rows = []
    for t in cfg.tickers:
        if t not in prices:
            continue
        df = prices[t]
        bench_sym = data.benchmark_for(t, cfg.benchmarks)
        bench = prices.get(bench_sym, pd.DataFrame()).get("Close")
        feats = technical.features(df, bench)
        close = df["Close"].to_numpy()
        b = (bench.reindex(df.index).ffill().to_numpy() if bench is not None
             else np.full(len(df), np.nan))
        pos = month_end_positions(df.index)
        pos = pos[pos >= cfg.warmup]
        for k, i in enumerate(pos):
            a = scoring.assess(feats.iloc[i].to_dict(), None, w_tech=1.0)

            def fwd(arr, h):
                return arr[i + h] / arr[i] - 1.0 if i + h < len(arr) else np.nan

            nxt = pos[k + 1] if k + 1 < len(pos) else None
            sigma = feats["vol_63"].iat[i]
            rows.append({
                "date": df.index[i], "session": df.index[i], "ticker": t, "benchmark": bench_sym, "price": close[i],
                "score": a.technical, "outlook_score": a.outlook_score, "signal": a.signal,
                "outlook": a.outlook, "prob_up": a.prob_up,
                "lo_1m": a.range_1m[0], "hi_1m": a.range_1m[1],
                "lo_3m": a.range_3m[0], "hi_3m": a.range_3m[1],
                "s_3m": sigma * np.sqrt(h3 / 252) if np.isfinite(sigma) else np.nan,
                "r_1m": fwd(close, h1), "r_3m": fwd(close, h3),
                "rb_1m": fwd(b, h1), "rb_3m": fwd(b, h3),
                "price_1m": close[i + h1] if i + h1 < len(close) else np.nan,
                "price_3m": close[i + h3] if i + h3 < len(close) else np.nan,
                "r_next": close[nxt] / close[i] - 1.0 if nxt is not None else np.nan,
            })
    obs = pd.DataFrame(rows)
    if obs.empty:
        return obs
    obs["date"] = pd.to_datetime(obs["date"]).dt.to_period("M").dt.to_timestamp("M")
    obs["ex_1m"] = obs["r_1m"] - obs["rb_1m"]
    obs["ex_3m"] = obs["r_3m"] - obs["rb_3m"]
    return obs.sort_values(["date", "ticker"]).reset_index(drop=True)


# --------------------------------------------------------------------------- métricas
def _ic(obs: pd.DataFrame, col: str, min_names: int = 4) -> dict[str, float]:
    vals = []
    for _, g in obs.dropna(subset=["score", col]).groupby("date"):
        if len(g) >= min_names and g["score"].nunique() > 1:
            vals.append(g["score"].rank().corr(g[col].rank()))
    v = np.array([x for x in vals if np.isfinite(x)])
    if len(v) < 2:
        return {"media": np.nan, "desv": np.nan, "t": np.nan, "fechas": int(len(v))}
    return {"media": float(v.mean()), "desv": float(v.std(ddof=1)),
            "t": float(v.mean() / v.std(ddof=1) * np.sqrt(len(v))), "fechas": int(len(v))}


def _group_table(obs: pd.DataFrame, by: str, order: list[str]) -> list[dict]:
    out = []
    for key in order:
        g = obs[obs[by] == key]
        if g.empty:
            continue
        g3 = g.dropna(subset=["r_3m"])
        if by == "outlook":
            if key == "Alcista":
                hit = (g3["r_3m"] > 0).mean()
            elif key == "Bajista":
                hit = (g3["r_3m"] < 0).mean()
            else:
                hit = (np.abs(np.log1p(g3["r_3m"])) < 0.5 * g3["s_3m"]).mean()
        else:
            hit = (g3["r_3m"] > 0).mean()
        out.append({by: key, "casos": int(len(g)), "r_1m_media": float(g["r_1m"].mean()),
                    "r_3m_media": float(g["r_3m"].mean()),
                    "exceso_3m_medio": float(g["ex_3m"].mean()),
                    "acierto": float(hit) if len(g3) else np.nan})
    return out


def _calibration(obs: pd.DataFrame) -> list[dict]:
    g = obs.dropna(subset=["r_3m"])
    bins = [0.0, 0.40, 0.45, 0.50, 0.55, 0.60, 1.0]
    labels = ["< 40 %", "40–45 %", "45–50 %", "50–55 %", "55–60 %", "≥ 60 %"]
    cut = pd.cut(g["prob_up"], bins, labels=labels, include_lowest=True, right=False)
    out = []
    for label, gg in g.groupby(cut, observed=True):
        out.append({"tramo": str(label), "casos": int(len(gg)),
                    "p_media": float(gg["prob_up"].mean()),
                    "frecuencia_subida": float((gg["r_3m"] > 0).mean())})
    return out


def portfolios(obs: pd.DataFrame, cost_bps: float) -> pd.DataFrame:
    """Rentabilidades mensuales (cierre de mes → siguiente) de las carteras descritas arriba."""
    o = obs.dropna(subset=["r_next", "score"])
    n_tickers = o["ticker"].nunique()
    n_groups = 5 if n_tickers >= 10 else 3
    rows, prev_w = [], pd.Series(dtype=float)
    for date, g in o.groupby("date"):
        buy = g[g["signal"].isin(BUY)]
        w = (pd.Series(1.0 / len(buy), index=buy["ticker"]) if len(buy)
             else pd.Series(dtype=float))
        turnover = w.sub(prev_w, fill_value=0.0).abs().sum()
        prev_w = w
        r_sig = float((buy["r_next"].mean() if len(buy) else 0.0) - turnover * cost_bps / 1e4)
        q = pd.qcut(g["score"].rank(method="first"), min(n_groups, len(g)), labels=False)
        rows.append({"date": date, "senal": r_sig, "universo": float(g["r_next"].mean()),
                     "q_sup": float(g.loc[q == q.max(), "r_next"].mean()),
                     "q_inf": float(g.loc[q == q.min(), "r_next"].mean()),
                     "invertido": len(buy) > 0, "rotacion": float(turnover)})
    p = pd.DataFrame(rows).set_index("date")
    if not p.empty:
        p["dif_q"] = p["q_sup"] - p["q_inf"]
    return p


def _perf(r: pd.Series) -> dict[str, float]:
    r = r.dropna()
    if r.empty:
        return {}
    eq = (1 + r).cumprod()
    years = len(r) / 12
    vol = r.std(ddof=1) * np.sqrt(12)
    return {"cagr": float(eq.iloc[-1] ** (1 / years) - 1), "vol": float(vol),
            "sharpe": float(r.mean() * 12 / vol) if vol > 0 else np.nan,
            "max_drawdown": float((eq / eq.cummax() - 1).min()), "meses": int(len(r))}


def summarize(obs: pd.DataFrame, cfg: BacktestConfig) -> dict:
    o = obs.dropna(subset=["score"])
    done3 = o.dropna(subset=["r_3m"])
    done1 = o.dropna(subset=["r_1m"])
    p = portfolios(o, cfg.cost_bps)
    return {
        "observaciones": int(len(o)), "valores": int(o["ticker"].nunique()),
        "desde": str(pd.Timestamp(o["session"].min()).date()),
        "hasta": str(pd.Timestamp(o["session"].max()).date()),
        "ic_1m": _ic(o, "r_1m"), "ic_3m": _ic(o, "r_3m"),
        "ic_exceso_3m": _ic(o, "ex_3m"),
        "por_senal": _group_table(o, "signal", SIGNAL_ORDER),
        "por_perspectiva": _group_table(o, "outlook", OUTLOOK_ORDER),
        "calibracion": _calibration(o),
        "cobertura_rango_1m": float(((done1["price_1m"] >= done1["lo_1m"])
                                     & (done1["price_1m"] <= done1["hi_1m"])).mean()),
        "cobertura_rango_3m": float(((done3["price_3m"] >= done3["lo_3m"])
                                     & (done3["price_3m"] <= done3["hi_3m"])).mean()),
        "carteras": {"senal": _perf(p.get("senal", pd.Series(dtype=float))),
                     "universo": _perf(p.get("universo", pd.Series(dtype=float))),
                     "dif_quintiles": _perf(p.get("dif_q", pd.Series(dtype=float))),
                     "meses_invertido": float(p["invertido"].mean()) if len(p) else np.nan,
                     "rotacion_media": float(p["rotacion"].mean()) if len(p) else np.nan},
    }


# --------------------------------------------------------------------------- informe
def _pct(x: float, d: int = 1) -> str:
    return "—" if x is None or not np.isfinite(x) else f"{100 * x:+.{d}f} %"


def _plain_pct(x: float) -> str:
    return "—" if x is None or not np.isfinite(x) else f"{100 * x:.0f} %"


def figures(obs: pd.DataFrame, cfg: BacktestConfig, outdir: Path) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    series = ["#2a78d6", "#eb6834", "#1baf7a"]
    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.color": "#e1e0d9", "axes.edgecolor": "#c3c2b7",
                         "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold"})
    names = []
    p = portfolios(obs.dropna(subset=["score"]), cfg.cost_bps)
    if not p.empty:
        fig, ax = plt.subplots(figsize=(8, 4.2))
        for col, label, c in (("senal", "Cartera por señal (Comprar/Compra fuerte)", series[0]),
                              ("universo", "Universo equiponderado", series[1]),
                              ("dif_q", "Diferencial mejor − peor grupo", series[2])):
            ax.plot(p.index, (1 + p[col]).cumprod(), label=label, color=c, lw=1.8)
        ax.axhline(1, color="#898781", lw=0.8)
        ax.set_yscale("log")
        ax.set_title("Valor acumulado de 1 € (escala log., rebalanceo mensual, con costes)")
        ax.legend(frameon=False, loc="upper left")
        fig.tight_layout()
        fig.savefig(outdir / "carteras.png", dpi=150)
        plt.close(fig)
        names.append("carteras.png")

    tab = pd.DataFrame(_group_table(obs, "signal", SIGNAL_ORDER))
    if not tab.empty:
        fig, ax = plt.subplots(figsize=(8, 3.6))
        x = np.arange(len(tab))
        ax.bar(x - 0.2, 100 * tab["r_1m_media"], 0.38, label="21 sesiones", color=series[0])
        ax.bar(x + 0.2, 100 * tab["r_3m_media"], 0.38, label="63 sesiones", color=series[1])
        ax.set_xticks(x, [f"{s}\n(n={n})" for s, n in zip(tab["signal"], tab["casos"])])
        ax.axhline(0, color="#898781", lw=0.8)
        ax.set_ylabel("Rentabilidad media (%)")
        ax.set_title("Rentabilidad posterior según la señal")
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(outdir / "por_senal.png", dpi=150)
        plt.close(fig)
        names.append("por_senal.png")

    cal = pd.DataFrame(_calibration(obs))
    if not cal.empty:
        fig, ax = plt.subplots(figsize=(4.8, 4.2))
        ax.plot([0.25, 0.75], [0.25, 0.75], color="#898781", lw=0.8, ls="--",
                label="Calibración perfecta")
        ax.plot(cal["p_media"], cal["frecuencia_subida"], "o-", color=series[0], lw=1.8, ms=7,
                label="Observado")
        for _, r in cal.iterrows():
            ax.annotate(f"n={r['casos']}", (r["p_media"], r["frecuencia_subida"]),
                        textcoords="offset points", xytext=(6, -10), fontsize=8,
                        color="#52514e")
        ax.set_xlabel("P(subida) estimada")
        ax.set_ylabel("Frecuencia observada r₆₃ > 0")
        ax.set_title("Calibración de P(subida)")
        ax.legend(frameon=False, loc="upper left")
        fig.tight_layout()
        fig.savefig(outdir / "calibracion.png", dpi=150)
        plt.close(fig)
        names.append("calibracion.png")
    return names


def write_report(obs: pd.DataFrame, summ: dict, cfg: BacktestConfig, outdir: Path,
                 meta: dict, figs: list[str]) -> None:
    ic1, ic3, icx = summ["ic_1m"], summ["ic_3m"], summ["ic_exceso_3m"]
    c = summ["carteras"]

    def perf_row(name, d):
        if not d:
            return f"| {name} | — | — | — | — |"
        return (f"| {name} | {_pct(d['cagr'])} | {_plain_pct(d['vol'])} | "
                f"{d['sharpe']:.2f} | {_pct(d['max_drawdown'])} |")

    lines = [
        f"# Backtest «{cfg.name}»",
        "",
        *(["> **Datos sintéticos.** Este informe sólo comprueba que el proceso funciona: los "
           "precios demo tienen regímenes persistentes por construcción, así que las cifras "
           "**no dicen nada sobre mercados reales**. Para el backtest real ver "
           "`dashboard/backtest/README.md`.", ""]
          if meta.get("origen_datos", "").startswith("sintéticos") else []),
        f"Generado {meta['generado']} · datos {meta['origen_datos']} · "
        f"{summ['valores']} valores · {summ['observaciones']} observaciones mensuales · "
        f"{summ['desde']} → {summ['hasta']}",
        "",
        "Evalúa la **puntuación técnica** del dashboard (los fundamentales no tienen histórico "
        "point-in-time). Metodología y cómo reproducirlo: `dashboard/backtest/README.md`.",
        "",
        "## Poder predictivo (IC de Spearman por fecha)",
        "",
        "| Horizonte | IC medio | Desv. | t | Fechas |",
        "|---|---|---|---|---|",
        *(f"| {k} | {d['media']:+.3f} | {d['desv']:.3f} | {d['t']:+.2f} | {d['fechas']} |"
          for k, d in (("21 sesiones", ic1), ("63 sesiones", ic3),
                       ("63 sesiones, exceso vs índice", icx))),
        "",
        "Referencia: un IC medio de 0,02–0,05 con t > 2 ya se considera útil en factores de "
        "renta variable; |t| < 2 no es distinguible de cero.",
        "",
        "## Rentabilidad posterior por recomendación",
        "",
        "| Señal | Casos | r 21 s. | r 63 s. | Exceso 63 s. | % r₆₃ > 0 |",
        "|---|---|---|---|---|---|",
        *(f"| {r['signal']} | {r['casos']} | {_pct(r['r_1m_media'])} | {_pct(r['r_3m_media'])} | "
          f"{_pct(r['exceso_3m_medio'])} | {_plain_pct(r['acierto'])} |"
          for r in summ["por_senal"]),
        "",
        "## Perspectiva a 1–3 meses",
        "",
        "| Perspectiva | Casos | r 63 s. | Exceso 63 s. | Acierto |",
        "|---|---|---|---|---|",
        *(f"| {r['outlook']} | {r['casos']} | {_pct(r['r_3m_media'])} | "
          f"{_pct(r['exceso_3m_medio'])} | {_plain_pct(r['acierto'])} |"
          for r in summ["por_perspectiva"]),
        "",
        "Acierto: Alcista ⇒ r₆₃ > 0; Bajista ⇒ r₆₃ < 0; Lateral ⇒ |log(1+r₆₃)| < ½·σ₆₃·√(63/252).",
        "",
        f"Cobertura de los rangos ±1σ (ideal ≈ 68 %): 1 mes {_plain_pct(summ['cobertura_rango_1m'])}"
        f", 3 meses {_plain_pct(summ['cobertura_rango_3m'])}.",
        "",
        "## Calibración de P(subida) a 63 sesiones",
        "",
        "| Tramo | Casos | P media | Frecuencia observada |",
        "|---|---|---|---|",
        *(f"| {r['tramo']} | {r['casos']} | {_plain_pct(r['p_media'])} | "
          f"{_plain_pct(r['frecuencia_subida'])} |" for r in summ["calibracion"]),
        "",
        f"## Carteras mensuales (coste {cfg.cost_bps:.0f} pb por rotación)",
        "",
        "| Cartera | CAGR | Volatilidad | Sharpe | Máx. caída |",
        "|---|---|---|---|---|",
        perf_row("Por señal (Comprar/Compra fuerte, si no liquidez)", c["senal"]),
        perf_row("Universo equiponderado", c["universo"]),
        perf_row("Diferencial mejor − peor grupo", c["dif_quintiles"]),
        "",
        f"La cartera por señal estuvo invertida el {_plain_pct(c['meses_invertido'])} de los meses;"
        f" rotación media mensual {c['rotacion_media']:.2f}.",
        "",
        *(f"![{f}]({f})" for f in figs),
        "",
        "## Limitaciones",
        "",
        "- Sesgo de supervivencia: el universo son los valores elegidos hoy, que existen hoy.",
        "- Sólo técnico; los umbrales no se han optimizado con estos datos (no hay sobreajuste, "
        "pero tampoco calibración).",
        "- Observaciones a 63 sesiones solapadas mes a mes: los t del IC y los aciertos están "
        "algo inflados; las carteras usan rentabilidades mensuales no solapadas.",
        "",
    ]
    (outdir / "INFORME.md").write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------- orquestación
def run(prices: dict[str, pd.DataFrame], cfg: BacktestConfig, outdir: Path,
        meta: dict | None = None) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    obs = observations(prices, cfg)
    if obs.empty:
        raise SystemExit("Sin observaciones: ¿hay al menos ~13 meses de datos por valor?")
    summ = summarize(obs, cfg)
    meta = {"generado": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "python": platform.python_version(), "numpy": np.__version__,
            "pandas": pd.__version__, **(meta or {})}
    obs.to_csv(outdir / "observaciones.csv", index=False, float_format="%.6g")
    figs = figures(obs, cfg, outdir)
    write_report(obs, summ, cfg, outdir, meta, figs)
    cfg_d = asdict(cfg)
    (outdir / "resumen.json").write_text(
        json.dumps({"config": cfg_d, "meta": meta, "metricas": summ}, indent=2,
                   ensure_ascii=False, default=lambda x: None if x != x else str(x)) + "\n",
        encoding="utf-8")
    return summ


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="python -m stockdash.backtest",
        description="Backtest replicable de la señal técnica del dashboard.")
    ap.add_argument("--tickers", help="Lista separada por comas (por defecto, watchlist.json)")
    ap.add_argument("--name", default=None,
                    help="Nombre del experimento: datos y resultados se guardan con él")
    ap.add_argument("--start", default="2012-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--cost-bps", type=float, default=10.0)
    ap.add_argument("--offline", action="store_true",
                    help="Reutiliza backtest/datos/<nombre>.csv.gz sin descargar")
    ap.add_argument("--demo", action="store_true",
                    help="Datos sintéticos (para comprobar el proceso sin red)")
    args = ap.parse_args(argv)

    wl = data.load_config()
    tickers = data.parse_tickers(args.tickers) if args.tickers else wl["tickers"]
    name = args.name or ("demo" if args.demo else "watchlist")
    cfg = BacktestConfig(tickers=tickers, benchmarks=wl["benchmarks"], start=args.start,
                         end=args.end, cost_bps=args.cost_bps, name=name)
    cache = BACKTEST_DIR / "datos" / f"{name}.csv.gz"
    if args.demo:
        symbols = list(dict.fromkeys(tickers + [data.benchmark_for(t, cfg.benchmarks)
                                                for t in tickers]))
        prices = data.demo_prices(symbols, n_days=2600)
        origen = "sintéticos (demo, semilla fija)"
    else:
        prices = load_or_download(cfg, cache, args.offline)
        origen = f"Yahoo Finance, guardados en backtest/datos/{cache.name}"
    meta = {"origen_datos": origen, "sha256_datos": sha256(cache) if not args.demo else "",
            "comando": "python -m stockdash.backtest " + " ".join(argv or [])}
    outdir = BACKTEST_DIR / "resultados" / name
    summ = run(prices, cfg, outdir, meta)
    print(f"Informe: {outdir / 'INFORME.md'}")
    print(f"IC 63 sesiones: {summ['ic_3m']['media']:+.3f} (t = {summ['ic_3m']['t']:+.2f})")


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
