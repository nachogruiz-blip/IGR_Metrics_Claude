"""Estilo común de figuras (paleta categórica validada, marcas finas, rejilla discreta)."""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Orden fijo: nunca se cicla ni se reordena por rango.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
SURFACE = "#fcfcfb"
NEUTRAL = "#9a9890"

def _default_fig_dir() -> Path:
    """$MALLIAVIN_FIG_DIR, o figures/ del repositorio si la librería está instalada en modo
    editable, o ./figures en el directorio actual en otro caso."""
    env = os.environ.get("MALLIAVIN_FIG_DIR")
    if env:
        return Path(env)
    repo = Path(__file__).resolve().parents[2]
    if (repo / "pyproject.toml").exists():
        return repo / "figures"
    return Path.cwd() / "figures"


FIG_DIR = _default_fig_dir()


def setup() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "axes.edgecolor": GRID,
            "axes.labelcolor": TEXT_2,
            "axes.titlecolor": TEXT,
            "axes.titleweight": "bold",
            "axes.titlesize": 11,
            "axes.labelsize": 9,
            "axes.grid": True,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.prop_cycle": matplotlib.cycler(color=SERIES),
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "xtick.color": TEXT_2,
            "ytick.color": TEXT_2,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "lines.linewidth": 2.0,
            "legend.frameon": False,
            "legend.fontsize": 8,
            "legend.labelcolor": TEXT_2,
            "font.size": 9,
            "savefig.dpi": 150,
            "savefig.bbox": "tight",
        }
    )


def save(fig, name: str) -> Path:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / f"{name}.png"
    fig.savefig(path)
    plt.close(fig)
    return path
