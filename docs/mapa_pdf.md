# Mapa: guía teórica (PDF) → LaTeX → código

Fuente: [`docs/pdf/Calculo_de_Malliavin_corregido.pdf`](pdf/Calculo_de_Malliavin_corregido.pdf),
*Cálculo de Malliavin: de los procesos estocásticos y la integral de Itô al estado del arte*
(105 págs., 7 partes, 23 capítulos + formulario + notación).

`latex/` **no transcribe** la guía: es su *compañero numérico*. Sigue su notación y cita su
numeración con `\guia{Teorema 8.9}`.

Leyenda: ✅ implementado · 🔜 candidato natural a módulo · 📖 sólo teórico (sin código previsto por ahora)

| Cap. guía | Tema | Estado | LaTeX (`latex/capitulos/`) | Código / ejemplo |
|---|---|---|---|---|
| 1 | Preliminares de probabilidad | 📖 | — | — |
| 2 | Movimiento browniano (Lévy–Ciesielski, variación cuadrática, reflexión) | 🔜 | — | `brownian.py` (simulación); faltan Lévy–Ciesielski y la variación cuadrática |
| 3 | Cálculo de Itô, Girsanov, representación de martingalas | 🔜 | — | `skorokhod.ito_integral` |
| 4 | EDEs, flujos, proceso tangente | ✅ parcial | 09 | `greeks.diffusion_with_tangent` |
| 5 | Procesos isonormales | 📖 | 01 (notación) | — |
| 6 | Caos de Wiener, H_n, fórmula del producto | ✅ | 02 | `chaos.py`, ej. 01 |
| 7 | Derivada de Malliavin; supremo (Prop. 7.16) | ✅ | 03 | `derivative.py`, ej. 02 |
| 8 | Divergencia, Skorokhod, Clark–Ocone (T. 8.9, 8.11) | ✅ | 04, 05 | `skorokhod.py`, `clark_ocone.py`, ej. 03–04 |
| 9 | Ornstein–Uhlenbeck, Mehler, Poincaré, hipercontractividad | 🔜 | — | posible `ornstein_uhlenbeck.py`: Mehler, L = −Σ n J_n |
| 10 | Densidades (T. 10.1), Nourdin–Viens | ✅ parcial | 07 | `density.py`, ej. 06; falta Nourdin–Viens |
| 11 | EDEs y Hörmander, matriz de Malliavin | 📖 | — | — |
| 12 | Griegas: pesos BS (P. 12.2), BEL (T. 12.3), asiática (P. 12.5), localización (§12.6), tabla §12.7 | ✅ | 06, 09 | `greeks.py`, ej. 05, 07 |
| 13 | Cobertura Clark–Ocone (call, digital, asiática, lookback), Merton–Ocone–Karatzas, insider | ✅ parcial | 05 | `clark_ocone.py` (call, digital); faltan lookback, Merton y asiática |
| 14 | Esperanzas condicionales (T. 14.1), americanas, Alòs, skew en tiempo corto | ✅ parcial | 10 | `conditional.py`, ej. 08; faltan Alòs, Hull–White y el skew rough Bergomi |
| 15–17 | EDPEs: Walsh–Dalang, densidades, modelo parabólico de Anderson | 📖 | — | — |
| 18 | Browniano fraccionario, volatilidad rugosa | 🔜 | — | conecta con §14.4 (rough Bergomi) |
| 19 | Malliavin en el espacio de Poisson | 📖 | — | — |
| 20 | Malliavin–Stein, teorema del cuarto momento | 🔜 | — | ej.: TCL de la variación cuadrática del fBm (§20.4) |
| 21–23 | Rough paths, estructuras de regularidad, fronteras | 📖 | — | — |
| A | Formulario | ✅ | — | ver `docs/teoria_resumen.md` |
| B | Notación | ✅ | 01 | ver la tabla de abajo |

## Diferencias de notación

| Guía (PDF) | Código / LaTeX compañero | Comentario |
|---|---|---|
| H_n (Hermite probabilístico) | `hermite_e`, H_n en LaTeX | NumPy lo llama `hermite_e` (He_n); es el mismo polinomio |
| A = ∫₀ᵀ S_t dt (asiática) | A = (1/T)∫₀ᵀ S_t dt | Fórmulas del peso equivalentes |
| ϕ_t (acciones en cartera) | `delta` en los ejemplos; `integrand_*` devuelve E[D_tF\|F_t] = ϕ_t σ S̃_t | |
| W̃ (browniano bajo Q) | `W` | El código trabaja siempre bajo la medida neutral al riesgo |

## Próximos módulos propuestos (por orden de valor para finanzas)

1. **Alòs / Hull–White y skew** (§14.3–14.4, 18.5): Heston y rough Bergomi por Monte Carlo y pendiente ATM frente a T − t.
2. **Cobertura lookback y asiática** (Ejemplos 13.4–13.5).
3. **Merton con coeficientes aleatorios** (T. 13.6): demanda de cobertura intertemporal.
4. **Ornstein–Uhlenbeck / Mehler / Poincaré** (cap. 9) y **Nourdin–Viens** (§10.5).
5. **Malliavin–Stein**: cuarto momento y TCL para la variación cuadrática del fBm (cap. 20).
