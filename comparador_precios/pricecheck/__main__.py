"""CLI: ``python -m pricecheck "Sony WH-1000XM5" [--brand sony] [--demo] [--json]``."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from . import core, report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pricecheck", description="Compara el precio de un producto entre tiendas.")
    ap.add_argument("query", nargs="?", help="producto a buscar (modelo exacto mejor)")
    ap.add_argument("--brand", help="marca, para detectar la tienda oficial")
    ap.add_argument("--official-domain", action="append", default=[], help="dominio oficial adicional")
    ap.add_argument("--max-shops", type=int, default=12)
    ap.add_argument("--include-used", action="store_true", help="incluir reacondicionados/usados")
    ap.add_argument("--demo", action="store_true", help="datos ficticios sin red")
    ap.add_argument("--json", action="store_true", help="salida JSON en vez de Markdown")
    a = ap.parse_args(argv)

    if a.demo:
        from .demo import DEMO_BRAND, DEMO_QUERY, demo_sources
        sources, query, brand = demo_sources(), a.query or DEMO_QUERY, a.brand or DEMO_BRAND
    else:
        if not a.query:
            ap.error("indica el producto o usa --demo")
        sources, query, brand = core.live_sources(max_shops=a.max_shops), a.query, a.brand
    rep = core.check(query, sources, brand=brand, official_domains=tuple(a.official_domain),
                     include_used=a.include_used)
    if a.json:
        print(json.dumps(asdict(rep), default=str, ensure_ascii=False, indent=2))
    else:
        print(report.to_markdown(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
