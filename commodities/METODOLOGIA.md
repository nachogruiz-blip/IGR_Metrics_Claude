## Metodología

### Tramos

El **mes 0** es el mes en curso y **nunca cuenta**: si estamos en noviembre, el primer mes es
el de entrega en diciembre (M+1).

| Tramo | Meses (ejemplo a 20-nov-2026) | Qué es |
|---|---|---|
| 1A rolling | M+1 … M+12 (dic-26 – nov-27) | Próximos 12 meses; se renueva cada mes |
| 2A rolling | M+1 … M+24 (dic-26 – nov-28) | Próximos 24 meses |
| 3A rolling | M+1 … M+36 (dic-26 – nov-29) | Próximos 36 meses |
| Cal A | meses del año en curso posteriores a M0 (dic-26) | Resto del año; vacío en diciembre |
| Cal A+1 | ene – dic del año siguiente (2027) | Año de calendario completo |
| Cal A+2 | ene – dic del año siguiente al siguiente (2028) | Año de calendario completo |

Los tramos rolling son **acumulados** (2A incluye el 1A). Los años de calendario son productos
fijos: su histórico es el de ese mismo año (Cal-27 a lo largo del tiempo), siempre sin el mes 0
de cada día; por eso Cal A va perdiendo meses según avanza el año.

### Precio del tramo

Media de los precios de los meses del tramo:

- **Media simple** (petróleo, metales, agrícolas).
- **Por días de entrega** (gas natural; también recomendable para TTF y electricidad, que llegan
  por CSV). Se puede forzar una u otra en la barra lateral.

Cada contrato usa su último cierre (*settlement*). Si un contrato ya ha vencido pero su mes de
entrega todavía cuenta (el WTI de diciembre vence a mediados de noviembre), se usa su
liquidación final.

Meses sin contrato propio (el oro cotiza meses pares; maíz y trigo, mar/may/jul/sep/dic): se
interpolan linealmente entre los vencimientos vecinos. En los extremos de la curva se extrapola
plano como máximo 3 meses; si falta más, el tramo queda sin precio. La **cobertura** es la
fracción del tramo (ponderada) con cotización propia sobre los meses que deberían cotizar; por
debajo del 80 % se avisa en el panel.

### Variaciones, volatilidad y rango

- **Variación like-for-like** (1D, 1S, 1M, 3M): precio actual del tramo frente al precio de
  **los mismos contratos** hace 1, 5, 21 y 63 sesiones. Así un roll de mes no aparece como
  movimiento de mercado.
- **Serie histórica** de los rolling: el tramo como se veía cada día (cambia de contratos el
  primer día hábil de cada mes; los saltos de esa fecha son *roll*, no mercado).
- **Volatilidad 1M / 3M**: desviación típica anualizada (√252) de las log-variaciones diarias
  like-for-like de las últimas 21 / 63 sesiones.
- **Rango 52 semanas** y **posición en rango** (0 % = mínimo, 100 % = máximo), sobre la serie
  histórica del tramo.
- **Estructura 12m**: pendiente M+12 / M+1 − 1. *Contango* si > +1 %, *backwardation* si
  < −1 %, plana en medio.

### Datos

- **Yahoo Finance**, contrato a contrato (`CLF27.NYM`, `GCZ26.CMX`, `ZCH27.CBT`…). Cierres con
  retraso; los vencimientos lejanos pueden faltar o tener poca liquidez (ver cobertura). Yahoo
  no siempre conserva el histórico de contratos vencidos, así que el histórico más antiguo de
  los rolling puede tener menos cobertura.
- **CSV propio** para curvas que Yahoo no tiene contrato a contrato (TTF, electricidad OMIP/EEX,
  CO2…): columnas `fecha, commodity, entrega, precio` (entrega `AAAA-MM`; separador `,` o `;`).
- **Modo demo**: curvas sintéticas de un modelo de dos factores (shock corto que se disipa a lo
  largo de la curva + nivel largo), con carry y estacionalidad, para probar sin red.
