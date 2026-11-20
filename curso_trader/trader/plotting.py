"""Estilo común de figuras (curso, capítulo 0 «Cómo usar el curso»)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Orden fijo de series; nunca doble eje Y.
SERIES = ["#1f4e79", "#c0504d", "#4f9a5b", "#e3a21a", "#7b5ea7", "#5a5a5a"]
FIG_DIR = Path(__file__).resolve().parents[1] / "figuras"


def setup() -> None:
    plt.rcParams.update({
        "figure.dpi": 110,
        "savefig.dpi": 150,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.prop_cycle": matplotlib.cycler(color=SERIES),
        "font.size": 9,
        "legend.frameon": False,
    })


def save(fig, name: str, directory: Path | None = None) -> Path:
    directory = Path(directory) if directory else FIG_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.png"
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path
