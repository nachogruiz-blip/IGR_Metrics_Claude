"""La app arranca en modo demo con cada perfil (acciones y oro) sin excepciones.

Ojo: ``AppTest`` no informa de los errores de sintaxis en ``at.exception``; por eso también se
comprueba que se ha pintado el título.
"""

import os
from pathlib import Path

import pytest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.mark.parametrize("ticker,tab", [("DEMO-ESPERA", "Balance y cuentas"), ("DEMO-ORO", "Factores macro")])
def test_app_runs_in_demo(ticker, tab, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setitem(os.environ, "ANALYST_DEMO", "1")
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception and len(at.title) == 1
    at.selectbox[0].set_value(ticker).run()
    assert not at.exception, at.exception
    assert ticker in at.title[0].value
    assert tab in [t.label for t in at.tabs]
