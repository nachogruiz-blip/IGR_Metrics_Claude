"""Backtest de estrategias de ejemplo con costes, métricas y gráfico (curso §5).

  python scripts/backtest.py --estrategia sma --rapida 20 --lenta 100
  python scripts/backtest.py --csv datos/SPY.csv --estrategia donchian --coste 2 --vol-objetivo 0.10
  python scripts/backtest.py --estrategia rsi
  python scripts/backtest.py --estrategia pares      # par sintético cointegrado
"""
import argparse

import pandas as pd

import _comun  # noqa: F401
from _comun import fmt, pct, table
from trader import backtest as bt
from trader import data, equity, performance as perf, plotting


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv"); ap.add_argument("--estrategia", choices=["sma", "donchian", "rsi", "pares"], default="sma")
    ap.add_argument("--rapida", type=int, default=20); ap.add_argument("--lenta", type=int, default=100)
    ap.add_argument("--coste", type=float, default=1.0, help="coste por unidad de rotación en pb (def. 1)")
    ap.add_argument("--vol-objetivo", type=float, help="escala la posición a esta vol anual (p. ej. 0.10)")
    ap.add_argument("--grafico", default="backtest", help="nombre del PNG en figuras/ ('' para no guardar)")
    args = ap.parse_args(argv)

    if args.estrategia == "pares":
        if args.csv:
            print("Aviso: «pares» usa un par sintético; --csv se ignora en esta estrategia.")
        df = data.synthetic_pair(1500)
        b = equity.hedge_ratio(df["y"].iloc[:500], df["x"].iloc[:500])  # estimado sólo con el pasado
        s = equity.spread(df["y"], df["x"], b)
        z = equity.rolling_zscore(s, 60)
        pos = equity.pair_positions(z)
        ret = (s.diff().fillna(0.0))  # rentabilidad log del spread ≈ cartera y − β x
        strat = pos.shift(1).fillna(0) * ret - args.coste * 1e-4 * pos.diff().abs().fillna(0) * (1 + abs(b))
        res = pd.DataFrame({"strategy": strat, "ret": ret, "pos": pos})
        res = res.iloc[500:]
        res["equity"] = (1 + res["strategy"]).cumprod()
        close = None
        print(f"β estimado (in-sample 500 sesiones): {b:.3f} · vida media {equity.half_life(s.iloc[:500]):.1f} días")
    else:
        ohlc = data.load_prices(args.csv) if args.csv else data.synthetic_ohlc(2000, seed=7, mu=0.06, sigma=0.22)
        close = ohlc["close"]
        if args.estrategia == "sma":
            pos = bt.sma_crossover(close, args.rapida, args.lenta)
        elif args.estrategia == "donchian":
            pos = bt.donchian_breakout(ohlc)
        else:
            pos = bt.rsi_reversion(close)
        if args.vol_objetivo:
            pos = bt.vol_targeted(pos, close, args.vol_objetivo)
        res = bt.backtest(close, pos, args.coste)

    s = perf.summary(res["strategy"])
    bh = perf.summary(res["ret"])
    rows = [(k, fmt(v, 3) if k in ("Sharpe", "Sortino", "Calmar", "Asimetría", "Curtosis exc.", "PSR(SR>0)") else pct(v), 
             fmt(bh[k], 3) if k in ("Sharpe", "Sortino", "Calmar", "Asimetría", "Curtosis exc.", "PSR(SR>0)") else pct(bh[k]))
            for k, v in s.items()]
    print(table(rows, ("Métrica", "Estrategia", "Comprar y mantener")))
    if close is not None:
        tr = bt.trades(close, pos.where(pos == 0, pos / pos.abs()))
        ts = perf.trade_stats(tr["ret"])
        print(f"\nOperaciones: {ts['n']} · acierto {pct(ts['hit_rate'])} · payoff {fmt(ts['payoff'])} · "
              f"profit factor {fmt(ts['profit_factor'])} · duración media {fmt(tr['days'].mean(), 1)} días")
    print(f"Exposición media |pos| {fmt(res['pos'].abs().mean())} · rotación anual {fmt(res['pos'].diff().abs().sum() / len(res) * 252, 1)}x")
    print("\nRecuerda: un Sharpe in-sample no es una predicción (curso §5.4). Prueba fuera de muestra.")
    if args.grafico:
        import matplotlib.pyplot as plt
        plotting.setup()
        fig, (a1, a2) = plt.subplots(2, 1, figsize=(8, 5), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
        a1.plot(res.index, res["equity"], label="Estrategia")
        a1.plot(res.index, (1 + res["ret"]).cumprod(), label="Activo / spread")
        a1.set_ylabel("Capital (base 1)"); a1.legend(); a1.set_title(f"Backtest «{args.estrategia}»")
        dd = res["equity"] / res["equity"].cummax() - 1
        a2.fill_between(res.index, dd, 0, color=plotting.SERIES[1], alpha=0.5)
        a2.set_ylabel("Drawdown")
        print(f"Gráfico: {plotting.save(fig, args.grafico)}")


if __name__ == "__main__":
    main()
