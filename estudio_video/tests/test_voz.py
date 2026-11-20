import json

import numpy as np
import pytest

from videostudio.camera import label_frame
from videostudio.voice import VoiceListener, dictation_to_text, strip_wake_word, voice_action


@pytest.mark.parametrize("frase,accion", [
    ("graba", "grabar"), ("empieza a grabar", "grabar"), ("para", "parar"), ("deja de grabar", "parar"),
    ("haz una foto", "foto"), ("foto", "foto"), ("salir", "salir"), ("cierra la cámara", "salir"),
    ("ponme en la playa", None), ("para la cara pon un robot", None),
])
def test_acciones(frase, accion):
    assert voice_action(frase) == accion


def test_palabra_clave():
    assert strip_wake_word("ponme en la playa", None) == "ponme en la playa"
    assert strip_wake_word("Estudio, ponme en la playa", "estudio") == "ponme en la playa"
    assert strip_wake_word("ponme en la playa", "estudio") is None
    assert strip_wake_word("estudio", "estudio") is None


def test_dictado_a_texto_y_guion():
    t = dictation_to_text("un viaje dos puntos despegamos punto vemos estrellas siguiente escena volvemos")
    assert t == "Un viaje: Despegamos. Vemos estrellas. Volvemos"
    from videostudio import plan_from_text

    assert [s.text for s in plan_from_text(t).scenes] == ["Viaje", "Despegamos", "Vemos estrellas", "Volvemos"]


class FakeRecognizer:
    """Imita a vosk.KaldiRecognizer: cada bloque es ya el texto de una frase («» = sin frase)."""

    def __init__(self):
        self._last = ""

    def AcceptWaveform(self, data):
        self._last = data.decode()
        return bool(self._last)

    def Result(self):
        return json.dumps({"text": self._last})

    def FinalResult(self):
        return json.dumps({"text": ""})


def test_listener_entrega_frases_con_palabra_clave():
    got = []
    VoiceListener(got.append, wake_word="estudio").process(
        FakeRecognizer(), [b"", b"estudio ponme en la nieve", b"hola que tal", b"estudio haz una foto", None])
    assert got == ["ponme en la nieve", "haz una foto"]


def test_marca_visible_solo_en_la_esquina():
    f = np.full((120, 200, 3), 128, np.uint8)
    out = label_frame(f)
    assert out.shape == f.shape and np.array_equal(out[:60], f[:60])
    assert not np.array_equal(out[-20:, -100:], f[-20:, -100:])
