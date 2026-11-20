"""Transformación de la persona en vídeo: entorno, cuerpo y cara.

* :func:`compose` — un fotograma + máscara + caras + :class:`Look` → fotograma transformado.
* :func:`process_video` — aplica un look a un archivo de vídeo (con su audio original).
* :func:`live` — cámara web en directo; escribe órdenes en la terminal para cambiar el look.
"""

from __future__ import annotations

import queue
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from .backgrounds import get_background
from .effects import get_effect
from .looks import Look, parse_look, vocabulary
from .segment import Box, OpenCVSegmenter, Segmenter, make_segmenter, median_background

GHOST_ALPHA = 0.45


class Resolved:
    """Look con las funciones ya resueltas (evita recargar imágenes en cada fotograma)."""

    def __init__(self, look: Look) -> None:
        self.look = look
        self.background = get_background(look.background)
        self.body = get_effect(look.body)
        self.face = get_effect(look.face)


def _ellipse_mask(w: int, h: int) -> np.ndarray:
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    d = ((x - w / 2) / (w / 2)) ** 2 + ((y - h / 2) / (h / 2)) ** 2
    return np.clip((1 - d) / 0.25, 0, 1)  # borde suave


def compose(frame: np.ndarray, mask: np.ndarray, faces: list[Box], look: Look | Resolved, t: float) -> np.ndarray:
    """Aplica el look a un fotograma RGB.

    ``mask`` ∈ [0,1] (1 = persona). Orden: efecto de cuerpo → entorno → efecto de cara.
    Con un look vacío devuelve el fotograma sin cambios.
    """
    r = look if isinstance(look, Resolved) else Resolved(look)
    h, w = frame.shape[:2]
    out = frame.astype(np.float32)
    m = np.clip(mask, 0, 1).astype(np.float32)[..., None]

    if r.body is not None:
        eff = r.body(frame, t).astype(np.float32)
        out = out * (1 - m) + eff * m

    alpha = m * (GHOST_ALPHA if r.look.body == "fantasma" else 1.0)
    if r.background is not None:
        bg = r.background(t, w, h).astype(np.float32)
        out = bg * (1 - alpha) + out * alpha
    elif r.look.blur_background:
        k = max(3, (min(h, w) // 25) | 1)
        bg = cv2.GaussianBlur(frame, (k, k), 0).astype(np.float32)
        out = bg * (1 - alpha) + out * alpha

    if r.face is not None:
        for b in faces:
            e = b.expanded(1.45, w, h)
            region = frame[e.y : e.y + e.h, e.x : e.x + e.w]
            if region.size == 0:
                continue
            new = r.face(np.ascontiguousarray(region), t).astype(np.float32)
            em = _ellipse_mask(e.w, e.h)[..., None]
            sl = out[e.y : e.y + e.h, e.x : e.x + e.w]
            out[e.y : e.y + e.h, e.x : e.x + e.w] = sl * (1 - em) + new * em
    return np.clip(out, 0, 255).astype(np.uint8)


class Transformer:
    """Encadena segmentador + look; suaviza la máscara en el tiempo para evitar parpadeo."""

    def __init__(self, look: Look, segmenter: Segmenter, smooth: float = 0.5) -> None:
        self.segmenter = segmenter
        self.smooth = smooth
        self._prev: np.ndarray | None = None
        self._faces: list[Box] = []
        self._miss = 0
        self.set_look(look)

    def set_look(self, look: Look) -> None:
        self.resolved = Resolved(look)

    @property
    def look(self) -> Look:
        return self.resolved.look

    def __call__(self, frame: np.ndarray, t: float) -> np.ndarray:
        lk = self.look
        if lk == Look():
            return frame
        t_ms = int(t * 1000)
        need_mask = lk.background or lk.body or lk.blur_background
        if need_mask:
            m = self.segmenter.person_mask(frame, t_ms)
            if self._prev is not None and self._prev.shape == m.shape:
                m = self.smooth * self._prev + (1 - self.smooth) * m
            self._prev = m
        else:
            m = np.zeros(frame.shape[:2], np.float32)
        if lk.face:
            found = self.segmenter.faces(frame, t_ms)
            if found:
                self._faces, self._miss = found, 0
            else:  # conserva la última cara unos fotogramas (detecciones intermitentes)
                self._miss += 1
                if self._miss > 8:
                    self._faces = []
        return compose(frame, m, self._faces if lk.face else [], self.resolved, t)


def _read_frames(path: str | Path):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise FileNotFoundError(f"No se pudo abrir {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def gen():
        try:
            while True:
                ok, f = cap.read()
                if not ok:
                    break
                yield cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
        finally:
            cap.release()

    return gen(), fps, w, h


def process_video(src: str | Path, out: str | Path, look: Look, engine: str = "auto",
                  max_width: int | None = 1280) -> Path:
    """Aplica ``look`` a todo el vídeo ``src`` y guarda ``out`` (conserva el audio original).

    Con ``engine="opencv"`` el fondo de referencia es la mediana del vídeo (cámara fija).
    """
    from .edit import has_audio
    from .render import ffmpeg_exe, write_video

    frames, fps, w, h = _read_frames(src)
    scale = min(1.0, max_width / w) if max_width else 1.0
    W, H = (int(w * scale) // 2 * 2, int(h * scale) // 2 * 2)

    def resize(f):
        return f if (f.shape[1], f.shape[0]) == (W, H) else cv2.resize(f, (W, H), interpolation=cv2.INTER_AREA)

    seg: Segmenter
    if engine == "opencv":
        all_frames = [resize(f) for f in frames]
        seg = OpenCVSegmenter(median_background(all_frames))
        frames = iter(all_frames)
    else:
        seg = make_segmenter(engine)
    tr = Transformer(look, seg, smooth=0.3)
    out = Path(out)
    tmp = out.with_suffix(".sin_audio.mp4")
    try:
        write_video((tr(resize(f), i / fps) for i, f in enumerate(frames)), tmp, W, H, int(round(fps)))
    finally:
        seg.close()
    if has_audio(src):
        import subprocess

        subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(tmp), "-i", str(src), "-map", "0:v",
                        "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest", str(out)], check=True)
        tmp.unlink()
    else:
        tmp.replace(out)
    return out


PRESETS = {
    ord("1"): Look(background="playa"),
    ord("2"): Look(background="espacio", face="alien"),
    ord("3"): Look(background="ciudad", body="dibujo"),
    ord("4"): Look(background="neon", body="neon"),
    ord("5"): Look(background="bosque", body="boceto"),
    ord("6"): Look(background="fuego", body="robot", face="robot"),
    ord("7"): Look(background="nieve", face="emoji"),
    ord("8"): Look(blur_background=True),
    ord("9"): Look(background="fondo_marino", body="fantasma"),
    ord("0"): Look(),
}

HELP = """\
Cámara del estudio de vídeo
  Escribe órdenes en ESTA terminal y pulsa Enter, por ejemplo:
    ponme en la playa
    cara de robot y cuerpo de dibujo animado
    llévame al espacio con cara de alien
    desenfoca el fondo / quita la cara / quita todo
  Teclas en la ventana: 1-9 looks rápidos · 0 original · r grabar/parar · f foto · q salir
"""


def _stdin_reader(q: "queue.Queue[str]") -> None:
    for line in sys.stdin:
        q.put(line.strip())


def live(camera: int = 0, look: Look | None = None, engine: str = "auto", use_ai: bool = False,
         outdir: str | Path = "salidas", width: int = 960) -> None:  # pragma: no cover - necesita cámara
    """Bucle en directo con la cámara web. Las grabaciones/fotos se guardan en ``outdir``."""
    from .render import write_video

    cap = cv2.VideoCapture(camera)
    if not cap.isOpened():
        raise RuntimeError(f"No se pudo abrir la cámara {camera}. ¿Está conectada y con permiso?")
    seg = make_segmenter(engine)
    if isinstance(seg, OpenCVSegmenter):
        print("Modo OpenCV: sal del encuadre 2 segundos para capturar el fondo vacío…")
        time.sleep(2)
        ok, f = cap.read()
        seg.reference = cv2.cvtColor(cv2.flip(f, 1), cv2.COLOR_BGR2RGB).astype(np.float32) if ok else None
    tr = Transformer(look or Look(), seg)
    print(HELP)
    print(vocabulary())
    print(f"Look actual: {tr.look.describe()}")
    q: "queue.Queue[str]" = queue.Queue()
    threading.Thread(target=_stdin_reader, args=(q,), daemon=True).start()

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    recording: list[np.ndarray] | None = None
    t0 = time.time()
    fps_est = 20.0
    last = time.time()
    win = "Estudio de video (q para salir)"
    try:
        while True:
            ok, f = cap.read()
            if not ok:
                break
            f = cv2.flip(f, 1)
            if f.shape[1] > width:
                f = cv2.resize(f, (width, int(f.shape[0] * width / f.shape[1])))
            rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
            outf = tr(rgb, time.time() - t0)
            while not q.empty():
                cmd = q.get()
                if cmd:
                    try:
                        tr.set_look(parse_look(cmd, tr.look, use_ai=use_ai))
                        print(f"→ {tr.look.describe()}")
                    except (KeyError, FileNotFoundError) as e:
                        print(f"No entendí: {e}")
            if recording is not None:
                recording.append(outf)
            show = cv2.cvtColor(outf, cv2.COLOR_RGB2BGR)
            label = tr.look.describe() + ("   ● REC" if recording is not None else "")
            cv2.putText(show, label, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3)
            cv2.putText(show, label, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            cv2.imshow(win, show)
            now = time.time()
            fps_est = 0.9 * fps_est + 0.1 / max(now - last, 1e-3)
            last = now
            k = cv2.waitKey(1) & 0xFF
            if k in (ord("q"), 27):
                break
            if k in PRESETS:
                tr.set_look(PRESETS[k])
                print(f"→ {tr.look.describe()}")
            elif k == ord("f"):
                p = outdir / f"foto_{time.strftime('%Y%m%d_%H%M%S')}.png"
                cv2.imwrite(str(p), show)
                print(f"Foto guardada: {p}")
            elif k == ord("r"):
                if recording is None:
                    recording = []
                    print("Grabando… (r para parar)")
                else:
                    p = outdir / f"video_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
                    hh, ww = (s // 2 * 2 for s in recording[0].shape[:2])  # H.264 exige tamaño par
                    write_video((r[:hh, :ww] for r in recording), p, ww, hh, max(1, int(round(fps_est))))
                    print(f"Vídeo guardado: {p}")
                    recording = None
    finally:
        cap.release()
        seg.close()
        cv2.destroyAllWindows()
