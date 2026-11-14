# Erratas y correcciones respecto al PDF original

Política: `latex/guia/` reproduce el contenido de `docs/pdf/Calculo_de_Malliavin_corregido.pdf`,
pero **corrige** las erratas y los errores que se detecten en el original (no se conservan).
Cada corrección se anota aquí.

| Ubicación | Original | Corregido | Tipo |
|---|---|---|---|
| Índice | El Prefacio no aparece en el índice | Añadido al índice | Presentación |
| §22.4, recuadro «Intuición» | «Este ganancia de regularidad» | «Esta ganancia de regularidad» | Errata |

## Comprobaciones realizadas (sin errores encontrados)

- Ortografía de todo el texto con `hunspell` (es_ES).
- Comparación palabra a palabra del texto extraído de ambos PDF (coincidencia del 98,4 %; el resto son
  cabeceras de página y guiones de partición).
- Verificación manual de las fórmulas: pesos de Malliavin de Black–Scholes (Prop. 12.2, incluida la doble
  integración por partes de la gamma), peso asiático (Prop. 12.5), Bismut–Elworthy–Li (T. 12.3),
  coberturas de Clark–Ocone (Ejemplos 13.2–13.5), Ocone–Karatzas (T. 13.6), Ejemplo 14.2,
  pendiente del Ejemplo 14.7 y límite del T. 14.6(a) (coincide con el skew de SABR, ρν/2),
  corchetes de Lie de los Ejemplos 11.6–11.8, condición de Dalang (T. 15.3), segundo momento y
  exponentes de Lyapunov del PAM (§17.1–17.2), fórmulas del cuarto cumulante (Lema 20.3) y tasas
  de Breuer–Major (T. 20.6), umbral H > 1/4 (§18.3, §21.2–21.3).
- Además, varias fórmulas están verificadas numéricamente por los tests de la librería (`tests/`).
