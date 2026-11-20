"""Informe de riesgo de cartera: volatilidad, VaR/ES, contribuciones y estrés (curso §4.4–4.6).

  python scripts/informe_riesgo.py                                   # demo
  python scripts/informe_riesgo.py --csv precios.csv --pos SPY=50000 --pos TLT=-20000 --pos GLD=15000
El CSV tiene fecha + una columna de cierre por activo; ``--pos`` es nocional firmado en divisa de cuenta.
"""
import argparse

import numpy as np

import _comun  # noqa: F401
from _comun import fmt, pct, table
from trader import data, risk


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv"); ap.add_argument("--pos", action="append", default=[])
    ap.add_argument("--capital", type=float, default=100_000)
    ap.add_argument("--ventana", type=int, default=500, help="sesiones para estimar (def. 500)")
    ap.add_argument("--estres", type=float, default=-10, help="shock común en %% (def. −10)")
    args = ap.parse_args(argv)
    if args.csv:
        px = data.load_prices(args.csv)
        pos = {k: float(v) for k, v in (p.split("=") for p in args.pos)}
    else:
        print("(demo: tres activos sintéticos correlacionados)")
        px = data.synthetic_universe(["ACCIONES", "BONOS", "ORO"], 750, rho=0.3)
        pos = {"ACCIONES": 60_000, "BONOS": 30_000, "ORO": -15_000}
    names = list(pos)
    rets = px[names].pct_change().dropna().iloc[-args.ventana:]
    w = np.array([pos[n] for n in names])
    pnl = rets.values @ w
    cov = rets.cov().values
    sd = risk.portfolio_vol(w, cov)
    rc = risk.risk_contributions(w, cov)
    print(f"\nCapital {fmt(args.capital)} · nocional bruto {fmt(np.abs(w).sum())} ({fmt(np.abs(w).sum() / args.capital)}x)"
          f" · neto {fmt(w.sum())}")
    vols = rets.std().values * np.sqrt(252)
    print(table([(n, fmt(pos[n]), pct(v), fmt(r), pct(r / sd)) for n, v, r in zip(names, vols, rc)],
                ("Activo", "Nocional", "Vol anual", "Contrib. σ diaria", "% riesgo")))
    print(f"\nσ diaria de la cartera: {fmt(sd)} ({pct(sd / args.capital)} del capital) · anual {pct(sd * np.sqrt(252) / args.capital)}")
    rows = []
    for a in (0.95, 0.99):
        rows.append((f"{a:.0%}", fmt(risk.var_parametric(0, sd, a)), fmt(risk.var_historical(pnl, a)),
                     fmt(risk.es_parametric(0, sd, a)), fmt(risk.es_historical(pnl, a))))
    print("\nVaR / ES a 1 día (pérdida positiva):")
    print(table(rows, ("Confianza", "VaR normal", "VaR hist.", "ES normal", "ES hist.")))
    print(f"VaR 99 % a 10 días (raíz del tiempo): {fmt(risk.scale_var(risk.var_historical(pnl, 0.99), 10))}")
    print(f"Peor día del histórico: {fmt(pnl.min())} · max drawdown simulado de la cartera: "
          f"{pct(risk.max_drawdown(args.capital + np.cumsum(pnl)))}")
    print(f"\nEstrés: todos los activos {args.estres:+g} % → P&L {fmt(w.sum() * args.estres / 100)}")
    print("\nCorrelaciones:\n" + rets.corr().round(2).to_string())
    if sd / args.capital > 0.02:
        print("\n⚠ La σ diaria supera el 2 % del capital: reduce tamaño o diversifica.")


if __name__ == "__main__":
    main()
