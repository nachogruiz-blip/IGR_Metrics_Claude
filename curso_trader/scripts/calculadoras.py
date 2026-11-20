"""Calculadoras rápidas por clase de activo (curso §7–§12) y de liderazgo con signaturas (§15).

  python scripts/calculadoras.py opcion --spot 100 --strike 105 --dias 30 --vol 25 --tipo-interes 4
  python scripts/calculadoras.py iv --precio 2.35 --spot 100 --strike 105 --dias 30 --tipo-interes 4
  python scripts/calculadoras.py movimiento --spot 5200 --vol 14 --dias 1
  python scripts/calculadoras.py forward --par EURUSD --spot 1.085 --r-base 2.25 --r-cotizada 4.5 --dias 90
  python scripts/calculadoras.py cruce --par EURJPY --cotiza EURUSD=1.085 --cotiza USDJPY=151.2
  python scripts/calculadoras.py curva --precios 78.1 77.4 76.9 76.5 --meses 1 2 3 4
  python scripts/calculadoras.py crack --crudo 75 --gasolina 2.35 --gasoleo 2.55
  python scripts/calculadoras.py bono --cupon 4.25 --tir 4.4 --anos 10
  python scripts/calculadoras.py funding --tasa 0.01 --spot 65000 --futuro 66200 --dias 90
  python scripts/calculadoras.py liderazgo --csv datos/cierres.csv --a SPY --b EWJ --ventana 20
  python scripts/calculadoras.py liderazgo            # demo: B sigue a A con un periodo de retraso
"""
import argparse

import numpy as np

import _comun  # noqa: F401
from _comun import fmt, pct, table
from trader import commodities as cm
from trader import crypto, data, fx, options as op, rates
from trader import signature as sg


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("opcion")
    for k in ("spot", "strike", "dias", "vol"):
        o.add_argument(f"--{k}", type=float, required=True)
    o.add_argument("--tipo-interes", type=float, default=0.0); o.add_argument("--dividendo", type=float, default=0.0)
    i = sub.add_parser("iv")
    for k in ("precio", "spot", "strike", "dias"):
        i.add_argument(f"--{k}", type=float, required=True)
    i.add_argument("--tipo-interes", type=float, default=0.0); i.add_argument("--put", action="store_true")
    m = sub.add_parser("movimiento")
    for k in ("spot", "vol", "dias"):
        m.add_argument(f"--{k}", type=float, required=True)
    f = sub.add_parser("forward"); f.add_argument("--par", required=True)
    for k in ("spot", "r-base", "r-cotizada", "dias"):
        f.add_argument(f"--{k}", type=float, required=True)
    c = sub.add_parser("cruce"); c.add_argument("--par", required=True); c.add_argument("--cotiza", action="append", required=True)
    cu = sub.add_parser("curva"); cu.add_argument("--precios", type=float, nargs="+", required=True)
    cu.add_argument("--meses", type=float, nargs="+", required=True)
    k = sub.add_parser("crack")
    for x in ("crudo", "gasolina", "gasoleo"):
        k.add_argument(f"--{x}", type=float, required=True)
    b = sub.add_parser("bono")
    for x in ("cupon", "tir", "anos"):
        b.add_argument(f"--{x}", type=float, required=True)
    b.add_argument("--frecuencia", type=int, default=2)
    fu = sub.add_parser("funding"); fu.add_argument("--tasa", type=float, required=True, help="%% por 8 h")
    fu.add_argument("--spot", type=float); fu.add_argument("--futuro", type=float); fu.add_argument("--dias", type=float)
    li = sub.add_parser("liderazgo", help="¿qué activo se mueve antes? (área de Lévy, curso §15.4)")
    li.add_argument("--csv", help="CSV con fecha + una columna de cierre por activo")
    li.add_argument("--a"); li.add_argument("--b")
    li.add_argument("--ventana", type=int, default=20, help="sesiones por ventana (def. 20)")
    a = ap.parse_args(argv)

    if a.cmd == "opcion":
        T, r, q, s = a.dias / 365, a.tipo_interes / 100, a.dividendo / 100, a.vol / 100
        rows = []
        for kind in ("call", "put"):
            g = op.greeks(a.spot, a.strike, T, r, s, q, kind)
            rows.append((kind, fmt(float(op.bs_price(a.spot, a.strike, T, r, s, q, kind)), 4), fmt(g["delta"], 3),
                         fmt(g["gamma"], 4), fmt(g["vega"], 4), fmt(g["theta"], 4)))
        print(table(rows, ("Tipo", "Precio", "Delta", "Gamma", "Vega/pt vol", "Theta/día")))
        print(f"Movimiento esperado 1σ hasta vencimiento: ±{fmt(op.expected_move(a.spot, s, a.dias))}")
    elif a.cmd == "iv":
        iv = op.implied_vol(a.precio, a.spot, a.strike, a.dias / 365, a.tipo_interes / 100, kind="put" if a.put else "call")
        print(f"Volatilidad implícita: {pct(iv)} · movimiento esperado ±{fmt(op.expected_move(a.spot, iv, a.dias))}")
    elif a.cmd == "movimiento":
        em = op.expected_move(a.spot, a.vol / 100, a.dias)
        print(f"±1σ: {fmt(em)} ({fmt(a.spot - em)} – {fmt(a.spot + em)}) · ±2σ: {fmt(2 * em)}")
        print("Nota: usa días naturales con vol implícita; con vol histórica diaria, √(sesiones/252).")
    elif a.cmd == "forward":
        F = fx.forward_rate(a.spot, a.r_cotizada / 100, a.r_base / 100, a.dias / 360)
        print(f"Forward {a.dias:g} días: {F:.5f} · puntos forward {fx.forward_points(a.spot, F, a.par):+.1f} pips")
        print(f"Carry anual de estar largo {a.par[:3]}: {pct((a.r_base - a.r_cotizada) / 100)} (se pierde si es negativo)")
    elif a.cmd == "cruce":
        q = {k.upper(): float(v) for k, v in (x.split("=") for x in a.cotiza)}
        print(f"{a.par.upper()} = {fx.cross_rate(q, a.par):.5f}")
    elif a.cmd == "curva":
        t = [m / 12 for m in a.meses]
        print(f"Forma: {cm.curve_shape(a.precios)}")
        ry = cm.roll_yield_curve(a.precios, t)
        print(table([(k, pct(v)) for k, v in ry.items()], ("Tramo (años)", "Roll yield anual")))
    elif a.cmd == "crack":
        print(f"Crack 3:2:1 = {fmt(cm.crack_spread_321(a.crudo, a.gasolina, a.gasoleo))} $/bbl")
    elif a.cmd == "bono":
        c, y = a.cupon / 100, a.tir / 100
        p = rates.bond_price(100, c, y, a.anos, a.frecuencia)
        print(f"Precio {fmt(p, 4)} · D. Macaulay {fmt(rates.macaulay_duration(100, c, y, a.anos, a.frecuencia))} · "
              f"D. modificada {fmt(rates.modified_duration(100, c, y, a.anos, a.frecuencia))} · "
              f"convexidad {fmt(rates.convexity(100, c, y, a.anos, a.frecuencia), 1)}")
        print(f"DV01 por 100 de nominal: {fmt(rates.dv01(100, c, y, a.anos, a.frecuencia), 4)} · por 1 M: "
              f"{fmt(rates.dv01(100, c, y, a.anos, a.frecuencia) * 1e4)}")
    elif a.cmd == "funding":
        print(f"Funding anualizado: {pct(crypto.annualized_funding(a.tasa / 100))} (lo pagan los largos si es > 0)")
        if a.spot and a.futuro and a.dias:
            print(f"Base anualizada del futuro: {pct(crypto.annualized_basis(a.spot, a.futuro, a.dias))}")
    elif a.cmd == "liderazgo":
        if a.csv:
            df = data.load_prices(a.csv)
            na, nb = a.a or df.columns[0], a.b or df.columns[1]
            r = np.log(df[[na, nb]]).diff().dropna()
            ra, rb = r[na].to_numpy(), r[nb].to_numpy()
        else:
            na, nb = "A", "B"
            rng = np.random.default_rng(15)
            x = rng.standard_normal(2001)
            ra, rb = x[1:], 0.4 * x[:-1] + np.sqrt(1 - 0.4**2) * rng.standard_normal(2000)
            print("Demo sintético: r_B(t) = 0,4·r_A(t−1) + ruido → puntuación esperada 0,40.")
        score, se = sg.lead_lag_score(ra, rb, a.ventana)
        lead = na if score > 0 else nb
        print(table([("Puntuación A→B", fmt(score, 3)), ("Error típico", fmt(se, 3)), ("z", fmt(score / se, 2)),
                     ("Correlación simultánea", fmt(float(np.corrcoef(ra, rb)[0, 1]), 3))], ("Medida", "Valor")))
        if abs(score) > 2 * se:
            print(f"{lead} tiende a moverse antes (|z| > 2). Comprueba que no es un artefacto de horarios de cierre distintos.")
        else:
            print("Sin liderazgo significativo (|z| ≤ 2).")


if __name__ == "__main__":
    main()
