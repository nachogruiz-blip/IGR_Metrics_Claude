"""Regenera todas las figuras del PDF en figuras/ (deterministas, sin red)."""
import numpy as np
import pandas as pd
from scipy.stats import norm

import _comun  # noqa: F401
import matplotlib.pyplot as plt
from trader import backtest as bt
from trader import commodities as cm
from trader import data, equity, indicators as ind, options as op, performance as perf, plotting, rates, risk

S = plotting.SERIES


def f01_indicadores():
    df = data.synthetic_ohlc(500, seed=21, mu=0.12)
    c = df["close"].iloc[-250:]
    bb = ind.bollinger(df["close"]).iloc[-250:]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8, 5), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    a1.plot(c.index, c, color=S[0], lw=1, label="Cierre")
    a1.plot(c.index, ind.sma(df["close"], 50).iloc[-250:], color=S[1], label="SMA 50")
    a1.plot(c.index, ind.sma(df["close"], 200).iloc[-250:], color=S[2], label="SMA 200")
    a1.fill_between(c.index, bb["lower"], bb["upper"], color=S[0], alpha=0.12, label="Bollinger (20, 2σ)")
    a1.legend(ncol=4, loc="upper left"); a1.set_ylabel("Precio")
    r = ind.rsi(df["close"]).iloc[-250:]
    a2.plot(r.index, r, color=S[4]); a2.axhline(70, color=S[5], ls="--", lw=0.8); a2.axhline(30, color=S[5], ls="--", lw=0.8)
    a2.set_ylabel("RSI(14)"); a2.set_ylim(0, 100)
    plotting.save(fig, "f01_indicadores")


def f02_colas():
    r = np.log(data.synthetic_ohlc(20_000, seed=22, sigma=0.2)["close"]).diff().dropna()
    z = (r - r.mean()) / r.std()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8, 3.2))
    x = np.linspace(-6, 6, 400)
    a1.hist(z, bins=120, density=True, color=S[0], alpha=0.6, label="Rentabilidades (t, ν=4)")
    a1.plot(x, norm.pdf(x), color=S[1], label="Normal")
    a1.set_xlim(-6, 6); a1.legend(); a1.set_title("Densidad")
    a2.semilogy(x[x > 0], 2 * norm.sf(x[x > 0]), color=S[1], label="Normal")
    emp = np.array([np.mean(np.abs(z) > k) for k in x[x > 0]])
    a2.semilogy(x[x > 0], np.where(emp > 0, emp, np.nan), color=S[0], label="Empírica")
    a2.set_title("P(|Z| > k): colas"); a2.set_xlabel("k (desviaciones típicas)"); a2.legend()
    plotting.save(fig, "f02_colas")


def f03_kelly():
    f = np.linspace(0, 0.6, 400)
    fig, ax = plt.subplots(figsize=(7, 3.4))
    for i, (p, b) in enumerate([(0.55, 1.0), (0.40, 2.0), (0.60, 1.5)]):
        k = risk.kelly_fraction(p, b)
        ax.plot(f, risk.growth_rate(f, p, b) * 100, color=S[i], label=f"p={p:.0%}, b={b:g} (Kelly {k:.0%})")
        ax.plot(k, risk.growth_rate(k, p, b) * 100, "o", color=S[i])
    ax.axhline(0, color="k", lw=0.8); ax.set_ylim(-4, 10)
    ax.set_xlabel("Fracción arriesgada por operación f"); ax.set_ylabel("Crecimiento log. esperado (%/op.)")
    ax.legend(loc="upper right")
    plotting.save(fig, "f03_kelly")


def f04_ruina():
    rp = np.array([0.0025, 0.005, 0.01, 0.015, 0.02, 0.03, 0.04, 0.05])
    fig, ax = plt.subplots(figsize=(7, 3.4))
    for i, (p, b, lab) in enumerate([(0.45, 1.5, "ventaja pequeña (E=0,13R)"), (0.50, 1.5, "E=0,25R"),
                                     (0.40, 1.5, "sin ventaja (E=0)")]):
        pr = [risk.risk_of_ruin_mc(p, b, x, 0.30, 250, 6000, seed=1) for x in rp]
        ax.plot(rp * 100, np.array(pr) * 100, "o-", color=S[i], label=lab)
    ax.set_xlabel("Riesgo por operación (% del capital)"); ax.set_ylabel("P(drawdown ≥ 30 %) en 250 op. (%)")
    ax.legend(title="Payoff 1,5R")
    plotting.save(fig, "f04_ruina")


def f05_backtest():
    ohlc = data.synthetic_ohlc(2500, seed=4, mu=0.07, sigma=0.2, start="2015-01-02")
    c = ohlc["close"]
    res = bt.backtest(c, bt.sma_crossover(c, 50, 200), cost_bps=2)
    res_vt = bt.backtest(c, bt.vol_targeted(bt.sma_crossover(c, 50, 200), c, 0.12), cost_bps=2)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8, 4.6), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    a1.plot(res.index, (1 + res["ret"]).cumprod(), color=S[5], label="Comprar y mantener")
    a1.plot(res.index, res["equity"], color=S[0], label=f"SMA 50/200 (Sharpe {perf.sharpe(res['strategy']):.2f})".replace(".", ","))
    a1.plot(res.index, res_vt["equity"], color=S[1], label=f"… con vol objetivo 12 % (Sharpe {perf.sharpe(res_vt['strategy']):.2f})".replace(".", ","))
    a1.set_yscale("log"); a1.set_ylabel("Capital (log)"); a1.legend()
    a2.fill_between(res.index, risk.drawdown(res["equity"]), 0, color=S[0], alpha=0.5)
    a2.set_ylabel("Drawdown")
    plotting.save(fig, "f05_backtest")


def f06_sobreajuste():
    rng = np.random.default_rng(6)
    n_days, trials = 756, np.array([1, 2, 5, 10, 20, 50, 100, 200, 500, 1000])
    R = 0.01 * rng.standard_normal((n_days, trials.max()))  # estrategias SIN ventaja
    sr = R.mean(0) / R.std(0) * np.sqrt(252)
    mx = [np.max(sr[:k]) for k in trials]
    sd = np.sqrt(252 / n_days)
    fig, ax = plt.subplots(figsize=(7, 3.4))
    ax.semilogx(trials, mx, "o-", color=S[0], label="Mejor Sharpe in-sample (simulado)")
    ax.semilogx(trials, [perf.expected_max_sharpe(int(k), sd) if k > 1 else 0 for k in trials], "--", color=S[1],
                label="E[máx] teórico (Bailey–López de Prado)")
    ax.set_xlabel("Número de configuraciones probadas"); ax.set_ylabel("Sharpe anual")
    ax.set_title("Estrategias aleatorias de 3 años: todas tienen Sharpe verdadero 0"); ax.legend()
    plotting.save(fig, "f06_sobreajuste")


def f07_pares():
    df = data.synthetic_pair(900, seed=8)
    b = equity.hedge_ratio(df["y"].iloc[:300], df["x"].iloc[:300])
    z = equity.rolling_zscore(equity.spread(df["y"], df["x"], b), 60).iloc[300:]
    pos = equity.pair_positions(z)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8, 4.4), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    a1.plot(z.index, z, color=S[0], lw=1)
    for v, ls in [(2, "--"), (-2, "--"), (0.5, ":"), (-0.5, ":")]:
        a1.axhline(v, color=S[1] if abs(v) == 2 else S[5], ls=ls, lw=0.9)
    a1.set_ylabel("z-score del spread")
    a2.step(pos.index, pos, color=S[2], where="post"); a2.set_ylabel("Posición"); a2.set_yticks([-1, 0, 1])
    plotting.save(fig, "f07_pares")


def f08_carry():
    rng = np.random.default_rng(9)
    n = 252 * 8
    diff = 0.045  # diferencial de tipos a favor
    jumps = rng.random(n) < 1.5 / 252
    r_spot = 0.08 / np.sqrt(252) * rng.standard_normal(n) + 0.0002 + np.where(jumps, rng.normal(-0.035, 0.01, n), 0)
    idx = pd.bdate_range("2017-01-02", periods=n)
    carry = np.cumsum(np.full(n, diff / 252)); spot = np.cumsum(r_spot)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.5, 3.3), gridspec_kw={"width_ratios": [2, 1]})
    a1.plot(idx, carry * 100, color=S[2], label="Carry acumulado")
    a1.plot(idx, spot * 100, color=S[1], label="P&L del tipo de cambio")
    a1.plot(idx, (carry + spot) * 100, color=S[0], label="Total")
    a1.set_ylabel("% acumulado"); a1.legend()
    monthly = pd.Series(r_spot + diff / 252, index=idx).resample("ME").sum() * 100
    a2.hist(monthly, bins=30, color=S[0], alpha=0.7); a2.set_title(f"Rent. mensual: asimetría {monthly.skew():.2f}".replace(".", ","))
    a2.set_xlabel("%")
    plotting.save(fig, "f08_carry")


def f09_curvas():
    t = np.linspace(1 / 12, 2, 24)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.5, 3.3))
    a1.plot(t * 12, cm.synthetic_curve(70, t, 0.045, 0.06, 0.0), "o-", ms=3, color=S[0], label="Contango (almacenaje caro)")
    a1.plot(t * 12, cm.synthetic_curve(70, t, 0.045, 0.01, 0.15), "o-", ms=3, color=S[1], label="Backwardation (escasez)")
    a1.set_xlabel("Meses a vencimiento"); a1.set_ylabel("Precio futuro ($/bbl)"); a1.legend()
    # Spot plano, curva constante: el rolador gana/pierde el roll yield.
    months = np.arange(0, 37)
    for i, (name, slope) in enumerate([("Contango −1 %/mes", -0.01), ("Backwardation +1 %/mes", 0.01), ("Contado", 0.0)]):
        a2.plot(months, 100 * (1 + slope) ** months, color=S[i if i < 2 else 5], label=name)
    a2.set_xlabel("Meses"); a2.set_ylabel("Índice de exceso de rentabilidad"); a2.legend()
    a2.set_title("Mismo contado, distinta curva")
    plotting.save(fig, "f09_curvas")


def f10_bono():
    y = np.linspace(0.0, 0.10, 200)
    args = (100, 0.045, 10)
    p = np.array([rates.bond_price(100, 0.045, yy, 10) for yy in y])
    y0 = 0.045
    p0, d, c = rates.bond_price(100, 0.045, y0, 10), rates.modified_duration(100, 0.045, y0, 10), rates.convexity(100, 0.045, y0, 10)
    fig, ax = plt.subplots(figsize=(7, 3.4))
    ax.plot(y * 100, p, color=S[0], label="Precio exacto")
    ax.plot(y * 100, p0 - d * p0 * (y - y0), "--", color=S[1], label=f"Duración (D_mod={d:.2f})")
    ax.plot(y * 100, p0 + rates.price_change_approx(p0, d, c, y - y0), ":", color=S[2], lw=2, label=f"Duración + convexidad (C={c:.0f})")
    ax.set_xlabel("TIR (%)"); ax.set_ylabel("Precio"); ax.legend(); ax.set_title("Bono a 10 años, cupón 4,5 %")
    del args
    plotting.save(fig, "f10_bono")


def f11_opciones():
    s = np.linspace(70, 130, 300)
    K, T, r, v = 100, 30 / 365, 0.04, 0.25
    c0, p0 = float(op.bs_price(100, K, T, r, v)), float(op.bs_price(100, K, T, r, v, kind="put"))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.5, 3.3))
    a1.plot(s, op.payoff(s, [("call", K, 1, c0), ("put", K, 1, p0)]), color=S[0], label="Straddle largo (vencimiento)")
    now = op.bs_price(s, K, T / 2, r, v) + op.bs_price(s, K, T / 2, r, v, kind="put") - c0 - p0
    a1.plot(s, now, "--", color=S[0], label="… a mitad de plazo")
    cs = op.payoff(s, [("call", 100, 1, c0), ("call", 110, -1, float(op.bs_price(100, 110, T, r, v)))])
    a1.plot(s, cs, color=S[1], label="Call spread 100/110")
    a1.axhline(0, color="k", lw=0.8); a1.set_xlabel("Subyacente"); a1.set_ylabel("P&L"); a1.legend(fontsize=7)
    for i, days in enumerate([60, 20, 5]):
        g = op.greeks(s, K, days / 365, r, v)
        a2.plot(s, g["gamma"], color=S[i], label=f"Gamma, {days} días")
    a2.set_xlabel("Subyacente"); a2.legend(); a2.set_title("La gamma se concentra cerca del strike")
    plotting.save(fig, "f11_opciones")


def main():
    plotting.setup()
    for fn in (f01_indicadores, f02_colas, f03_kelly, f04_ruina, f05_backtest, f06_sobreajuste, f07_pares,
               f08_carry, f09_curvas, f10_bono, f11_opciones):
        fn()
        print("ok", fn.__name__)


if __name__ == "__main__":
    main()
