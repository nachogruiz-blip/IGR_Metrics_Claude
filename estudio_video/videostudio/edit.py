"""Edición de vídeos existentes con ffmpeg: recortar, unir, velocidad, música, rótulos, GIF…

Cada operación tiene una función ``*_cmd`` que sólo construye la orden (fácil de probar) y
otra que la ejecuta. Todas devuelven la ruta de salida.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .render import ffmpeg_exe


def _run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg falló ({' '.join(cmd[:3])}…):\n{r.stderr[-2000:]}")


def _base(src) -> list[str]:
    return [ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(src)]


def trim_cmd(src, out, start: float, end: float | None = None) -> list[str]:
    cmd = [ffmpeg_exe(), "-y", "-loglevel", "error", "-ss", f"{start}", "-i", str(src)]
    if end is not None:
        cmd += ["-t", f"{end - start}"]
    return cmd + ["-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", str(out)]


def speed_cmd(src, out, factor: float, audio: bool = True) -> list[str]:
    """``factor`` > 1 acelera, < 1 cámara lenta. El audio se ajusta con ``atempo`` encadenado."""
    if factor <= 0:
        raise ValueError("factor debe ser > 0")
    tempos, f = [], factor
    while f > 2.0:
        tempos.append(2.0)
        f /= 2.0
    while f < 0.5:
        tempos.append(0.5)
        f /= 0.5
    tempos.append(f)
    atempo = ",".join(f"atempo={x:.6g}" for x in tempos)
    if not audio:
        return _base(src) + ["-vf", f"setpts=PTS/{factor}", "-an", "-pix_fmt", "yuv420p", str(out)]
    return _base(src) + [
        "-filter_complex", f"[0:v]setpts=PTS/{factor}[v];[0:a]{atempo}[a]",
        "-map", "[v]", "-map", "[a]", "-pix_fmt", "yuv420p", str(out),
    ]


def music_cmd(src, out, audio, volume: float = 1.0, keep_original: bool = False) -> list[str]:
    cmd = _base(src) + ["-stream_loop", "-1", "-i", str(audio)]
    if keep_original:
        filt = f"[1:a]volume={volume}[m];[0:a][m]amix=inputs=2:duration=first[a]"
        return cmd + ["-filter_complex", filt, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-shortest", str(out)]
    return cmd + ["-filter:a", f"volume={volume}", "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                  "-c:a", "aac", "-shortest", str(out)]


def _escape_drawtext(s: str) -> str:
    return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace("%", "\\%")


def caption_cmd(src, out, text: str, position: str = "abajo", start: float = 0.0, end: float | None = None) -> list[str]:
    y = {"arriba": "h*0.08", "centro": "(h-text_h)/2", "abajo": "h*0.85-text_h"}[position]
    enable = f":enable='between(t,{start},{end})'" if end is not None else (f":enable='gte(t,{start})'" if start else "")
    dt = (f"drawtext=text='{_escape_drawtext(text)}':fontcolor=white:fontsize=h*0.06:"
          f"box=1:boxcolor=black@0.5:boxborderw=12:x=(w-text_w)/2:y={y}{enable}")
    return _base(src) + ["-vf", dt, "-c:a", "copy", "-pix_fmt", "yuv420p", str(out)]


def filter_cmd(src, out, name: str) -> list[str]:
    filters = {
        "blanco_negro": "hue=s=0",
        "sepia": "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131",
        "vintage": "curves=vintage,vignette",
        "brillo": "eq=brightness=0.08:saturation=1.3",
        "frio": "colorbalance=bs=0.25:rs=-0.1",
        "calido": "colorbalance=rs=0.2:bs=-0.15",
        "espejo": "hflip",
        "reves": "reverse",
    }
    if name not in filters:
        raise KeyError(f"Filtro desconocido {name!r}. Disponibles: {', '.join(filters)}")
    extra = ["-af", "areverse"] if name == "reves" else ["-c:a", "copy"]
    if name == "reves" and not has_audio(src):
        extra = ["-an"]
    return _base(src) + ["-vf", filters[name], *extra, "-pix_fmt", "yuv420p", str(out)]


def resize_cmd(src, out, fmt: str) -> list[str]:
    """Reencuadra a vertical (9:16), horizontal (16:9) o cuadrado, rellenando con desenfoque."""
    size = {"vertical": (720, 1280), "horizontal": (1280, 720), "cuadrado": (1080, 1080)}[fmt]
    w, h = size
    filt = (f"[0:v]split[a][b];[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=20[bg];"
            f"[b]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[v]")
    return _base(src) + ["-filter_complex", filt, "-map", "[v]", "-map", "0:a?", "-pix_fmt", "yuv420p", str(out)]


def gif_cmd(src, out, fps: int = 12, width: int = 480) -> list[str]:
    filt = f"fps={fps},scale={width}:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
    return _base(src) + ["-vf", filt, str(out)]


# ------------------------------------------------------------------ ejecución


def trim(src, out, start: float, end: float | None = None) -> Path:
    _run(trim_cmd(src, out, start, end))
    return Path(out)


def has_audio(path) -> bool:
    """¿Tiene pista de audio? (lee la cabecera con ``ffmpeg -i``)."""
    r = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    return "Audio:" in r.stderr


def speed(src, out, factor: float) -> Path:
    _run(speed_cmd(src, out, factor, audio=has_audio(src)))
    return Path(out)


def add_music(src, out, audio, volume: float = 1.0, keep_original: bool = False) -> Path:
    _run(music_cmd(src, out, audio, volume, keep_original))
    return Path(out)


def caption(src, out, text: str, position: str = "abajo", start: float = 0.0, end: float | None = None) -> Path:
    _run(caption_cmd(src, out, text, position, start, end))
    return Path(out)


def apply_filter(src, out, name: str) -> Path:
    _run(filter_cmd(src, out, name))
    return Path(out)


def reframe(src, out, fmt: str) -> Path:
    _run(resize_cmd(src, out, fmt))
    return Path(out)


def to_gif(src, out, fps: int = 12, width: int = 480) -> Path:
    _run(gif_cmd(src, out, fps, width))
    return Path(out)


def concat(sources: list, out) -> Path:
    """Une varios vídeos (se reescalan al tamaño del primero)."""
    import cv2

    cap = cv2.VideoCapture(str(sources[0]))
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    cmd = [ffmpeg_exe(), "-y", "-loglevel", "error"]
    for s in sources:
        cmd += ["-i", str(s)]
    parts = "".join(
        f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=25[v{i}];"
        for i in range(len(sources))
    )
    parts += "".join(f"[v{i}]" for i in range(len(sources))) + f"concat=n={len(sources)}:v=1:a=0[v]"
    _run(cmd + ["-filter_complex", parts, "-map", "[v]", "-pix_fmt", "yuv420p", str(out)])
    return Path(out)


def probe_duration(path) -> float:
    """Duración en segundos (vía OpenCV, sin ffprobe)."""
    import cv2

    cap = cv2.VideoCapture(str(path))
    n = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    cap.release()
    return float(n / fps)


def tmp_path(suffix: str = ".mp4") -> Path:
    return Path(tempfile.mkstemp(suffix=suffix)[1])
