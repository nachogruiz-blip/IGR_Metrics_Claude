import pytest

from videostudio import Look, Storyboard, parse_look, plan_from_text
from videostudio.plan import validate


def test_plan_duracion_formato_y_escenas():
    sb = plan_from_text("Vídeo vertical de 12 segundos sobre un viaje: Despegamos hacia el espacio. "
                        "Vemos la ciudad. Volvemos al atardecer.")
    assert (sb.width, sb.height) == (720, 1280)
    assert sb.duration == pytest.approx(12, abs=0.05)
    assert sb.title == "Viaje"
    assert [s.background for s in sb.scenes[1:]] == ["espacio", "ciudad", "atardecer"]
    assert sb.scenes[0].transition == "corte"


def test_plan_sin_dos_puntos_y_json():
    sb = plan_from_text("Un día en la playa. Luego una fiesta")
    assert len(sb.scenes) == 2 and sb.scenes[1].background == "neon"
    assert sb.width == 1280
    sb2 = Storyboard.from_json(sb.to_json())
    assert sb2 == sb


def test_validate_corrige():
    sb = plan_from_text("hola")
    sb.scenes[0].background, sb.scenes[0].duration = "marte", -3
    validate(sb)
    assert sb.scenes[0].background == "degradado" and sb.scenes[0].duration == 0.5


@pytest.mark.parametrize("orden,esperado", [
    ("ponme en la playa con cara de robot y el cuerpo de dibujo animado", Look("playa", "dibujo", "robot")),
    ("llévame al espacio con cara de alien", Look("espacio", None, "alien")),
    ("hazme un zombi", Look(body="zombi")),
    ("desenfoca el fondo", Look(blur_background=True)),
    ("fondo marino y cuerpo fantasma", Look("fondo_marino", "fantasma")),
    ("careta de emoji", Look(face="emoji")),
])
def test_parse_look(orden, esperado):
    assert parse_look(orden) == esperado


def test_ordenes_se_acumulan_y_se_quitan():
    lk = parse_look("en la nieve con cara de emoji")
    lk = parse_look("ahora cuerpo de robot", lk)
    assert lk == Look("nieve", "robot", "emoji")
    assert parse_look("quita la cara", lk) == Look("nieve", "robot", None)
    assert parse_look("quítame el fondo", lk).background is None
    assert parse_look("quita todo", lk) == Look()
