"""malliavin — cálculo de Malliavin numérico y aplicaciones en finanzas.

Módulos
-------
brownian     Simulación de trayectorias brownianas y de procesos GBM.
chaos        Descomposición en caos de Wiener (polinomios de Hermite).
derivative   Derivada de Malliavin: fórmulas analíticas y aproximación discreta.
skorokhod    Divergencia (integral de Skorokhod) e integración por partes.
clark_ocone  Representación de Clark–Ocone y cobertura.
greeks       Griegas: pesos de Malliavin, localización, Bismut–Elworthy–Li.
conditional  Esperanzas condicionales por IBP y opciones bermudas.
stochvol     Rough Bergomi y Heston: fórmula de Alòs y skew en tiempo corto.
density      Estimación de densidades vía integración por partes.
bs           Fórmulas cerradas de Black–Scholes (referencia).
plotting     Estilo y paleta comunes para las figuras.

Teoría: docs/pdf/Calculo_de_Malliavin_corregido.pdf (mapa en docs/mapa_pdf.md).
Ver docs/guia_libreria.md para el mapa fórmula -> función.
"""

from . import bs, brownian, chaos, clark_ocone, conditional, density, derivative, greeks, skorokhod, stochvol

__all__ = [
    "bs",
    "brownian",
    "chaos",
    "clark_ocone",
    "conditional",
    "density",
    "derivative",
    "greeks",
    "skorokhod",
    "stochvol",
]
__version__ = "0.3.0"
