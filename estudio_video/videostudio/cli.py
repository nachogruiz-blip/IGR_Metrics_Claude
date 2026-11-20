"""Línea de órdenes: ``python -m videostudio <orden> …``.

Órdenes
-------
crear     «texto»            → vídeo MP4 generado desde una descripción
guion     «texto»            → muestra el guion (JSON) sin renderizar; editable y reutilizable
camara    [«look»]           → cámara web en directo con fondo/cuerpo/cara cambiables
procesar  vídeo «look»       → aplica un look a un vídeo grabado
editar    <operación> …      → recortar, unir, velocidad, música, rótulo, filtro, formato, gif
opciones                     → lista de entornos y efectos
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from . import edit
from .looks import Look, parse_look, vocabulary
from .plan import Storyboard, plan_from_text


def _slug(text: str) -> str:
    from .text import normalize

    s = re.sub(r"[^a-z0-9]+", "_", normalize(text)).strip("_")
    return s[:40] or "video"


def cmd_crear(a) -> int:
    from .render import render

    if a.guion:
        sb = Storyboard.from_json(Path(a.guion).read_text(encoding="utf-8"))
    else:
        texto = a.texto
        if a.voz:
            from .voice import dictate

            texto = dictate()
            print(f"Has dicho: {texto}")
            if not texto:
                print("No se reconoció nada.", file=sys.stderr)
                return 1
        sb = plan_from_text(texto, use_ai=a.ia, fps=a.fps)
    out = Path(a.salida or f"salidas/{_slug(sb.title)}.mp4")
    print(f"Guion: {len(sb.scenes)} escenas, {sb.duration:.1f} s, {sb.width}x{sb.height}")
    for i, s in enumerate(sb.scenes, 1):
        print(f"  {i}. [{s.background}, {s.duration:.1f} s] {s.text}")
    render(sb, out, audio=a.musica)
    print(f"Vídeo creado: {out}")
    return 0


def cmd_guion(a) -> int:
    sb = plan_from_text(a.texto, use_ai=a.ia)
    js = sb.to_json()
    if a.salida:
        Path(a.salida).write_text(js, encoding="utf-8")
        print(f"Guion guardado en {a.salida} (edítalo y usa: crear --guion {a.salida})")
    else:
        print(js)
    return 0


def _look_from_args(a) -> Look:
    look = parse_look(a.orden, use_ai=a.ia) if getattr(a, "orden", None) else Look()
    if a.fondo:
        look = Look(a.fondo, look.body, look.face, False)
    if a.cuerpo:
        look = Look(look.background, a.cuerpo, look.face, look.blur_background)
    if a.cara:
        look = Look(look.background, look.body, a.cara, look.blur_background)
    return look


def cmd_camara(a) -> int:
    from .camera import live

    live(camera=a.camara, look=_look_from_args(a), engine=a.motor, use_ai=a.ia, outdir=a.carpeta,
         voice=a.voz, wake_word=a.palabra_clave, label=not a.sin_marca)
    return 0


def cmd_procesar(a) -> int:
    from .camera import process_video

    look = _look_from_args(a)
    out = a.salida or str(Path(a.video).with_name(Path(a.video).stem + "_editado.mp4"))
    print(f"Look: {look.describe()}")
    process_video(a.video, out, look, engine=a.motor, label=not a.sin_marca)
    print(f"Vídeo creado: {out}")
    return 0


def cmd_editar(a) -> int:
    op = a.operacion
    out = a.salida
    if op == "recortar":
        edit.trim(a.entrada[0], out, a.inicio, a.fin)
    elif op == "unir":
        edit.concat(a.entrada, out)
    elif op == "velocidad":
        edit.speed(a.entrada[0], out, a.factor)
    elif op == "musica":
        edit.add_music(a.entrada[0], out, a.audio, a.volumen, a.mezclar)
    elif op == "rotulo":
        edit.caption(a.entrada[0], out, a.texto, a.posicion, a.inicio, a.fin)
    elif op == "filtro":
        edit.apply_filter(a.entrada[0], out, a.nombre)
    elif op == "formato":
        edit.reframe(a.entrada[0], out, a.nombre)
    elif op == "gif":
        edit.to_gif(a.entrada[0], out)
    print(f"Hecho: {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="videostudio", description="Estudio de vídeo por órdenes en español.")
    sub = p.add_subparsers(dest="orden_principal", required=True)

    c = sub.add_parser("crear", help="crear un vídeo desde texto")
    c.add_argument("texto", nargs="?", default="", help="descripción del vídeo")
    c.add_argument("-o", "--salida")
    c.add_argument("--guion", help="usar un guion JSON (de «guion») en vez de texto")
    c.add_argument("--musica", help="archivo de audio de fondo")
    c.add_argument("--fps", type=int, default=25)
    c.add_argument("--ia", action="store_true", help="usar Claude para escribir el guion")
    c.add_argument("--voz", action="store_true", help="dictar la descripción por el micrófono")
    c.set_defaults(func=cmd_crear)

    g = sub.add_parser("guion", help="ver/guardar el guion sin renderizar")
    g.add_argument("texto")
    g.add_argument("-o", "--salida")
    g.add_argument("--ia", action="store_true")
    g.set_defaults(func=cmd_guion)

    for name, helptext in (("camara", "cámara en directo"), ("procesar", "aplicar look a un vídeo")):
        s = sub.add_parser(name, help=helptext)
        if name == "procesar":
            s.add_argument("video")
            s.add_argument("-o", "--salida")
        s.add_argument("orden", nargs="?", default="", help="p. ej. «ponme en la playa con cara de robot»")
        s.add_argument("--fondo", help="entorno o ruta a imagen/vídeo")
        s.add_argument("--cuerpo", help="efecto de cuerpo")
        s.add_argument("--cara", help="efecto de cara o ruta a imagen PNG (careta)")
        s.add_argument("--motor", default="auto", choices=["auto", "mediapipe", "opencv"])
        s.add_argument("--ia", action="store_true", help="usar Claude para entender las órdenes")
        s.add_argument("--sin-marca", action="store_true",
                       help="no añadir la marca visible «Modificado con IA» (los metadatos la llevan siempre)")
        if name == "camara":
            s.add_argument("--camara", type=int, default=0, help="índice de la cámara")
            s.add_argument("--carpeta", default="salidas", help="dónde guardar fotos y grabaciones")
            s.add_argument("--voz", action="store_true", help="dar órdenes hablando (Vosk, sin conexión)")
            s.add_argument("--palabra-clave", help="sólo obedecer frases que empiecen así (p. ej. «estudio»)")
            s.set_defaults(func=cmd_camara)
        else:
            s.set_defaults(func=cmd_procesar)

    e = sub.add_parser("editar", help="editar vídeos existentes")
    e.add_argument("operacion", choices=["recortar", "unir", "velocidad", "musica", "rotulo", "filtro", "formato", "gif"])
    e.add_argument("entrada", nargs="+")
    e.add_argument("-o", "--salida", required=True)
    e.add_argument("--inicio", type=float, default=0.0)
    e.add_argument("--fin", type=float)
    e.add_argument("--factor", type=float, default=2.0, help="velocidad: 2 = doble, 0.5 = cámara lenta")
    e.add_argument("--audio")
    e.add_argument("--volumen", type=float, default=1.0)
    e.add_argument("--mezclar", action="store_true", help="mezclar música con el audio original")
    e.add_argument("--texto", default="")
    e.add_argument("--posicion", default="abajo", choices=["arriba", "centro", "abajo"])
    e.add_argument("--nombre", default="", help="filtro (sepia, blanco_negro…) o formato (vertical…)")
    e.set_defaults(func=cmd_editar)

    o = sub.add_parser("opciones", help="entornos y efectos disponibles")
    o.set_defaults(func=lambda a: print(vocabulary()) or 0)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.orden_principal == "crear" and not (args.texto or args.guion or args.voz):
        print("Indica un texto o --guion", file=sys.stderr)
        return 2
    return args.func(args)
