"""Diario de trading en CSV con estadísticas en R (curso §6.3).

  python scripts/diario.py nueva --fichero diario.csv --simbolo EURUSD --clase fx --lado largo \
      --entrada 1.0850 --stop 1.0825 --salida 1.0900 --tamano 200000 --setup ruptura --notas "tras IPC"
  python scripts/diario.py resumen --fichero diario.csv
  python scripts/diario.py demo        # crea datos/diario_demo.csv y lo resume
"""
import argparse
from datetime import date

import numpy as np

import _comun  # noqa: F401
from _comun import ROOT, fmt, pct, table
from trader import journal


def resumen(path):
    df = journal.load(path)
    s = journal.stats(df)
    print(f"Operaciones: {s['n']} · acierto {pct(s['hit_rate'])} · R ganador {fmt(s['avg_win'])} · R perdedor {fmt(s['avg_loss'])}")
    print(f"Esperanza: {fmt(s['expectancy_R'])} R/operación · profit factor {fmt(s['profit_factor'])} · P&L total {fmt(s['total_pnl'])}")
    print("\nPor setup:")
    bs = journal.by_setup(df)
    print(table([(k, int(r.n), pct(r.acierto), fmt(r.R_medio), fmt(r.pnl)) for k, r in bs.iterrows()],
                ("Setup", "N", "Acierto", "R medio", "P&L")))
    big = df[df["R"] < -1.2]
    if len(big):
        print(f"\n⚠ {len(big)} operación(es) perdieron más de 1,2R: ¿stops saltados o movidos? Revísalas.")


def demo():
    path = ROOT / "datos" / "diario_demo.csv"
    path.unlink(missing_ok=True)
    rng = np.random.default_rng(5)
    setups = {"ruptura": (0.40, 2.2), "pullback": (0.55, 1.3), "reversión": (0.50, 0.9)}
    for i in range(60):
        name = list(setups)[i % 3]
        p, b = setups[name]
        entry, stop = 100.0, 98.0
        exit_ = entry + (2 * b * rng.uniform(0.6, 1.4) if rng.random() < p else -2 * rng.uniform(0.8, 1.1))
        journal.add_trade(path, date=f"2026-{1 + i // 6:02d}-{1 + i % 6 * 4:02d}", symbol="DEMO", asset_class="equity",
                          side="largo", entry=entry, stop=stop, exit=round(exit_, 2), size=100, point_value=1,
                          fees=2, setup=name, notes="")
    print(f"Diario de ejemplo: {path}\n")
    resumen(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("nueva")
    n.add_argument("--fichero", required=True); n.add_argument("--fecha", default=str(date.today()))
    n.add_argument("--simbolo", required=True); n.add_argument("--clase", default="")
    n.add_argument("--lado", choices=["largo", "corto"], required=True)
    for k in ("entrada", "stop", "salida", "tamano"):
        n.add_argument(f"--{k}", type=float, required=True)
    n.add_argument("--valor-punto", type=float, default=1.0); n.add_argument("--comisiones", type=float, default=0.0)
    n.add_argument("--setup", default="sin_setup"); n.add_argument("--notas", default="")
    r = sub.add_parser("resumen"); r.add_argument("--fichero", required=True)
    sub.add_parser("demo")
    a = ap.parse_args(argv)
    if a.cmd == "nueva":
        journal.add_trade(a.fichero, date=a.fecha, symbol=a.simbolo, asset_class=a.clase, side=a.lado, entry=a.entrada,
                          stop=a.stop, exit=a.salida, size=a.tamano, point_value=a.valor_punto, fees=a.comisiones,
                          setup=a.setup, notes=a.notas)
        last = journal.load(a.fichero).iloc[-1]
        print(f"Anotada: P&L {fmt(last['pnl'])} = {fmt(last['R'])} R")
    elif a.cmd == "resumen":
        resumen(a.fichero)
    else:
        demo()


if __name__ == "__main__":
    main()
