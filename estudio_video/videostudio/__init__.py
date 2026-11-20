"""Estudio de vídeo: crea vídeos a partir de texto y transforma la cámara (fondo, cuerpo, cara)."""

from .plan import Scene, Storyboard, plan_from_text
from .looks import Look, parse_look

__all__ = ["Scene", "Storyboard", "plan_from_text", "Look", "parse_look"]
__version__ = "0.1.0"
