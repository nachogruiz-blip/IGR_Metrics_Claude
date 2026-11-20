"""Detección de la persona (máscara) y de la cara en cada fotograma.

Motor principal: MediaPipe Tasks (segmentador «selfie» y detector BlazeFace). Los modelos
(~0,5 MB en total) se descargan la primera vez a ``~/.cache/estudio_video``.
Si MediaPipe no está disponible se usan alternativas sólo con OpenCV:

* persona: diferencia con un fondo de referencia (hay que salir del encuadre al empezar o
  usar la mediana de un vídeo con cámara fija);
* cara: clasificador Haar incluido en OpenCV.
"""

from __future__ import annotations

import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

MODELS = {
    "selfie_segmenter.tflite": "https://storage.googleapis.com/mediapipe-models/image_segmenter/"
    "selfie_segmenter/float16/latest/selfie_segmenter.tflite",
    "blaze_face_short_range.tflite": "https://storage.googleapis.com/mediapipe-models/face_detector/"
    "blaze_face_short_range/float16/latest/blaze_face_short_range.tflite",
}


def model_path(name: str) -> Path:
    cache = Path(os.environ.get("ESTUDIO_VIDEO_CACHE", Path.home() / ".cache" / "estudio_video"))
    p = cache / name
    if not p.exists():
        cache.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(MODELS[name], p)
    return p


@dataclass
class Box:
    """Caja de la cara en píxeles."""

    x: int
    y: int
    w: int
    h: int

    def expanded(self, k: float, W: int, H: int) -> "Box":
        """Agranda la caja (k=1,4 ⇒ 40 % más) hacia arriba para cubrir frente y pelo."""
        cx, cy = self.x + self.w / 2, self.y + self.h / 2 - self.h * 0.12
        w, h = self.w * k, self.h * k * 1.15
        x0, y0 = int(max(0, cx - w / 2)), int(max(0, cy - h / 2))
        x1, y1 = int(min(W, cx + w / 2)), int(min(H, cy + h / 2))
        return Box(x0, y0, max(1, x1 - x0), max(1, y1 - y0))


class Segmenter:
    """Interfaz común: ``person_mask(rgb, t_ms) -> float32 (h,w) ∈ [0,1]`` y ``faces(rgb, t_ms)``."""

    name = "base"

    def person_mask(self, rgb: np.ndarray, t_ms: int) -> np.ndarray:  # pragma: no cover
        raise NotImplementedError

    def faces(self, rgb: np.ndarray, t_ms: int) -> list[Box]:  # pragma: no cover
        raise NotImplementedError

    def close(self) -> None:
        pass


class MediaPipeSegmenter(Segmenter):
    name = "mediapipe"

    def __init__(self) -> None:
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        self._mp = mp
        self._seg = vision.ImageSegmenter.create_from_options(
            vision.ImageSegmenterOptions(
                base_options=BaseOptions(model_asset_path=str(model_path("selfie_segmenter.tflite"))),
                running_mode=vision.RunningMode.VIDEO,
                output_confidence_masks=True,
            )
        )
        self._face = vision.FaceDetector.create_from_options(
            vision.FaceDetectorOptions(
                base_options=BaseOptions(model_asset_path=str(model_path("blaze_face_short_range.tflite"))),
                running_mode=vision.RunningMode.VIDEO,
                min_detection_confidence=0.5,
            )
        )
        self._last_t = -1
        self._img = None

    def _image(self, rgb: np.ndarray, t_ms: int):
        if t_ms <= self._last_t:  # MediaPipe exige tiempos estrictamente crecientes
            t_ms = self._last_t + 1
        self._last_t = t_ms
        return self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)), t_ms

    def person_mask(self, rgb: np.ndarray, t_ms: int) -> np.ndarray:
        img, t = self._image(rgb, t_ms)
        r = self._seg.segment_for_video(img, t)
        m = r.confidence_masks[0].numpy_view()
        return np.asarray(m, dtype=np.float32).reshape(rgb.shape[:2])

    def faces(self, rgb: np.ndarray, t_ms: int) -> list[Box]:
        img, t = self._image(rgb, t_ms)
        r = self._face.detect_for_video(img, t)
        return [Box(d.bounding_box.origin_x, d.bounding_box.origin_y, d.bounding_box.width, d.bounding_box.height)
                for d in r.detections]

    def close(self) -> None:
        self._seg.close()
        self._face.close()


class OpenCVSegmenter(Segmenter):
    """Alternativa sin IA: fondo de referencia + Haar.

    ``reference`` es una imagen del escenario vacío. Si no se da, el primer fotograma recibido
    se toma como fondo (sal del encuadre al empezar) — o usa :func:`median_background`.
    """

    name = "opencv"

    def __init__(self, reference: np.ndarray | None = None, threshold: float = 28.0) -> None:
        self.reference = None if reference is None else reference.astype(np.float32)
        self.threshold = threshold
        self._haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    def person_mask(self, rgb: np.ndarray, t_ms: int) -> np.ndarray:
        if self.reference is None or self.reference.shape != rgb.shape:
            self.reference = rgb.astype(np.float32)
        diff = np.abs(rgb.astype(np.float32) - self.reference).max(axis=2)
        m = (diff > self.threshold).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
        return cv2.GaussianBlur(m.astype(np.float32), (9, 9), 0)

    def faces(self, rgb: np.ndarray, t_ms: int) -> list[Box]:
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        found = self._haar.detectMultiScale(gray, 1.15, 5, minSize=(40, 40))
        return [Box(int(x), int(y), int(w), int(h)) for x, y, w, h in found]


def median_background(frames: list[np.ndarray]) -> np.ndarray:
    """Fondo estimado como mediana temporal (cámara fija y persona en movimiento)."""
    return np.median(np.stack(frames[:: max(1, len(frames) // 30)]), axis=0).astype(np.uint8)


def make_segmenter(prefer: str = "auto", reference: np.ndarray | None = None) -> Segmenter:
    """``prefer``: «auto» (MediaPipe si se puede), «mediapipe» u «opencv»."""
    if prefer in ("auto", "mediapipe"):
        try:
            return MediaPipeSegmenter()
        except Exception as e:  # sin mediapipe, sin libEGL o sin red para el modelo
            if prefer == "mediapipe":
                raise
            print(f"[aviso] MediaPipe no disponible ({type(e).__name__}: {e}); uso OpenCV.")
    return OpenCVSegmenter(reference)
