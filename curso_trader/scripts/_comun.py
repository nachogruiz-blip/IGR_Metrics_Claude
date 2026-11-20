"""Utilidades compartidas por los scripts (ruta del paquete y formato)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def fmt(x: float, nd: int = 2) -> str:
    return f"{x:,.{nd}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def pct(x: float, nd: int = 2) -> str:
    return fmt(100 * x, nd) + " %"


def table(rows: list[tuple], headers: tuple | None = None) -> str:
    rows = [tuple(str(c) for c in r) for r in rows]
    if headers:
        rows = [tuple(headers)] + rows
    w = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    lines = ["  ".join(c.ljust(w[i]) if i == 0 else c.rjust(w[i]) for i, c in enumerate(r)) for r in rows]
    if headers:
        lines.insert(1, "-" * len(lines[0]))
    return "\n".join(lines)
