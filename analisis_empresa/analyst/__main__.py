"""CLI: ``python -m analyst TICKER [--demo] [--out informe.md]``."""

from __future__ import annotations

import argparse
import sys

from . import core, data, report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m analyst",
                                 description="Analiza una empresa cotizada y dice si comprar, vender o esperar.")
    ap.add_argument("ticker", help="Ticker de Yahoo: SAN.MC, ITX.MC, AAPL, ASML.AS… "
                                   "(con --demo: DEMO-COMPRA, DEMO-ESPERA, DEMO-VENDE, DEMO-CARA)")
    ap.add_argument("--demo", action="store_true", help="Datos sintéticos (sin red)")
    ap.add_argument("--years", type=int, default=5, help="Años de precios (por defecto 5)")
    ap.add_argument("--rf", type=float, default=None, help="Tipo libre de riesgo (fracción, p. ej. 0.03)")
    ap.add_argument("--out", help="Guardar el informe Markdown en este archivo")
    args = ap.parse_args(argv)
    try:
        cd = data.demo(args.ticker) if args.demo else data.fetch(args.ticker, args.years)
    except Exception as e:  # noqa: BLE001
        print(f"Error al obtener datos: {e}", file=sys.stderr)
        return 1
    if args.rf is not None:
        cd.risk_free = args.rf
    md = report.to_markdown(core.analyze(cd))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(md + "\n")
        print(f"Informe guardado en {args.out}")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
