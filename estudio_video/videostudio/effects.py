"""Efectos de imagen para el cuerpo y la cara.

Cada efecto es ``f(img, t) -> img`` sobre RGB uint8 (h, w, 3) y devuelve el mismo tamaño.
Se aplican sólo dentro de la máscara de la persona (cuerpo) o del óvalo de la cara.
"""

from __future__ import annotations

from typing import Callable

import cv2
import numpy as np

Effect = Callable[[np.ndarray, float], np.ndarray]


def _u8(a: np.ndarray) -> np.ndarray:
    return np.clip(a, 0, 255).astype(np.uint8)


def cartoon(img: np.ndarray, t: float = 0.0) -> np.ndarray:
    """Dibujo animado: colores planos (cuantización) + contornos negros."""
    small = cv2.bilateralFilter(img, 7, 60, 60)
    q = (small // 40) * 40 + 20
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    edges = cv2.adaptiveThreshold(
        cv2.medianBlur(gray, 5), 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 9, 4
    )
    return np.where(edges[..., None] > 0, q, 0).astype(np.uint8)


def sketch(img: np.ndarray, t: float = 0.0) -> np.ndarray:
    """Boceto a lápiz (división por la imagen desenfocada invertida)."""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(np.float32)
    blur = cv2.GaussianBlur(255 - gray, (21, 21), 0)
    s = np.clip(gray * 255 / np.maximum(255 - blur, 1), 0, 255)
    return np.repeat(_u8(s)[..., None], 3, axis=2)


def neon_edges(img: np.ndarray, t: float = 0.0) -> np.ndarray:
    """Silueta de neón: bordes brillantes cuyo color cambia con el tiempo."""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    e = cv2.Canny(gray, 60, 140)
    e = cv2.GaussianBlur(cv2.dilate(e, np.ones((3, 3), np.uint8)), (7, 7), 0).astype(np.float32) / 255
    h = 2 * np.pi * t / 4
    col = np.array([0.5 + 0.5 * np.sin(h), 0.5 + 0.5 * np.sin(h + 2.1), 0.5 + 0.5 * np.sin(h + 4.2)])
    return _u8(img * 0.15 + e[..., None] * col * 255 * 1.4)


def thermal(img: np.ndarray, t: float = 0.0) -> np.ndarray:
    """Cámara térmica (mapa de color INFERNO sobre la luminancia)."""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    return cv2.cvtColor(cv2.applyColorMap(gray, cv2.COLORMAP_INFERNO), cv2.COLOR_BGR2RGB)


def pixelate(img: np.ndarray, t: float = 0.0, block: int = 14) -> np.ndarray:
    """Pixel art / anonimizar: bloques de ``block`` píxeles."""
    h, w = img.shape[:2]
    small = cv2.resize(img, (max(1, w // block), max(1, h // block)), interpolation=cv2.INTER_AREA)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)


def blur(img: np.ndarray, t: float = 0.0) -> np.ndarray:
    """Difuminado fuerte (privacidad)."""
    k = max(3, (min(img.shape[:2]) // 6) | 1)
    return cv2.GaussianBlur(img, (k, k), 0)


def _tint(img: np.ndarray, color, strength: float, gamma: float = 1.0) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
    gray = gray**gamma
    tinted = gray[..., None] * np.asarray(color, np.float32)
    return _u8(img * (1 - strength) + tinted * strength)


def gold(img: np.ndarray, t: float = 0.0) -> np.ndarray:
    """Estatua dorada, con un brillo que recorre la figura."""
    out = _tint(img, (255, 200, 90), 0.9, 0.8).astype(np.float32)
    h, w = img.shape[:2]
    x = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    shine = np.exp(-(((x - (t * 0.3) % 1.4 + 0.2) / 0.06) ** 2)) * 80
    return _u8(out + shine[..., None])


def metal(img: np.ndarray, t: float = 0.0) -> np.ndarray:
    """Robot/metal: gris azulado con alto contraste y bordes marcados."""
    out = _tint(img, (190, 205, 225), 1.0, 1.4)
    e = cv2.Canny(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY), 80, 160)
    out[e > 0] = (40, 230, 255)
    return out


def zombie(img: np.ndarray, t: float = 0.0) -> np.ndarray:
    """Zombi: piel verdosa desaturada y sombras oscuras."""
    return _tint(img, (150, 200, 120), 0.75, 1.3)


def alien(img: np.ndarray, t: float = 0.0) -> np.ndarray:
    """Alien: verde intenso con rotación de tono."""
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    hsv[..., 0] = (hsv[..., 0].astype(int) + 60) % 180
    hsv[..., 1] = np.maximum(hsv[..., 1], 150)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)


def ghost(img: np.ndarray, t: float = 0.0) -> np.ndarray:
    """Fantasma: azulado y pálido (además el compositor lo hace semitransparente)."""
    return _tint(img, (200, 230, 255), 0.85, 0.7)


def glitch(img: np.ndarray, t: float = 0.0) -> np.ndarray:
    """Glitch: canales RGB desplazados y bandas horizontales que saltan."""
    out = img.copy()
    s = int(6 + 4 * np.sin(t * 7))
    out[..., 0] = np.roll(img[..., 0], s, axis=1)
    out[..., 2] = np.roll(img[..., 2], -s, axis=1)
    h = img.shape[0]
    rng = np.random.default_rng(int(t * 10))
    for y0 in rng.integers(0, max(1, h - 8), 4):
        out[y0 : y0 + 8] = np.roll(out[y0 : y0 + 8], int(rng.integers(-30, 30)), axis=1)
    return out


def comic(img: np.ndarray, t: float = 0.0) -> np.ndarray:
    """Cómic pop-art: pocos colores saturados con trama de puntos."""
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    hsv[..., 1] = np.clip(hsv[..., 1].astype(int) * 2, 0, 255).astype(np.uint8)
    q = (cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB) // 85) * 85 + 40
    h, w = img.shape[:2]
    y, x = np.mgrid[0:h, 0:w]
    dots = ((x % 6 - 3) ** 2 + (y % 6 - 3) ** 2) < 5
    return np.where(dots[..., None], q, _u8(q * 0.8)).astype(np.uint8)


EFFECTS: dict[str, Effect] = {
    "dibujo": cartoon,
    "boceto": sketch,
    "neon": neon_edges,
    "termico": thermal,
    "pixel": pixelate,
    "difuminar": blur,
    "oro": gold,
    "robot": metal,
    "zombi": zombie,
    "alien": alien,
    "fantasma": ghost,
    "glitch": glitch,
    "comic": comic,
}

#: Palabras (normalizadas) que piden cada efecto.
EFFECT_WORDS: dict[str, tuple[str, ...]] = {
    "dibujo": ("dibujo", "caricatura", "cartoon", "animado", "anime", "pixar"),
    "boceto": ("boceto", "lapiz", "sketch", "carboncillo"),
    "neon": ("neon", "luminos", "brillante", "tron"),
    "termico": ("termic", "calor", "infrarroj", "predator"),
    "pixel": ("pixel", "8 bits", "retro", "minecraft"),
    "difuminar": ("difumin", "borros", "anonim", "ocult", "privad", "desenfoc"),
    "oro": ("oro", "dorad", "estatua"),
    "robot": ("robot", "metal", "cyborg", "androide", "cibor"),
    "zombi": ("zombi", "muerto", "no muerto"),
    "alien": ("alien", "extraterrestre", "marciano", "verde"),
    "fantasma": ("fantasma", "transparente", "invisible", "espectro"),
    "glitch": ("glitch", "matrix", "hacker", "distorsion"),
    "comic": ("comic", "pop art", "tebeo", "superheroe"),
}


def face_mask_image(path: str) -> Effect:
    """Careta a partir de una imagen propia (avatar, dibujo, emoji…): se ajusta al óvalo de la cara.

    Si la imagen tiene canal alfa (PNG transparente) se respeta.
    """
    raw = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if raw is None:
        raise FileNotFoundError(f"No se pudo leer la imagen de careta {path}")
    if raw.ndim == 2:
        raw = cv2.cvtColor(raw, cv2.COLOR_GRAY2BGRA)
    if raw.shape[2] == 3:
        raw = cv2.cvtColor(raw, cv2.COLOR_BGR2BGRA)
    rgba = cv2.cvtColor(raw, cv2.COLOR_BGRA2RGBA)

    def eff(img: np.ndarray, t: float = 0.0) -> np.ndarray:
        h, w = img.shape[:2]
        m = cv2.resize(rgba, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32)
        a = m[..., 3:] / 255
        return _u8(img * (1 - a) + m[..., :3] * a)

    return eff


def emoji_face(img: np.ndarray, t: float = 0.0) -> np.ndarray:
    """Careta de emoji sonriente dibujada (guiña un ojo cada 3 s)."""
    h, w = img.shape[:2]
    out = np.zeros_like(img)
    out[:] = (255, 205, 40)
    cx, cy = w // 2, h // 2
    ex, ey, er = int(w * 0.18), int(h * 0.12), max(2, int(min(w, h) * 0.07))
    wink = (t % 3) < 0.25
    cv2.circle(out, (cx - ex, cy - ey), er, (60, 40, 20), -1)
    if wink:
        cv2.line(out, (cx + ex - er, cy - ey), (cx + ex + er, cy - ey), (60, 40, 20), max(2, er // 2))
    else:
        cv2.circle(out, (cx + ex, cy - ey), er, (60, 40, 20), -1)
    cv2.ellipse(out, (cx, cy + int(h * 0.08)), (int(w * 0.25), int(h * 0.18)), 0, 10, 170, (60, 40, 20), max(2, er // 2))
    return out


EFFECTS["emoji"] = emoji_face
EFFECT_WORDS["emoji"] = ("emoji", "careta", "sonrisa", "smiley", "emoticono")


def get_effect(name: str | None) -> Effect | None:
    """Resuelve un efecto por nombre o una ruta de imagen (careta). ``None``/«ninguno» ⇒ sin efecto."""
    if name is None or name in ("", "ninguno", "original"):
        return None
    if name in EFFECTS:
        return EFFECTS[name]
    from pathlib import Path

    if Path(name).exists():
        return face_mask_image(name)
    raise KeyError(f"Efecto desconocido: {name!r}. Disponibles: {', '.join(EFFECTS)}")
