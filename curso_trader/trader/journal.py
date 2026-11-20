"""Diario de operaciones en CSV y sus estadísticas en múltiplos de R (curso §6 y §13)."""
from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from .performance import trade_stats

COLUMNS = ["date", "symbol", "asset_class", "side", "entry", "stop", "exit", "size",
           "point_value", "fees", "setup", "notes"]


def add_trade(path: str | Path, **trade) -> None:
    path = Path(path)
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        if new:
            w.writeheader()
        w.writerow({c: trade.get(c, "") for c in COLUMNS})


def load(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    for c in ("entry", "stop", "exit", "size", "point_value", "fees"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["point_value"] = df["point_value"].fillna(1.0)
    df["fees"] = df["fees"].fillna(0.0)
    return enrich(df)


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Añade P&L neto, riesgo inicial (1R) y múltiplo R = P&L / 1R."""
    df = df.copy()
    sign = df["side"].str.lower().map({"long": 1, "largo": 1, "buy": 1, "short": -1, "corto": -1, "sell": -1})
    df["pnl"] = sign * (df["exit"] - df["entry"]) * df["size"] * df["point_value"] - df["fees"]
    df["risk"] = (df["entry"] - df["stop"]).abs() * df["size"] * df["point_value"]
    df["R"] = df["pnl"] / df["risk"]
    return df


def stats(df: pd.DataFrame) -> dict:
    out = trade_stats(df["R"])
    out["total_pnl"] = float(df["pnl"].sum())
    out["expectancy_R"] = out.pop("expectancy")
    return out


def by_setup(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("setup")
    return pd.DataFrame({"n": g.size(), "acierto": g["R"].apply(lambda r: (r > 0).mean()),
                         "R_medio": g["R"].mean(), "pnl": g["pnl"].sum()}).sort_values("R_medio", ascending=False)
