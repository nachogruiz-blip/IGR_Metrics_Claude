"""Órdenes por voz, sin conexión, con Vosk.

* :class:`VoiceListener` escucha el micrófono en segundo plano y entrega cada frase reconocida
  a una función (en la cámara, la misma cola que las órdenes escritas).
* :func:`dictate` graba un dictado completo para ``crear --voz``.

El reconocimiento es local: el audio no sale del ordenador. La primera vez Vosk descarga su
modelo pequeño de español (~40 MB) a ``~/.cache/vosk``. Requiere ``pip install vosk
sounddevice`` y, en Linux, ``libportaudio2``.
"""

from __future__ import annotations

import json
import queue
import re
import threading
import time
from typing import Callable

from .text import normalize

SAMPLE_RATE = 16000

#: Acciones de la cámara reconocidas por voz o por escrito (la frase entera debe encajar).
ACTIONS: dict[str, str] = {
    "grabar": r"(empieza a |ponte a |puedes )?(grabar|graba|grabacion|empieza la grabacion|rec)( (el )?video)?",
    "parar": r"(para|deja de grabar|para de grabar|para la grabacion|corta|stop|detente)( (de )?grabar| la grabacion)?",
    "foto": r"(haz(me)? (una )?|saca(me)? (una )?)?(foto|captura|fotografia)",
    "salir": r"(salir|sal|cierra|cerrar|adios|apaga|termina)( la camara| el programa)?",
}


def voice_action(text: str) -> str | None:
    """«haz una foto» → «foto»; «ponme en la playa» → ``None`` (no es una acción)."""
    t = normalize(text).strip(" .!¡?¿")
    for name, pattern in ACTIONS.items():
        if re.fullmatch(pattern, t):
            return name
    return None


def strip_wake_word(text: str, wake_word: str | None) -> str | None:
    """Con palabra clave («estudio, ponme en la playa») devuelve el resto; si falta, ``None``."""
    if not wake_word:
        return text.strip() or None
    t = re.sub(r"[,.;:!¡?¿]", " ", normalize(text)).strip()
    t, w = re.sub(r"\s+", " ", t), normalize(wake_word).strip()
    if t == w or not t.startswith(w + " "):
        return None
    return t[len(w) :].strip(" ,") or None


_DICTATION = [
    (r"\s*\bdos puntos\b\s*", ": "),
    (r"\s*\b(punto y aparte|siguiente escena|nueva escena|punto)\b\s*", ". "),
    (r"\s*\bcoma\b\s*", ", "),
]


def dictation_to_text(words: str) -> str:
    """Convierte la puntuación dictada en signos («… viaje dos puntos despegamos punto …»).

    Vosk no devuelve puntuación, así que las escenas se separan diciendo «punto» o
    «siguiente escena», y el título del resto con «dos puntos».
    """
    s = words.strip()
    for pattern, rep in _DICTATION:
        s = re.sub(pattern, rep, s)
    s = re.sub(r"\s+", " ", s).strip()
    # mayúscula tras cada signo de cierre
    return re.sub(r"(^|[.:]\s)([a-záéíóúñ])", lambda m: m.group(1) + m.group(2).upper(), s)


def load_model(model_path: str | None = None, lang: str = "es"):
    try:
        import vosk
    except ImportError as e:
        raise RuntimeError("Para la voz instala: pip install vosk sounddevice") from e
    vosk.SetLogLevel(-1)
    return vosk.Model(model_path=model_path) if model_path else vosk.Model(lang=lang)


def _results(recognizer, chunks) -> "iter[str]":
    """Pasa bloques de audio al reconocedor y produce cada frase final no vacía."""
    for data in chunks:
        if data is None:
            break
        if recognizer.AcceptWaveform(data):
            text = json.loads(recognizer.Result()).get("text", "").strip()
            if text:
                yield text
    text = json.loads(recognizer.FinalResult()).get("text", "").strip()
    if text:
        yield text


class VoiceListener:
    """Escucha en un hilo y llama a ``on_text(frase)`` por cada frase reconocida."""

    def __init__(self, on_text: Callable[[str], None], wake_word: str | None = None,
                 model_path: str | None = None, device: int | str | None = None) -> None:
        self.on_text = on_text
        self.wake_word = wake_word
        self.model_path = model_path
        self.device = device
        self._audio: "queue.Queue[bytes | None]" = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stream = None

    def handle(self, text: str) -> None:
        cmd = strip_wake_word(text, self.wake_word)
        if cmd:
            print(f"🎤 «{cmd}»")
            self.on_text(cmd)

    def process(self, recognizer, chunks) -> None:
        for text in _results(recognizer, chunks):
            self.handle(text)

    def _chunks(self):
        while True:
            yield self._audio.get()

    def start(self) -> "VoiceListener":  # pragma: no cover - necesita micrófono
        import sounddevice as sd
        import vosk

        model = load_model(self.model_path)
        rec = vosk.KaldiRecognizer(model, SAMPLE_RATE)
        self._stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE, blocksize=4000, dtype="int16", channels=1, device=self.device,
            callback=lambda data, frames, t, status: self._audio.put(bytes(data)),
        )
        self._stream.start()
        self._thread = threading.Thread(target=self.process, args=(rec, self._chunks()), daemon=True)
        self._thread.start()
        hint = f" (empieza cada orden con «{self.wake_word}»)" if self.wake_word else ""
        print(f"🎤 Escuchando órdenes por voz{hint}.")
        return self

    def stop(self) -> None:  # pragma: no cover - necesita micrófono
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
        self._audio.put(None)


def dictate(max_seconds: float = 90, silence_end: float = 3.0, model_path: str | None = None,
            device: int | str | None = None) -> str:  # pragma: no cover - necesita micrófono
    """Graba un dictado hasta decir «fin del vídeo»/«terminado» o ``silence_end`` s de silencio."""
    import sounddevice as sd
    import vosk

    rec = vosk.KaldiRecognizer(load_model(model_path), SAMPLE_RATE)
    parts: list[str] = []
    t0 = last = time.time()
    print("🎤 Dicta el vídeo. Di «dos puntos» tras el título y «punto» entre escenas; "
          "termina con «fin del vídeo» o calla 3 segundos.")
    with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=4000, dtype="int16", channels=1, device=device) as st:
        while time.time() - t0 < max_seconds:
            data, _ = st.read(4000)
            if rec.AcceptWaveform(bytes(data)):
                text = json.loads(rec.Result()).get("text", "").strip()
                if text:
                    parts.append(text)
                    last = time.time()
                    print(f"   … {text}")
                    if re.search(r"\b(fin del video|terminado|ya esta)$", normalize(text)):
                        break
            elif json.loads(rec.PartialResult()).get("partial"):
                last = time.time()
            if parts and time.time() - last > silence_end:
                break
    parts.append(json.loads(rec.FinalResult()).get("text", ""))
    words = " ".join(p for p in parts if p)
    words = re.sub(r"\b(fin del video|fin del vídeo|terminado|ya esta|ya está)\s*$", "", words)
    return dictation_to_text(words)
