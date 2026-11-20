"""Renderizado de un :class:`Storyboard` a MP4 (H.264) con ffmpeg.

Cada fotograma = entorno animado (``backgrounds``) + rótulo de la escena con entrada animada.
Las transiciones entre escenas se calculan mezclando el último instante de la anterior.
"""

from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Iterator

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .backgrounds import BACKGROUNDS
from .plan import Storyboard, validate

TRANSITION_TIME = 0.6  # s


def ffmpeg_exe() -> str:
    """Ruta a ffmpeg: el del sistema o el que trae ``imageio-ffmpeg``."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf", "LiberationSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def text_layer(text: str, w: int, h: int) -> np.ndarray:
    """Capa RGBA (h, w, 4) float32 ∈ [0,1] con el texto centrado, sombra y caja translúcida."""
    size = max(18, int(min(w, h) * 0.07))
    font = _font(size)
    chars = max(8, int(w / (size * 0.55)))
    lines = textwrap.wrap(text, width=chars) or [""]
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    boxes = [d.textbbox((0, 0), ln, font=font) for ln in lines]
    lh = int(size * 1.25)
    total_h = lh * len(lines)
    maxw = max(b[2] - b[0] for b in boxes)
    y0 = (h - total_h) // 2
    pad = size // 2
    d.rounded_rectangle(
        ((w - maxw) // 2 - pad, y0 - pad, (w + maxw) // 2 + pad, y0 + total_h + pad // 2),
        radius=pad,
        fill=(0, 0, 0, 110),
    )
    for i, (ln, b) in enumerate(zip(lines, boxes)):
        x = (w - (b[2] - b[0])) // 2
        y = y0 + i * lh
        d.text((x + 3, y + 3), ln, font=font, fill=(0, 0, 0, 160))
        d.text((x, y), ln, font=font, fill=(255, 255, 255, 255))
    return np.asarray(img, dtype=np.float32) / 255


def _scene_frame(bg_img: np.ndarray, layer: np.ndarray, local_t: float, dur: float) -> np.ndarray:
    """Compone el rótulo sobre el fondo con aparición (0,5 s) y salida (0,4 s) suaves."""
    a_in = np.clip(local_t / 0.5, 0, 1)
    a_out = np.clip((dur - local_t) / 0.4, 0, 1)
    a = float(min(a_in, a_out))
    a = a * a * (3 - 2 * a)  # smoothstep
    shift = int((1 - a) * bg_img.shape[0] * 0.04)
    lay = np.roll(layer, shift, axis=0) if shift else layer
    alpha = lay[..., 3:] * a
    return (bg_img * (1 - alpha) + lay[..., :3] * 255 * alpha).astype(np.uint8)


def frames(sb: Storyboard) -> Iterator[np.ndarray]:
    """Genera los fotogramas RGB del guion en orden."""
    sb = validate(sb)
    w, h, fps = sb.width, sb.height, sb.fps
    layers = [text_layer(s.text, w, h) for s in sb.scenes]
    t0 = 0.0
    prev_last: np.ndarray | None = None
    for k, (scene, layer) in enumerate(zip(sb.scenes, layers)):
        bg = BACKGROUNDS[scene.background]
        n = max(1, int(round(scene.duration * fps)))
        ntrans = int(TRANSITION_TIME * fps) if (k and scene.transition != "corte") else 0
        for i in range(n):
            lt = i / fps
            f = _scene_frame(bg(t0 + lt, w, h), layer, lt, scene.duration)
            if prev_last is not None and i < ntrans:
                a = (i + 1) / (ntrans + 1)
                if scene.transition == "deslizar":
                    cut = int(w * a)
                    f = np.concatenate([f[:, w - cut :], prev_last[:, : w - cut]], axis=1) if cut < w else f
                else:
                    f = (prev_last * (1 - a) + f * a).astype(np.uint8)
            yield f
        prev_last = f
        t0 += scene.duration


AI_NOTICE = "Contenido generado o modificado con IA (estudio_video)"


def write_video(frame_iter, out: str | Path, w: int, h: int, fps: int, audio: str | Path | None = None,
                notice: str | None = AI_NOTICE) -> Path:
    """Escribe fotogramas RGB a MP4 mediante una tubería a ffmpeg (opcionalmente con audio).

    ``notice`` se guarda en los metadatos del archivo (campo *comment*) para que quede
    constancia de que el contenido es sintético o manipulado (transparencia, Reglamento UE de IA,
    art. 50). ``None`` lo omite.
    """
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{w}x{h}", "-r", str(fps), "-i", "-"]
    if audio:
        cmd += ["-i", str(audio), "-shortest", "-c:a", "aac"]
    if notice:
        cmd += ["-metadata", f"comment={notice}"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "22",
            "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for f in frame_iter:
            proc.stdin.write(np.ascontiguousarray(f, dtype=np.uint8).tobytes())
    finally:
        proc.stdin.close()
        err = proc.stderr.read().decode() if proc.stderr else ""
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg falló: {err}")
    return out


def render(sb: Storyboard, out: str | Path, audio: str | Path | None = None) -> Path:
    """Renderiza el guion completo a ``out`` (MP4)."""
    return write_video(frames(sb), out, sb.width, sb.height, sb.fps, audio)


def thumbnail(sb: Storyboard, t: float | None = None) -> np.ndarray:
    """Fotograma de muestra (por defecto, mitad de la primera escena) para previsualizar."""
    sb = validate(sb)
    s = sb.scenes[0]
    t = s.duration / 2 if t is None else t
    bg = BACKGROUNDS[s.background](t, sb.width, sb.height)
    return _scene_frame(bg, text_layer(s.text, sb.width, sb.height), t, s.duration)
