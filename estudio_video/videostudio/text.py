"""Utilidades de texto en español: normalización y búsqueda de palabras clave."""

from __future__ import annotations

import re
import unicodedata


def normalize(s: str) -> str:
    """Minúsculas y sin tildes («Cámara» → «camara»)."""
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def find_keyword(text: str, vocab: dict[str, tuple[str, ...]]) -> str | None:
    """Devuelve la clave de ``vocab`` cuya palabra aparece antes en ``text`` (ya normalizado)."""
    best, pos = None, len(text) + 1
    for key, words in vocab.items():
        for w in words:
            m = re.search(r"\b" + re.escape(w), text)
            if m and m.start() < pos:
                best, pos = key, m.start()
    return best
