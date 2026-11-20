"""stockdash: indicadores técnicos y fundamentales, puntuación agregada y señal a 1–3 meses."""

from .scoring import Assessment, assess

__all__ = ["Assessment", "assess"]
