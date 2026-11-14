# Bibliografía comentada

Entradas BibTeX completas en [`latex/referencias.bib`](../latex/referencias.bib).
Los DOI incluidos en el `.bib` se han verificado; para el resto, consultar la editorial.

## Textos de referencia (teoría)

| Clave BibTeX | Referencia | Para qué sirve |
|---|---|---|
| `nualart2006` | D. Nualart, *The Malliavin Calculus and Related Topics*, 2ª ed., Springer 2006 | Referencia estándar. Cap. 1: derivada, divergencia, caos. Cap. 2: existencia/regularidad de densidades (fórmula usada en `density.py`). Cap. 6: aplicaciones a finanzas. |
| `nualartnualart2018` | D. Nualart, E. Nualart, *Introduction to Malliavin Calculus*, CUP 2018 | Introducción más pedagógica y corta; buen primer libro. |
| `dinunno2009` | G. Di Nunno, B. Øksendal, F. Proske, *Malliavin Calculus for Lévy Processes with Applications to Finance*, Springer 2009 | Enfoque vía caos (muy accesible), Clark–Ocone generalizado, cobertura y extensión a Lévy. |
| `oksendal1997` | B. Øksendal, *An Introduction to Malliavin Calculus with Applications to Economics*, notas 1997 | Notas gratuitas, muy útiles para empezar (Clark–Ocone, Skorokhod). |
| `nourdinpeccati2012` | I. Nourdin, G. Peccati, *Normal Approximations with Malliavin Calculus*, CUP 2012 | Método de Stein + Malliavin, teoremas de cuarto momento. |
| `malliavin1978` | P. Malliavin, *Stochastic calculus of variation and hypoelliptic operators*, 1978 | Artículo fundacional. |
| `skorokhod1975` | A. V. Skorokhod, *On a generalization of a stochastic integral*, 1975 | Origen de la integral anticipativa (`skorokhod.py`). |

## Finanzas

| Clave BibTeX | Referencia | Para qué sirve |
|---|---|---|
| `fournie1999` | Fournié, Lasry, Lebuchoux, Lions, Touzi, *Finance Stoch.* 3 (1999) | **Artículo clave** de las griegas por Malliavin (pesos de `greeks.py`, incluida la asiática). |
| `fournie2001` | Fournié, Lasry, Lebuchoux, Lions, *Finance Stoch.* 5 (2001) | Esperanzas condicionadas y localización (opciones americanas, reducción de varianza). |
| `benhamou2003` | E. Benhamou, *Math. Finance* 13 (2003) | Pesos de Malliavin de varianza mínima. |
| `ocone1984`, `oconekaratzas1991` | Ocone (1984); Ocone & Karatzas (1991) | Fórmula de Clark–Ocone y carteras óptimas (`clark_ocone.py`). |
| `malliavinthalmaier2006` | P. Malliavin, A. Thalmaier, *Stochastic Calculus of Variations in Mathematical Finance*, Springer 2006 | Visión del propio Malliavin sobre finanzas: griegas, mercados incompletos. |
| `alos2007` | Alòs, León, Vives, *Finance Stoch.* 11 (2007) | Volatilidad implícita a corto plazo vía Malliavin (fórmula de Hull–White anticipativa). |
| `alosgarcialorite2021` | E. Alòs, D. García Lorite, *Malliavin Calculus in Finance*, CRC 2021 | Libro práctico reciente: volatilidad implícita, skew, modelos rough. Buen siguiente paso. |
| `glasserman2003` | P. Glasserman, *Monte Carlo Methods in Financial Engineering*, Springer 2003 | Cap. 7: comparación diferencias finitas / pathwise / likelihood ratio (≈ Malliavin en BS). |

## Ruta de lectura sugerida

1. Øksendal (1997) o Nualart & Nualart (2018), caps. 1–3 → ejemplos 01–03.
2. Clark–Ocone en Di Nunno et al. (2009) cap. 4 → ejemplo 04.
3. Fournié et al. (1999) → ejemplo 05.
4. Nualart (2006) §2.1 → ejemplo 06.
5. Alòs & García Lorite (2021) para volatilidad implícita (futuro módulo).
