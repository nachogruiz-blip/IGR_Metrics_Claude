"""Humo: cada script de uso diario se ejecuta en modo demo sin errores."""
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"

CASES = [
    ["tamano_posicion.py", "accion", "--capital", "50000", "--entrada", "100", "--stop", "95", "--objetivo", "115"],
    ["tamano_posicion.py", "fx", "--capital", "20000", "--par", "USDJPY", "--tipo", "150", "--stop-pips", "30"],
    ["tamano_posicion.py", "futuro", "--capital", "250000", "--simbolo", "GC", "--entrada", "2400", "--stop", "2380"],
    ["tamano_posicion.py", "atr", "--capital", "50000", "--atr", "2", "--precio", "100"],
    ["tamano_posicion.py", "cripto", "--capital", "10000", "--entrada", "100", "--stop", "95", "--apalancamiento", "25"],
    ["premercado.py", "--hora-utc", "8"],
    ["informe_riesgo.py"],
    ["backtest.py", "--estrategia", "rsi", "--grafico", ""],
    ["backtest.py", "--estrategia", "pares", "--grafico", ""],
    ["backtest.py", "--estrategia", "sig", "--grafico", ""],
    ["calculadoras.py", "iv", "--precio", "3", "--spot", "100", "--strike", "100", "--dias", "30"],
    ["calculadoras.py", "cruce", "--par", "EURJPY", "--cotiza", "EURUSD=1.1", "--cotiza", "USDJPY=150"],
    ["calculadoras.py", "crack", "--crudo", "75", "--gasolina", "2.3", "--gasoleo", "2.5"],
    ["calculadoras.py", "movimiento", "--spot", "5000", "--vol", "15", "--dias", "7"],
    ["calculadoras.py", "liderazgo"],
]


@pytest.mark.parametrize("args", CASES, ids=lambda a: " ".join(a[:2]))
def test_script_runs(args):
    out = subprocess.run([sys.executable, str(SCRIPTS / args[0]), *args[1:]], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip()


def test_journal_cli(tmp_path):
    f = tmp_path / "d.csv"
    base = [sys.executable, str(SCRIPTS / "diario.py")]
    for ex in ("1.0900", "1.0830"):
        r = subprocess.run(base + ["nueva", "--fichero", str(f), "--simbolo", "EURUSD", "--lado", "largo", "--entrada", "1.0850",
                                   "--stop", "1.0825", "--salida", ex, "--tamano", "100000", "--setup", "ruptura"],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
    r = subprocess.run(base + ["resumen", "--fichero", str(f)], capture_output=True, text=True)
    assert "Operaciones: 2" in r.stdout
