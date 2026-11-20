"""Entornos procedurales animados.

Cada entorno es una función ``f(t, w, h) -> ndarray (h, w, 3) uint8`` (RGB) que depende sólo
del tiempo ``t`` en segundos: el mismo ``t`` produce siempre la misma imagen. Se usan como fondo
de las escenas generadas desde texto y como «entorno» al sustituir el fondo de la cámara.
Todo está vectorizado con numpy (sin bucles por píxel).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Callable

import numpy as np

Background = Callable[[float, int, int], np.ndarray]


@lru_cache(maxsize=16)
def _grid(w: int, h: int) -> tuple[np.ndarray, np.ndarray]:
    """Coordenadas normalizadas x, y ∈ [0, 1) de tamaño (h, w)."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    return x / w, y / h


def _rgb(c) -> np.ndarray:
    return np.asarray(c, dtype=np.float32).reshape(1, 1, 3)


def _vgrad(h: int, w: int, top, bottom, y=None) -> np.ndarray:
    if y is None:
        y = _grid(w, h)[1]
    a = y[..., None]
    return _rgb(top) * (1 - a) + _rgb(bottom) * a


def _to_u8(img: np.ndarray) -> np.ndarray:
    return np.clip(img, 0, 255).astype(np.uint8)


def _points(seed: int, n: int) -> np.ndarray:
    """``n`` puntos pseudoaleatorios fijos (x, y, fase, tamaño) ∈ [0, 1)."""
    return np.random.default_rng(seed).random((n, 4)).astype(np.float32)


def _splat(img: np.ndarray, xs: np.ndarray, ys: np.ndarray, color, alpha: np.ndarray, r: int = 1):
    """Pinta puntos cuadrados de radio ``r`` (vectorizado sobre los puntos)."""
    h, w = img.shape[:2]
    xi = np.clip(xs.astype(int), 0, w - 1)
    yi = np.clip(ys.astype(int), 0, h - 1)
    col = _rgb(color).reshape(3)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            yy = np.clip(yi + dy, 0, h - 1)
            xx = np.clip(xi + dx, 0, w - 1)
            a = alpha[:, None]
            img[yy, xx] = img[yy, xx] * (1 - a) + col * a


# ---------------------------------------------------------------- entornos


def studio(t: float, w: int, h: int) -> np.ndarray:
    """Estudio: degradado radial gris azulado con un leve foco que respira."""
    x, y = _grid(w, h)
    d = np.sqrt((x - 0.5) ** 2 + ((y - 0.45) * h / w) ** 2)
    glow = 0.85 + 0.05 * np.sin(2 * np.pi * t / 6)
    a = np.clip(1 - d * 1.6 / glow, 0, 1)[..., None]
    return _to_u8(_rgb((30, 34, 44)) * (1 - a) + _rgb((120, 130, 150)) * a)


def gradient(t: float, w: int, h: int) -> np.ndarray:
    """Degradado diagonal cuyo tono gira lentamente."""
    x, y = _grid(w, h)
    s = (x + y) / 2
    ph = 2 * np.pi * t / 12
    r = 110 + 90 * np.sin(2 * np.pi * s + ph)
    g = 90 + 70 * np.sin(2 * np.pi * s + ph + 2.1)
    b = 150 + 90 * np.sin(2 * np.pi * s + ph + 4.2)
    return _to_u8(np.stack([r, g, b], axis=-1))


def beach(t: float, w: int, h: int) -> np.ndarray:
    """Playa: cielo, sol, mar con olas y arena."""
    x, y = _grid(w, h)
    img = _vgrad(h, w, (90, 170, 235), (200, 230, 250), y / 0.55)
    # sol
    d = np.sqrt((x - 0.75) ** 2 + ((y - 0.22) * h / w) ** 2)
    sun = np.clip(1 - d / 0.07, 0, 1)[..., None]
    halo = np.clip(1 - d / 0.25, 0, 1)[..., None] ** 2 * 0.35
    img = img * (1 - sun) + _rgb((255, 240, 180)) * sun
    img = img + _rgb((255, 220, 150)) * halo
    # mar
    horizon = 0.55
    shore = 0.78 + 0.015 * np.sin(2 * np.pi * (x * 3 - t * 0.4))
    sea = (y >= horizon) & (y < shore)
    depth = np.clip((y - horizon) / (shore - horizon), 0, 1)
    waves = 0.5 + 0.5 * np.sin(2 * np.pi * (x * 6 + y * 40 - t * 0.8))
    sea_col = _vgrad(h, w, (20, 90, 150), (40, 170, 190), depth) + (waves * 18 * depth)[..., None]
    foam = (np.abs(y - shore) < 0.012)[..., None]
    img = np.where(sea[..., None], sea_col, img)
    img = np.where(foam & (y >= horizon)[..., None], _rgb((245, 250, 250)), img)
    sand = (y >= shore)[..., None]
    img = np.where(sand, _vgrad(h, w, (235, 215, 170), (210, 185, 135), (y - 0.78) / 0.22), img)
    return _to_u8(img)


def space(t: float, w: int, h: int) -> np.ndarray:
    """Espacio: nebulosa oscura con estrellas que titilan y se desplazan."""
    x, y = _grid(w, h)
    neb = 0.5 + 0.5 * np.sin(4 * x + 3 * y + 0.2 * t) * np.cos(3 * x - 5 * y)
    img = _rgb((5, 5, 20)) + neb[..., None] * _rgb((40, 15, 60))
    p = _points(7, 220)
    xs = ((p[:, 0] + t * 0.01 * (0.5 + p[:, 3])) % 1) * w
    ys = p[:, 1] * h
    alpha = 0.55 + 0.45 * np.sin(2 * np.pi * (p[:, 2] + t * (0.3 + p[:, 3])))
    _splat(img, xs, ys, (255, 255, 255), alpha, r=0)
    big = p[:, 3] > 0.85
    _splat(img, xs[big], ys[big], (200, 220, 255), alpha[big] * 0.8, r=1)
    return _to_u8(img)


def city(t: float, w: int, h: int) -> np.ndarray:
    """Ciudad de noche: cielo violeta, rascacielos y ventanas encendidas."""
    x, y = _grid(w, h)
    img = _vgrad(h, w, (20, 15, 50), (120, 60, 110), y / 0.8)
    rng = np.random.default_rng(3)
    n = 14
    edges = np.sort(rng.random(n - 1))
    edges = np.concatenate([[0.0], edges, [1.0]])
    tops = 0.25 + 0.45 * rng.random(n)
    idx = np.clip(np.searchsorted(edges, x, side="right") - 1, 0, n - 1)
    top = tops[idx]
    building = y >= top
    shade = 25 + 20 * (idx % 3)
    img = np.where(building[..., None], np.stack([shade, shade, shade + 15], -1).astype(np.float32), img)
    # ventanas: rejilla, encendidas según un hash que cambia lentamente
    gx = np.floor(x * w / 10)
    gy = np.floor(y * h / 14)
    cell_on = (np.sin(gx * 12.9898 + gy * 78.233 + np.floor(t / 2) * 3.1) * 43758.5) % 1 > 0.55
    in_cell = ((x * w) % 10 > 3) & ((y * h) % 14 > 5)
    win = building & in_cell & cell_on & (y > top + 0.02)
    img = np.where(win[..., None], _rgb((255, 210, 120)), img)
    return _to_u8(img)


def forest(t: float, w: int, h: int) -> np.ndarray:
    """Bosque: niebla verde, árboles triangulares en capas que se mecen."""
    x, y = _grid(w, h)
    img = _vgrad(h, w, (170, 210, 190), (60, 110, 70), y)
    rng = np.random.default_rng(11)
    for layer, (col, base, size) in enumerate(
        [((70, 120, 90), 0.70, 0.35), ((40, 90, 55), 0.82, 0.45), ((20, 55, 30), 0.97, 0.55)]
    ):
        cx = rng.random(9)[:, None, None] + 0.004 * np.sin(t * (0.8 + layer * 0.3))
        hh = size * (0.7 + 0.3 * rng.random(9))[:, None, None]
        half = 0.07 + 0.03 * layer
        # triángulo: |x - cx| < half · (y - (base - hh)) / hh, por encima de base
        rel = (y[None] - (base - hh)) / hh
        tri = (rel > 0) & (rel < 1.2) & (np.abs(x[None] - cx) < half * rel * w / h * 0.6)
        mask = tri.any(axis=0)
        mask |= y > base
        img = np.where(mask[..., None], _rgb(col), img)
    return _to_u8(img)


def fire(t: float, w: int, h: int) -> np.ndarray:
    """Fuego: llamas procedurales (suma de senos que suben)."""
    x, y = _grid(w, h)
    n = (
        np.sin(x * 13 + t * 2.0) * 0.5
        + np.sin(x * 29 - t * 3.1 + y * 7) * 0.3
        + np.sin(x * 61 + t * 5.3 + y * 17) * 0.2
    )
    heat = np.clip((y - 0.25 + 0.18 * n) * 1.6 + 0.08 * np.sin(y * 40 + t * 9), 0, 1)
    r = 255 * np.clip(heat * 1.6, 0, 1)
    g = 255 * np.clip(heat * 1.6 - 0.6, 0, 1)
    b = 255 * np.clip(heat * 2.2 - 1.8, 0, 1)
    return _to_u8(np.stack([r, g, b], -1) + _rgb((15, 3, 3)))


def snow(t: float, w: int, h: int) -> np.ndarray:
    """Nieve: cielo invernal, suelo blanco y copos cayendo."""
    x, y = _grid(w, h)
    img = _vgrad(h, w, (120, 140, 170), (215, 225, 240), y)
    ground = y > 0.85 + 0.02 * np.sin(x * 9)
    img = np.where(ground[..., None], _rgb((245, 248, 252)), img)
    p = _points(5, 260)
    speed = 0.05 + 0.08 * p[:, 3]
    ys = ((p[:, 1] + t * speed) % 1) * h
    xs = ((p[:, 0] + 0.02 * np.sin(2 * np.pi * (p[:, 2] + t * 0.3))) % 1) * w
    _splat(img, xs, ys, (255, 255, 255), np.full(len(p), 0.9, np.float32), r=1)
    return _to_u8(img)


def neon(t: float, w: int, h: int) -> np.ndarray:
    """Fiesta/neón: fondo oscuro con bandas de colores que laten al ritmo."""
    x, y = _grid(w, h)
    beat = 0.6 + 0.4 * np.abs(np.sin(np.pi * t * 2))  # 120 bpm
    a = np.sin(10 * x + 3 * t) + np.sin(8 * y - 2 * t) + np.sin(6 * (x + y) + t)
    r = 128 + 127 * np.sin(a * 1.5)
    g = 128 + 127 * np.sin(a * 1.5 + 2.1)
    b = 128 + 127 * np.sin(a * 1.5 + 4.2)
    lines = (np.abs(np.sin(a * 3)) > 0.97)[..., None] * 120
    return _to_u8(np.stack([r, g, b], -1) * 0.35 * beat + lines)


def underwater(t: float, w: int, h: int) -> np.ndarray:
    """Fondo marino: azul profundo con cáusticas de luz y burbujas."""
    x, y = _grid(w, h)
    img = _vgrad(h, w, (20, 120, 170), (5, 30, 70), y)
    c = np.sin(x * 25 + t * 1.3 + np.sin(y * 18 + t)) * np.sin(y * 22 - t * 1.1 + np.sin(x * 15))
    img = img + (np.clip(c, 0, 1) ** 3 * 70 * (1 - y))[..., None]
    p = _points(9, 60)
    ys = ((p[:, 1] - t * (0.05 + 0.1 * p[:, 3])) % 1) * h
    xs = (p[:, 0] + 0.01 * np.sin(t * 2 + p[:, 2] * 6)) * w
    _splat(img, xs, ys, (220, 240, 255), np.full(len(p), 0.6, np.float32), r=2)
    return _to_u8(img)


def sunset(t: float, w: int, h: int) -> np.ndarray:
    """Atardecer en el desierto: cielo naranja, sol bajo y dunas."""
    x, y = _grid(w, h)
    img = _vgrad(h, w, (60, 40, 110), (250, 140, 70), y / 0.65)
    d = np.sqrt((x - 0.5) ** 2 + ((y - 0.6 - 0.01 * np.sin(t / 3)) * h / w) ** 2)
    sun = np.clip(1 - d / 0.12, 0, 1)[..., None]
    img = img * (1 - sun) + _rgb((255, 220, 120)) * sun
    dune = y > 0.66 + 0.05 * np.sin(x * 5 + 1) + 0.03 * np.sin(x * 11)
    img = np.where(dune[..., None], _vgrad(h, w, (200, 110, 60), (120, 60, 40), (y - 0.6) / 0.4), img)
    return _to_u8(img)


BACKGROUNDS: dict[str, Background] = {
    "estudio": studio,
    "degradado": gradient,
    "playa": beach,
    "espacio": space,
    "ciudad": city,
    "bosque": forest,
    "fuego": fire,
    "nieve": snow,
    "neon": neon,
    "fondo_marino": underwater,
    "atardecer": sunset,
}

#: Palabras (normalizadas, sin tildes) que evocan cada entorno.
BACKGROUND_WORDS: dict[str, tuple[str, ...]] = {
    "playa": ("playa", "verano", "costa", "arena", "vacaciones", "caribe", "tropical", "isla"),
    "espacio": ("espaci", "estrella", "galaxia", "universo", "cosmos", "planeta", "luna", "astronauta", "cohete"),
    "ciudad": ("ciudad", "urbano", "calle", "rascacielos", "nueva york", "metropoli", "edificio"),
    "bosque": ("bosque", "selva", "naturaleza", "arbol", "montana", "jungla", "campo"),
    "fuego": ("fuego", "llama", "infierno", "volcan", "lava", "incendio", "dragon"),
    "nieve": ("nieve", "invierno", "navidad", "frio", "hielo", "polo", "esqui"),
    "neon": ("fiesta", "neon", "discoteca", "musica", "baile", "concierto", "rave", "club"),
    "fondo_marino": ("fondo marino", "submarino", "oceano", "bajo el agua", "acuario", "peces", "bucear"),
    "atardecer": ("atardecer", "desierto", "puesta de sol", "anochecer", "duna", "sahara"),
    "degradado": ("degradado", "colores", "abstracto"),
    "estudio": ("estudio", "neutro", "oficina", "presentacion"),
}


def image_background(path: str | Path) -> Background:
    """Entorno a partir de una imagen o vídeo propio (se reescala al tamaño pedido)."""
    import cv2

    path = Path(path)
    cap = cv2.VideoCapture(str(path))
    frames: list[np.ndarray] = []
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    while len(frames) < 600:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
    cap.release()
    if not frames:
        raise FileNotFoundError(f"No se pudo leer el fondo {path}")
    cache: dict[tuple[int, int, int], np.ndarray] = {}

    def bg(t: float, w: int, h: int) -> np.ndarray:
        i = int(t * fps) % len(frames)
        key = (i, w, h)
        if key not in cache:
            if len(cache) > 64:
                cache.clear()
            cache[key] = cv2.resize(frames[i], (w, h), interpolation=cv2.INTER_AREA)
        return cache[key]

    return bg


def get_background(name: str | None) -> Background | None:
    """Resuelve un nombre de entorno o una ruta a imagen/vídeo. ``None``/«ninguno» ⇒ sin cambio."""
    if name is None or name in ("", "ninguno", "original"):
        return None
    if name in BACKGROUNDS:
        return BACKGROUNDS[name]
    if Path(name).exists():
        return image_background(name)
    raise KeyError(f"Entorno desconocido: {name!r}. Disponibles: {', '.join(BACKGROUNDS)}")
