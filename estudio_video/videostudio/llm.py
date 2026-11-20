"""Modo IA opcional: Claude interpreta descripciones y órdenes libres.

Requiere el paquete ``anthropic`` y credenciales (``ANTHROPIC_API_KEY`` o ``ant auth login``).
Si algo falla (sin paquete, sin clave, sin red, rechazo) las funciones devuelven ``None`` y el
llamador vuelve a las reglas sin red. La respuesta se fuerza a JSON con *structured outputs*.
"""

from __future__ import annotations

import json

from .backgrounds import BACKGROUNDS
from .effects import EFFECTS
from .looks import Look
from .plan import TRANSITIONS, Scene, Storyboard, validate

MODEL = "claude-opus-5-5"


def _ask(system: str, user: str, schema: dict, max_tokens: int = 4000) -> dict | None:
    try:
        import anthropic
    except ImportError:
        print("[aviso] Falta el paquete 'anthropic' (pip install anthropic); uso reglas sin IA.")
        return None
    try:
        client = anthropic.Anthropic()
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.AuthenticationError:
        print("[aviso] Claude: credenciales no válidas o ausentes; uso reglas sin IA.")
        return None
    except anthropic.APIConnectionError:
        print("[aviso] Claude: sin conexión; uso reglas sin IA.")
        return None
    except anthropic.APIStatusError as e:
        print(f"[aviso] Claude devolvió {e.status_code}; uso reglas sin IA.")
        return None
    if resp.stop_reason in ("refusal", "max_tokens"):
        print(f"[aviso] Claude no completó la respuesta ({resp.stop_reason}); uso reglas sin IA.")
        return None
    text = next((b.text for b in resp.content if b.type == "text"), None)
    try:
        return json.loads(text) if text else None
    except json.JSONDecodeError:
        return None


_STORY_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "format": {"type": "string", "enum": ["horizontal", "vertical", "cuadrado"]},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "duration": {"type": "number"},
                    "background": {"type": "string", "enum": list(BACKGROUNDS)},
                    "transition": {"type": "string", "enum": list(TRANSITIONS)},
                },
                "required": ["text", "duration", "background", "transition"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "format", "scenes"],
    "additionalProperties": False,
}

_STORY_SYSTEM = (
    "Eres guionista de vídeos cortos. Convierte la petición del usuario en un guion de escenas. "
    "Cada escena muestra un rótulo breve (máx. 12 palabras, en el idioma del usuario) sobre un "
    "entorno animado elegido de la lista permitida. Respeta la duración total y el formato si se "
    "indican; si no, 15-30 s y horizontal. La primera escena es el título y usa transición 'corte'."
)


def plan_ai(prompt: str, fps: int = 25) -> Storyboard | None:
    data = _ask(_STORY_SYSTEM, prompt, _STORY_SCHEMA)
    if not data or not data.get("scenes"):
        return None
    from .plan import FORMATS

    w, h = FORMATS.get(data.get("format", "horizontal"), FORMATS["horizontal"])
    scenes = [Scene(**s) for s in data["scenes"]]
    return validate(Storyboard(title=data["title"], scenes=scenes, width=w, height=h, fps=fps))


_LOOK_SCHEMA = {
    "type": "object",
    "properties": {
        "background": {"type": "string", "enum": ["sin_cambio", "ninguno", *BACKGROUNDS]},
        "blur_background": {"type": "boolean"},
        "body": {"type": "string", "enum": ["sin_cambio", "ninguno", *EFFECTS]},
        "face": {"type": "string", "enum": ["sin_cambio", "ninguno", *EFFECTS]},
    },
    "required": ["background", "blur_background", "body", "face"],
    "additionalProperties": False,
}


def parse_look_ai(command: str, current: Look) -> Look | None:
    system = (
        "Traduce la orden del usuario para una cámara con efectos a un ajuste de entorno (fondo), "
        "efecto de cuerpo y efecto de cara, eligiendo de las listas permitidas el más parecido. "
        "Usa 'sin_cambio' para lo que la orden no menciona y 'ninguno' para quitar un efecto. "
        f"Estado actual: {current.describe()}."
    )
    d = _ask(system, command, _LOOK_SCHEMA, max_tokens=1000)
    if not d:
        return None

    def pick(new: str, old: str | None) -> str | None:
        return old if new == "sin_cambio" else (None if new == "ninguno" else new)

    bg = pick(d["background"], current.background)
    return Look(
        background=bg,
        body=pick(d["body"], current.body),
        face=pick(d["face"], current.face),
        blur_background=bool(d["blur_background"]) and bg is None,
    )
