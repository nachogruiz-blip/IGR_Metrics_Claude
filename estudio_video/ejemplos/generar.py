"""Regenera los ejemplos de esta carpeta: python ejemplos/generar.py (desde estudio_video/)."""

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from videostudio.backgrounds import BACKGROUNDS  # noqa: E402
from videostudio.plan import plan_from_text  # noqa: E402
from videostudio.render import render  # noqa: E402

AQUI = Path(__file__).parent

tiles = []
for name, f in BACKGROUNDS.items():
    im = f(3.0, 320, 180).copy()
    cv2.putText(im, name, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    tiles.append(im)
while len(tiles) % 4:
    tiles.append(np.zeros_like(tiles[0]))
grid = np.vstack([np.hstack(tiles[i : i + 4]) for i in range(0, len(tiles), 4)])
cv2.imwrite(str(AQUI / "entornos.png"), cv2.cvtColor(grid, cv2.COLOR_RGB2BGR))

sb = plan_from_text(
    "Vídeo de 10 segundos sobre un viaje: Despegamos hacia el espacio. "
    "Paseamos por la ciudad de noche. Volvemos a la playa."
)
sb.width, sb.height, sb.fps = 640, 360, 20
render(sb, AQUI / "viaje.mp4")
print("Ejemplos regenerados en", AQUI)
