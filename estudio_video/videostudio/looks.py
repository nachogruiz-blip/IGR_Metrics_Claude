"""«Looks» de cámara: qué entorno, qué efecto de cuerpo y qué efecto de cara aplicar.

``parse_look`` traduce órdenes en español como «ponme en la playa con cara de robot y el cuerpo
de dibujo animado» a un :class:`Look`. Funciona sin red con reglas de palabras clave; si se pide
``use_ai=True`` y hay credenciales de Claude, se usa el modelo para órdenes más libres.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from .backgrounds import BACKGROUND_WORDS, BACKGROUNDS
from .effects import EFFECT_WORDS, EFFECTS
from .text import find_keyword, normalize


@dataclass(frozen=True)
class Look:
    """Transformación de cámara. ``None`` en un campo = no tocar esa parte."""

    background: str | None = None  # nombre de BACKGROUNDS o ruta a imagen/vídeo
    body: str | None = None  # nombre de EFFECTS
    face: str | None = None  # nombre de EFFECTS o ruta a imagen (careta)
    blur_background: bool = False  # desenfocar el fondo real en lugar de sustituirlo

    def describe(self) -> str:
        parts = []
        if self.background:
            parts.append(f"entorno={self.background}")
        elif self.blur_background:
            parts.append("fondo desenfocado")
        if self.body:
            parts.append(f"cuerpo={self.body}")
        if self.face:
            parts.append(f"cara={self.face}")
        return ", ".join(parts) or "sin cambios"


FACE_ANCHORS = ("cara", "rostro", "cabeza", "careta", "mascara")
BODY_ANCHORS = ("cuerpo", "ropa", "piel", "todo yo", "mi figura", "silueta", "convierteme", "vuelveme", "hazme")
BG_ANCHORS = ("fondo", "entorno", "ponme", "llevame", "estoy en", "escenario", "lugar", "mandame")
RESET_WORDS = ("quita todo", "quitalo todo", "reset", "sin efectos", "como estaba", "vuelve a la normalidad")


def _segments(text: str) -> list[tuple[str, str, str]]:
    """Corta la orden en trozos [(ancla, texto, prefijo)] según dónde aparecen cara/cuerpo/fondo.

    El prefijo son las ~15 letras previas al ancla («quita la» en «quita la cara»).
    """
    marks: list[tuple[int, str]] = []
    for kind, words in (("face", FACE_ANCHORS), ("body", BODY_ANCHORS), ("bg", BG_ANCHORS)):
        for w in words:
            for m in re.finditer(r"\b" + re.escape(w), text):
                marks.append((m.start(), kind))
    marks.sort()
    if not marks:
        return [("", text, "")]
    segs = [("", text[: marks[0][0]], "")] if marks[0][0] > 0 else []
    for i, (pos, kind) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        segs.append((kind, text[pos:end], text[max(0, pos - 15) : pos]))
    return segs


def parse_look(command: str, current: Look | None = None, use_ai: bool = False) -> Look:
    """Interpreta una orden en español y devuelve el nuevo :class:`Look`.

    Las partes no mencionadas se conservan de ``current`` (las órdenes se acumulan:
    «ahora cara de zombi» cambia sólo la cara). «Quita todo» vuelve al original.

    Ejemplos
    --------
    >>> parse_look("ponme en la playa con cara de robot").background
    'playa'
    """
    current = current or Look()
    if use_ai:
        from .llm import parse_look_ai

        ai = parse_look_ai(command, current)
        if ai is not None:
            return ai
    text = normalize(command)
    if any(w in text for w in RESET_WORDS) or text.strip(" .!") in ("normal", "original"):
        return Look()

    bg, body, face = current.background, current.body, current.face
    blur_bg = current.blur_background
    blur_re = r"(desenfoc|difumin|borros)\w*\s+(el\s+|mi\s+)?(fondo|entorno)|(fondo|entorno)\s+(desenfocad|borros|difuminad)\w*"
    if re.search(blur_re, text):
        bg, blur_bg = None, True
        text = re.sub(blur_re, " ", text)
    for kind, seg, prefix in _segments(text):
        removing = bool(re.search(r"\b(quita|quitame|sin|elimina|borra|normal|original|real)\b", prefix + " " + seg))
        eff = find_keyword(seg, EFFECT_WORDS)
        env = find_keyword(seg, BACKGROUND_WORDS)
        if kind == "face":
            face = None if removing and not eff else (eff or face)
        elif kind == "body":
            body = None if removing and not eff else (eff or body)
        elif kind == "bg":
            if removing and not env:
                bg, blur_bg = None, False
            elif re.search(r"desenfoc|borros|difumin", seg) and not env:
                bg, blur_bg = None, True
            elif env:
                bg, blur_bg = env, False
        else:  # sin ancla: un entorno se entiende como fondo, un efecto como todo el cuerpo
            if env:
                bg, blur_bg = env, False
            elif eff:
                body = eff
    return replace(current, background=bg, body=body, face=face, blur_background=blur_bg)


def vocabulary() -> str:
    """Texto de ayuda con entornos y efectos disponibles."""
    return (
        "Entornos: " + ", ".join(BACKGROUNDS) + "\n"
        "Efectos (cuerpo o cara): " + ", ".join(EFFECTS) + "\n"
        "También: una ruta a imagen/vídeo como fondo o una imagen PNG como careta."
    )
