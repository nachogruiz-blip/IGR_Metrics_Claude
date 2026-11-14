"""malliavin — cálculo de Malliavin numérico y aplicaciones en finanzas.

Módulos
-------
brownian     Simulación de trayectorias brownianas y de procesos GBM.
chaos        Descomposición en caos de Wiener (polinomios de Hermite).
derivative   Derivada de Malliavin: fórmulas analíticas y aproximación discreta.
skorokhod    Divergencia (integral de Skorokhod) e integración por partes.
clark_ocone  Representación de Clark–Ocone y cobertura.
greeks       Griegas por pesos de Malliavin vs diferencias finitas.
density      Estimación de densidades vía integración por partes.
bs           Fórmulas cerradas de Black–Scholes (referencia).
plotting     Estilo y paleta comunes para las figuras.

Ver docs/guia_libreria.md para el mapa fórmula -> función.
"""

from . import bs, brownian, chaos, clark_ocone, density, derivative, greeks, skorokhod

__all__ = [
    "bs",
    "brownian",
    "chaos",
    "clark_ocone",
    "density",
    "derivative",
    "greeks",
    "skorokhod",
]
__version__ = "0.1.0"
