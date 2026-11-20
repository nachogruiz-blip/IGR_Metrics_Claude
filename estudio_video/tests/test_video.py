import json

import cv2
import numpy as np
import pytest

from videostudio import edit
from videostudio.camera import process_video
from videostudio.cli import main
from videostudio.looks import Look
from videostudio.plan import Scene, Storyboard
from videostudio.render import render, write_video


def _count(path):
    cap = cv2.VideoCapture(str(path))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return n, w, h


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    sb = Storyboard("t", [Scene("Hola", 1.0, "playa", "corte"), Scene("Adiós", 1.0, "nieve", "fundido")],
                    width=160, height=96, fps=10)
    return render(sb, tmp_path_factory.mktemp("v") / "clip.mp4")


def test_render_numero_de_fotogramas(clip):
    assert _count(clip) == (20, 160, 96)


def test_editar_recortar_velocidad_formato(clip, tmp_path):
    edit.trim(clip, tmp_path / "a.mp4", 0.5, 1.5)
    assert edit.probe_duration(tmp_path / "a.mp4") == pytest.approx(1.0, abs=0.15)
    edit.speed(clip, tmp_path / "b.mp4", 2.0)
    # ±2 fotogramas: ffmpeg rellena el final al pasar a fps constante (10 fps en el test)
    assert edit.probe_duration(tmp_path / "b.mp4") == pytest.approx(1.0, abs=0.25)
    edit.reframe(clip, tmp_path / "c.mp4", "vertical")
    assert _count(tmp_path / "c.mp4")[1:] == (720, 1280)
    edit.concat([clip, clip], tmp_path / "d.mp4")
    assert edit.probe_duration(tmp_path / "d.mp4") == pytest.approx(4.0, abs=0.2)


def test_atempo_encadenado():
    cmd = " ".join(map(str, edit.speed_cmd("x.mp4", "y.mp4", 4.0)))
    assert "atempo=2,atempo=2" in cmd and "setpts=PTS/4.0" in cmd


def test_procesar_video_opencv(tmp_path):
    w, h, fps = 64, 48, 10
    frames = []
    for i in range(20):  # cuadrado que se mueve sobre fondo fijo
        f = np.full((h, w, 3), 90, np.uint8)
        f[15:35, 5 + i * 2 : 25 + i * 2] = 240
        frames.append(f)
    src = write_video(iter(frames), tmp_path / "in.mp4", w, h, fps)
    out = process_video(src, tmp_path / "out.mp4", Look(background="fuego"), engine="opencv")
    cap = cv2.VideoCapture(str(out))
    ok, f = cap.read()
    cap.release()
    assert ok
    rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB).astype(int)
    assert abs(rgb[25, 15] - 240).max() < 30  # la «persona» se conserva
    assert abs(rgb[2, 60] - 90).max() > 3  # el fondo ya no es el gris original


def test_cli_guion(capsys):
    assert main(["guion", "vídeo cuadrado de 6 segundos: uno. dos"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["width"] == d["height"] == 1080 and len(d["scenes"]) == 3


def test_metadatos_de_ia(clip):
    import subprocess

    from videostudio.render import AI_NOTICE, ffmpeg_exe

    r = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(clip)], capture_output=True, text=True)
    assert AI_NOTICE in r.stderr
