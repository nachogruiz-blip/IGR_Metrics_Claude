"""Del texto al guion: :class:`Storyboard` con escenas (texto, duración, entorno, efecto).

``plan_from_text`` funciona sin red: corta la descripción en frases, detecta duración total,
formato (vertical/horizontal/cuadrado) y el entorno de cada escena por palabras clave.
Con ``use_ai=True`` y credenciales de Claude, el modelo escribe un guion más elaborado.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

from .backgrounds import BACKGROUND_WORDS, BACKGROUNDS
from .text import find_keyword, normalize

FORMATS = {
    "vertical": (720, 1280),
    "horizontal": (1280, 720),
    "cuadrado": (1080, 1080),
}
FORMAT_WORDS = {
    "vertical": ("vertical", "tiktok", "reel", "story", "stories", "shorts", "movil"),
    "cuadrado": ("cuadrado", "instagram post", "1:1"),
    "horizontal": ("horizontal", "youtube", "panoramic", "16:9"),
}
TRANSITIONS = ("fundido", "corte", "deslizar")


@dataclass
class Scene:
    text: str
    duration: float = 3.0
    background: str = "degradado"
    transition: str = "fundido"  # cómo entra esta escena


@dataclass
class Storyboard:
    title: str
    scenes: list[Scene] = field(default_factory=list)
    width: int = 1280
    height: int = 720
    fps: int = 25

    @property
    def duration(self) -> float:
        return sum(s.duration for s in self.scenes)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, s: str) -> "Storyboard":
        d = json.loads(s)
        d["scenes"] = [Scene(**sc) for sc in d.get("scenes", [])]
        return cls(**d)


_STRIP_PREFIX = re.compile(
    r"^(haz(me)?|crea(me)?|genera(me)?|quiero|un|una|v[ií]deos?|de|sobre|que|trate|"
    r"\d+\s*(s|seg|segundos|minutos?)|en|formato|vertical|horizontal|cuadrado|para|tiktok|youtube|instagram|reels?|"
    r"el|la|los|las|del)\b[\s,:]*",
    re.IGNORECASE,
)


def _clean_title(s: str) -> str:
    prev = None
    s = s.strip()
    while prev != s:
        prev = s
        s = _STRIP_PREFIX.sub("", s).strip()
    return s[:1].upper() + s[1:] if s else "Mi vídeo"


def _total_seconds(text: str) -> float | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(s\b|seg|segundos)", text)
    if m:
        return float(m.group(1).replace(",", "."))
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(min|minutos?)\b", text)
    if m:
        return 60 * float(m.group(1).replace(",", "."))
    return None


def plan_from_text(prompt: str, use_ai: bool = False, fps: int = 25) -> Storyboard:
    """Convierte una descripción libre en un guion de escenas.

    Formato admitido (flexible): «vídeo vertical de 12 segundos sobre un viaje: despegamos
    desde la Tierra. Vemos las estrellas. Volvemos a casa al atardecer.» — lo que va tras «:»
    (o cada frase, si no hay «:») es una escena. Cada escena hereda el entorno global si no
    nombra uno propio.
    """
    if use_ai:
        from .llm import plan_ai

        sb = plan_ai(prompt, fps=fps)
        if sb is not None:
            return sb

    norm = normalize(prompt)
    fmt = find_keyword(norm, FORMAT_WORDS) or "horizontal"
    width, height = FORMATS[fmt]
    total = _total_seconds(norm)

    head, sep, body = prompt.partition(":")
    if not sep:
        head, body = prompt, prompt
    sentences = [s.strip(" .;\n\t") for s in re.split(r"[.;!?\n]+", body)]
    sentences = [s for s in sentences if s]
    title = _clean_title(re.split(r"[.;!?\n]", head)[0])
    if sep:
        texts = [title] + sentences
    else:
        texts = sentences or [title]
        title = texts[0] = _clean_title(texts[0])

    global_bg = find_keyword(norm, BACKGROUND_WORDS) or "degradado"
    # duración proporcional al número de palabras (mín. 2 s), escalada al total pedido
    weights = [max(2.0, 0.45 * len(t.split()) + 1.2) for t in texts]
    if total:
        k = total / sum(weights)
        weights = [w * k for w in weights]
    scenes = []
    for i, (t, d) in enumerate(zip(texts, weights)):
        bg = find_keyword(normalize(t), BACKGROUND_WORDS) or global_bg
        scenes.append(Scene(text=t, duration=round(d, 2), background=bg, transition="fundido" if i else "corte"))
    return Storyboard(title=title, scenes=scenes, width=width, height=height, fps=fps)


def validate(sb: Storyboard) -> Storyboard:
    """Corrige valores fuera de rango (entornos desconocidos, duraciones ≤ 0)."""
    for s in sb.scenes:
        if s.background not in BACKGROUNDS:
            s.background = "degradado"
        if s.transition not in TRANSITIONS:
            s.transition = "fundido"
        s.duration = float(min(max(s.duration, 0.5), 60.0))
    return sb
