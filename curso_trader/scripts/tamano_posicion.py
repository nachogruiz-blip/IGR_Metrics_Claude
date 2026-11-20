"""Calculadora de tamaño de posición por riesgo fijo (curso §4.2, §7, §8, §9, §12).

Ejemplos:
  python scripts/tamano_posicion.py accion --capital 50000 --riesgo 0.5 --entrada 182.4 --stop 176.9
  python scripts/tamano_posicion.py fx --capital 20000 --riesgo 1 --par EURUSD --tipo 1.0850 --stop-pips 25
  python scripts/tamano_posicion.py fx --capital 20000 --par EURGBP --tipo 0.855 --stop-pips 20 --conversion 1.27
  python scripts/tamano_posicion.py futuro --capital 250000 --riesgo 0.75 --simbolo CL --entrada 74.2 --stop 72.6
  python scripts/tamano_posicion.py atr --capital 50000 --riesgo 1 --atr 3.2 --mult 2 --precio 120
  python scripts/tamano_posicion.py cripto --capital 10000 --riesgo 1 --entrada 65000 --stop 63000 --apalancamiento 5
"""
import argparse

import _comun  # noqa: F401
from _comun import fmt, pct
from trader import commodities as cm
from trader import crypto, fx, risk


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="modo", required=True)

    def common(p):
        p.add_argument("--capital", type=float, required=True)
        p.add_argument("--riesgo", type=float, default=1.0, help="%% del capital arriesgado (def. 1)")

    a = sub.add_parser("accion"); common(a)
    a.add_argument("--entrada", type=float, required=True); a.add_argument("--stop", type=float, required=True)
    a.add_argument("--objetivo", type=float)
    f = sub.add_parser("fx"); common(f)
    f.add_argument("--par", required=True); f.add_argument("--tipo", type=float, required=True)
    f.add_argument("--stop-pips", type=float, required=True); f.add_argument("--cuenta", default="USD")
    f.add_argument("--conversion", type=float, help="unidades de cuenta por unidad de divisa cotizada")
    u = sub.add_parser("futuro"); common(u)
    u.add_argument("--simbolo", required=True, choices=sorted(cm.CONTRACTS))
    u.add_argument("--entrada", type=float, required=True); u.add_argument("--stop", type=float, required=True)
    t = sub.add_parser("atr"); common(t)
    t.add_argument("--atr", type=float, required=True); t.add_argument("--mult", type=float, default=2.0)
    t.add_argument("--precio", type=float, required=True); t.add_argument("--valor-punto", type=float, default=1.0)
    c = sub.add_parser("cripto"); common(c)
    c.add_argument("--entrada", type=float, required=True); c.add_argument("--stop", type=float, required=True)
    c.add_argument("--apalancamiento", type=float, default=1.0)
    args = ap.parse_args(argv)
    r = args.riesgo / 100
    riesgo_dinero = args.capital * r
    print(f"Capital {fmt(args.capital)} · riesgo {pct(r)} = {fmt(riesgo_dinero)} por operación\n")

    if args.modo == "accion":
        n = risk.position_size_stop(args.capital, r, args.entrada, args.stop)
        side = "LARGO" if args.stop < args.entrada else "CORTO"
        print(f"{side}: {int(n)} acciones · nocional {fmt(n * args.entrada)} ({pct(n * args.entrada / args.capital)} del capital)")
        print(f"Distancia al stop: {fmt(abs(args.entrada - args.stop))} ({pct(abs(args.entrada / args.stop - 1))})")
        if args.objetivo:
            rr = abs(args.objetivo - args.entrada) / abs(args.entrada - args.stop)
            print(f"Objetivo {args.objetivo}: relación beneficio/riesgo = {fmt(rr)}R · acierto mínimo para no perder {pct(1 / (1 + rr))}")
    elif args.modo == "fx":
        pv = fx.pip_value(args.par, args.tipo, 1.0, args.cuenta, args.conversion)
        lots = fx.lots_for_risk(args.capital, r, args.stop_pips, pv)
        base, _ = fx.split_pair(args.par)
        print(f"Valor del pip (1 lote estándar): {fmt(pv)} {args.cuenta}")
        print(f"Tamaño: {fmt(lots)} lotes = {fmt(lots * fx.STANDARD_LOT, 0)} {base}")
        print(f"Pérdida al stop ({args.stop_pips:g} pips): {fmt(lots * pv * args.stop_pips)} {args.cuenta}")
    elif args.modo == "futuro":
        k = cm.CONTRACTS[args.simbolo]
        n = cm.futures_position_size(args.simbolo, args.capital, r, args.entrada, args.stop)
        per = abs(args.entrada - args.stop) * k.multiplier
        print(f"{k.name} ({k.exchange}) · cotiza en {k.unit} · multiplicador {k.multiplier:g} $/punto · tick {k.tick:g} = {fmt(k.tick_value)} $")
        print(f"Riesgo por contrato al stop: {fmt(per)} $ → {n} contrato(s)")
        print(f"Nocional: {fmt(n * cm.contract_value(args.simbolo, args.entrada))} $")
        if n == 0:
            print("⚠ El stop es demasiado amplio para este capital: usa micro-contratos o reduce la distancia.")
    elif args.modo == "atr":
        n = risk.atr_position_size(args.capital, r, args.atr, args.mult, args.valor_punto)
        print(f"Stop a {args.mult:g}·ATR = {fmt(args.mult * args.atr)} → {int(n)} unidades · nocional {fmt(n * args.precio * args.valor_punto)}")
    elif args.modo == "cripto":
        qty = riesgo_dinero / abs(args.entrada - args.stop)
        notional = qty * args.entrada
        side = "long" if args.stop < args.entrada else "short"
        liq = crypto.liquidation_price(args.entrada, args.apalancamiento, side=side) if args.apalancamiento > 1 else float("nan")
        print(f"Cantidad: {qty:.6f} · nocional {fmt(notional)} · margen con {args.apalancamiento:g}x: {fmt(notional / args.apalancamiento)}")
        if args.apalancamiento > 1:
            print(f"Liquidación aprox.: {fmt(liq)}")
            if (side == "long" and liq >= args.stop) or (side == "short" and liq <= args.stop):
                print("⚠ La liquidación llega ANTES que el stop: baja el apalancamiento.")


if __name__ == "__main__":
    main()
