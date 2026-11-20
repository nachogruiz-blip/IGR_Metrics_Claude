import numpy as np
import pytest

from videostudio.backgrounds import BACKGROUNDS
from videostudio.camera import Transformer, compose
from videostudio.effects import EFFECTS
from videostudio.looks import Look
from videostudio.segment import Box, OpenCVSegmenter


@pytest.mark.parametrize("name", list(BACKGROUNDS))
def test_fondos_forma_determinismo_animacion(name):
    f = BACKGROUNDS[name]
    a, b, c = f(1.0, 96, 64), f(1.0, 96, 64), f(2.7, 96, 64)
    assert a.shape == (64, 96, 3) and a.dtype == np.uint8
    assert np.array_equal(a, b)
    if name not in ("estudio",):  # el estudio respira muy despacio
        assert not np.array_equal(a, c)


@pytest.mark.parametrize("name", list(EFFECTS))
def test_efectos_conservan_forma(name):
    img = np.random.default_rng(0).integers(0, 255, (50, 70, 3), dtype=np.uint8)
    out = EFFECTS[name](img, 1.0)
    assert out.shape == img.shape and out.dtype == np.uint8


def _frame():
    return np.random.default_rng(1).integers(0, 255, (60, 80, 3), dtype=np.uint8)


def test_compose_identidad_y_fondo():
    f = _frame()
    assert np.array_equal(compose(f, np.ones((60, 80)), [], Look(), 0.0), f)
    # sin persona ⇒ todo es entorno; persona entera ⇒ fotograma original
    bg = BACKGROUNDS["playa"](0.5, 80, 60)
    assert np.array_equal(compose(f, np.zeros((60, 80)), [], Look("playa"), 0.5), bg)
    assert np.array_equal(compose(f, np.ones((60, 80)), [], Look("playa"), 0.5), f)


def test_cara_solo_dentro_de_la_caja():
    f = _frame()
    out = compose(f, np.zeros((60, 80)), [Box(30, 20, 16, 16)], Look(face="emoji"), 0.0)
    assert np.array_equal(out[:, :15], f[:, :15]) and np.array_equal(out[:, 60:], f[:, 60:])
    assert not np.array_equal(out[25:35, 32:44], f[25:35, 32:44])


def test_segmentador_opencv_detecta_lo_que_cambia():
    ref = np.full((40, 40, 3), 100, np.uint8)
    f = ref.copy()
    f[10:30, 10:30] = 230
    m = OpenCVSegmenter(ref).person_mask(f, 0)
    assert m[20, 20] > 0.9 and m[2, 2] < 0.05
    tr = Transformer(Look("espacio"), OpenCVSegmenter(ref), smooth=0)
    out = tr(f, 0.0)
    assert np.array_equal(out[20, 20], f[20, 20])
    assert np.array_equal(out[0, 0], BACKGROUNDS["espacio"](0.0, 40, 40)[0, 0])
