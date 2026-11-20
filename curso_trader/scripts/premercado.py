"""Hoja de preparación diaria: niveles, volatilidad, régimen y checklist (curso §13.1).

  python scripts/premercado.py                      # demo con datos sintéticos
  python scripts/premercado.py --csv datos/SPY.csv --csv datos/EURUSD.csv
  python scripts/premercado.py --hora-utc 13        # además, sesiones FX abiertas
El CSV debe tener fecha + open, high, low, close (volume opcional).
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import _comun  # noqa: F401
from _comun import fmt, pct, table
from trader import data, fx
from trader import indicators as ind

CHECKLIST = [
    "Calendario: datos macro, bancos centrales, resultados y vencimientos de hoy",
    "Noticias de la noche y movimientos en Asia/Europa; futuros del índice",
    "Riesgo abierto: ¿suma de stops < límite diario? ¿correlaciones concentradas?",
    "Niveles marcados (pivotes, máx/mín previos, medias) y escenarios si/entonces",
    "Tamaño calculado ANTES de entrar (scripts/tamano_posicion.py)",
    "Estado mental: ¿descansado? ¿pérdida de ayer digerida? Límite de pérdida diario",
]


def report(name: str, df) -> list[tuple]:
    c = df["close"]
    last = df.iloc[-1]
    a = ind.atr(df).iloc[-1]
    vol = ind.realized_vol(c, 20).iloc[-1]
    sma50, sma200 = ind.sma(c, 50).iloc[-1], ind.sma(c, 200).iloc[-1]
    piv = ind.pivot_points(last["high"], last["low"], last["close"])
    trend = "alcista" if c.iloc[-1] > sma200 and sma50 > sma200 else "bajista" if c.iloc[-1] < sma200 and sma50 < sma200 else "lateral/transición"
    print(f"\n=== {name} · último dato {df.index[-1]:%Y-%m-%d} ===")
    print(f"Cierre {fmt(last['close'], 4)} · ATR(14) {fmt(a, 4)} ({pct(a / last['close'])}) · vol 20d {pct(vol)}"
          f" · RSI(14) {fmt(ind.rsi(c).iloc[-1], 1)}")
    print(f"Régimen: {trend} · dist. SMA50 {pct(c.iloc[-1] / sma50 - 1)} · dist. SMA200 {pct(c.iloc[-1] / sma200 - 1)}")
    print(f"Rango esperado hoy (1σ): ±{fmt(last['close'] * vol / np.sqrt(252), 4)}")
    print(table([(k, fmt(v, 4)) for k, v in piv.items()], ("Pivote", "Nivel")))
    hi20, lo20 = df["high"].iloc[-20:].max(), df["low"].iloc[-20:].min()
    print(f"Máx/mín 20 sesiones: {fmt(hi20, 4)} / {fmt(lo20, 4)}")
    return [(name, fmt(last["close"], 4), pct(vol), trend)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", action="append", default=[], help="CSV OHLC (repetible)")
    ap.add_argument("--hora-utc", type=float, help="hora UTC para las sesiones FX (def. ahora)")
    args = ap.parse_args(argv)
    print("CHECKLIST PREMERCADO")
    for i, item in enumerate(CHECKLIST, 1):
        print(f"  [{i}] {item}")
    h = args.hora_utc if args.hora_utc is not None else datetime.now(timezone.utc).hour
    print(f"\nSesiones FX abiertas a las {h:g}h UTC: {', '.join(fx.open_sessions(h)) or 'ninguna'}")
    if args.csv:
        sets = [(Path(p).stem, data.load_prices(p)) for p in args.csv]
    else:
        print("(demo: datos sintéticos; usa --csv para tus activos)")
        sets = [("DEMO-ACCION", data.synthetic_ohlc(400, 100, 0.10, 0.25, seed=11)),
                ("DEMO-FX", data.synthetic_ohlc(400, 1.08, 0.0, 0.07, seed=12)),
                ("DEMO-CRUDO", data.synthetic_ohlc(400, 75, 0.0, 0.35, seed=13))]
    rows = []
    for name, df in sets:
        rows += report(name, df)
    print("\nRESUMEN\n" + table(rows, ("Activo", "Cierre", "Vol 20d", "Régimen")))


if __name__ == "__main__":
    main()
