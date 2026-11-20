"""La app arranca en modo demo sin excepciones (``AppTest`` no informa de errores de sintaxis en
``at.exception``; por eso se comprueba también el título)."""

import os
from pathlib import Path

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def test_app_runs_in_demo(monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setitem(os.environ, "PRICECHECK_DEMO", "1")
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception, at.exception
    assert len(at.title) == 1 and "Aurora X5" in at.title[0].value
    assert [t.label for t in at.tabs] == ["Comparativa", "Detalle por tienda", "Metodología"]
    best = next(m for m in at.metric if m.label == "Mejor opción fiable")
    assert best.value == "313,99 €"
