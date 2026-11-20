# Metodología

El analizador estudia **una** empresa desde cinco ángulos, puntúa cada indicador en
[−1, +1] (+1 = favorable para comprar) y combina los bloques en un veredicto:
**COMPRAR**, **ESPERAR**, **MANTENER** o **VENDER**, con lo que hay que esperar (si aplica) y
niveles orientativos de entrada, stop y objetivos.

> Herramienta de apoyo al análisis, no asesoramiento financiero. Los umbrales son heurísticos
> (literatura académica y práctica habitual), no están optimizados con datos.

## 1. Balance y solvencia

| Indicador | Lectura | Puntúa +1 | Puntúa −1 |
|---|---|---|---|
| Deuda neta / EBITDA | años de EBITDA para pagar la deuda neta | ≤ 0.5× o caja neta | ≥ 4.5× |
| Cobertura de intereses | EBIT / gastos financieros | ≥ 15× | ≤ 1× |
| Liquidez | activo corriente / pasivo corriente | ≥ 2.5 | ≤ 0.6 |
| Z de Altman (1968) | 1.2·CC/A + 1.4·BR/A + 3.3·EBIT/A + 0.6·Cap/Pasivo + 1.0·Ventas/A | ≥ 4.5 (zona segura > 2.99) | ≤ 1.2 (riesgo < 1.81) |
| Patrimonio / activo | colchón de capital propio | ≥ 50 % | ≤ 10 % |
| F-score de Piotroski (2000) | 9 pruebas binarias de rentabilidad, apalancamiento y eficiencia | 8 | 2 |
| Flujo operativo / beneficio | calidad del beneficio (¿se convierte en caja?) | ≥ 1.3 | ≤ 0.5 |

**Bancos y aseguradoras**: la deuda es su materia prima, así que se omiten liquidez,
deuda/EBITDA, Altman y calidad del beneficio, y se usan ROE, ROA y patrimonio/activo.

## 2. Rentabilidad y crecimiento

ROE, ROIC (EBIT·(1−t) / (patrimonio + deuda − caja), sobre saldos medios), margen EBIT, margen
de flujo de caja libre, tendencia del margen neto, crecimiento anual compuesto de ventas y
beneficio y variación del número de acciones (recompras +, dilución −). En financieras, ROA en
lugar de ROIC y márgenes.

## 3. Valoración

- **Coste de capital**: kₑ = r_f + β·5.5 % (CAPM; β de Yahoo o estimado con rendimientos
  semanales, acotado a [0.5, 2]); WACC con k_d = intereses/deuda y tipo impositivo 25 %.
- **DCF en dos etapas** (no financieras): FCF base = media de los últimos 3 ejercicios;
  crecimiento g₁ = TACC histórico de ventas acotado a [−3 %, 12 %] durante 5 años, convergencia
  lineal en otros 5 hasta g_T (2 % en euros, 2.5 % en dólares, nunca por encima de r_f) y valor
  terminal de Gordon. Valor por acción = (VE − deuda neta) / acciones. Se muestra una tabla de
  **sensibilidad** (tasa ±1 pp, g_T ±0.5–1 pp).
- **DCF inverso**: el crecimiento g₁ que justifica el precio actual. Si es mucho mayor que el
  histórico, el mercado descuenta un escenario exigente.
- **Financieras**: P/VC justificado = (ROE − g)/(kₑ − g).
- **Múltiplos**: PER (actual y estimado), rentabilidad por beneficio menos el bono, VE/EBITDA,
  rentabilidad por FCF, PEG, P/VC (banca), rentabilidad por dividendo (penaliza > 8 %:
  suele anticipar recortes) y consenso de analistas (potencial y recomendación media; sin peso
  si hay menos de 3 opiniones).

El margen de seguridad (valor/precio − 1) pesa 1.2 pero es **muy sensible a supuestos**: un
DCF nunca debe leerse solo.

## 4. Técnico

Tendencia (precio y media 50 frente a media 200, pendiente de la media 200), momentum
(12 meses saltando el último; 3 meses), fuerza relativa a 6 meses frente al índice del mercado
(IBEX, AEX, CAC, DAX, S&P 500… según el sufijo), MACD, RSI, volumen en subidas/bajadas y posición
en el rango de 52 semanas. Soportes y resistencias: pivotes de ±10 sesiones del último año
agrupados si distan menos de 1 ATR.

Avisos de *timing* (no puntúan, pero cambian el veredicto): RSI ≥ 70 / ≤ 30, precio fuera de las
bandas de Bollinger, extensión > 2.5 ATR respecto a la media de 20, cruce dorado / de la muerte
en el último mes.

## 5. Series temporales: rendimientos y volatilidad

- Rentabilidad anual compuesta, volatilidad, Sharpe, Sortino, Calmar, caída máxima y actual.
- Distribución: asimetría, curtosis, Jarque-Bera; VaR/CVaR diarios histórico, normal y
  **Cornish-Fisher** (corrige por asimetría y colas).
- Dependencia: Ljung-Box sobre r (¿predecible?) y sobre r² (¿agrupamiento de volatilidad?),
  ratio de varianzas de Lo-MacKinlay y exponente de Hurst (tendencia vs reversión).
- Volatilidad: realizada 21/63 sesiones, EWMA (λ = 0.94) y **GARCH(1,1)** por máxima
  verosimilitud: persistencia α+β, vida media de los choques, volatilidad prevista a 1 y 3 meses
  y de largo plazo. Percentil de la volatilidad actual frente a su historia.
- β, correlación y α frente al índice con rendimientos semanales.
- Cono de precios a 1 y 3 meses (log-normal con la vol GARCH, sin deriva).

El pilar de riesgo puntúa Sharpe a 3 años, caída máxima a 3 años, volatilidad, régimen de
volatilidad, tendencia prevista de la volatilidad y VaR. Modula la convicción, no la dirección.

## 6. Veredicto

Ejes: **calidad** Q = 0.45·balance + 0.55·rentabilidad; **atractivo fundamental**
A = 0.5·Q + 0.5·valoración; **momento técnico** T = pilar técnico.

| | T ≥ +0.15 | intermedio | T ≤ −0.25 |
|---|---|---|---|
| **A ≥ +0.25** | COMPRAR | COMPRAR (escalonado) | ESPERAR a confirmación técnica (recuperar la media 50, giro del MACD o soporte con sobreventa) |
| **intermedio** | COMPRAR táctico si T ≥ 0.40; si no, MANTENER | MANTENER (esperar a ruptura de soporte/resistencia) | VENDER si T ≤ −0.40; si no, MANTENER |
| **A ≤ −0.25** | VENDER aprovechando la fortaleza | VENDER | VENDER |

Reglas que se superponen:

1. **Veto por solvencia**: Altman < 1.81, cobertura < 1.5× o deuda neta/EBITDA > 4.5× impiden
   COMPRAR (pasa a ESPERAR).
2. **Sobrecompra / extensión**: COMPRAR pasa a ESPERAR un retroceso hacia la media de 20 o el
   soporte.
3. **Resultados en ≤ 14 días**: COMPRAR pasa a ESPERAR (o entrar con media posición).
4. **Volatilidad en el percentil ≥ 90 % y al alza** (GARCH): baja la convicción; posiciones más
   pequeñas y stops más anchos.
5. Fecha ex-dividendo en ≤ 30 días: aviso.

Convicción: media de |A| y |T| si apuntan en el mismo sentido (alta ≥ 0.5, media ≥ 0.28), la
mitad de |A| si se contradicen.

Niveles: stop = soporte − 0.5 ATR si el soporte está a menos de 3 ATR, si no precio − 2.5 ATR;
objetivos = resistencia, valor estimado y precio objetivo de analistas por encima del precio;
en ventas, la resistencia es el nivel que invalidaría la tesis bajista.

## Limitaciones

- Yahoo Finance da 4 ejercicios anuales y a veces partidas incompletas o con nombres distintos
  (`data.ALIASES`); un indicador sin dato se omite y los pesos se renormalizan (se muestra la
  cobertura de cada bloque).
- No hay comparación con el sector (el dashboard `dashboard/` sí la tiene para los múltiplos).
- Umbrales heurísticos y sin backtest: el veredicto es un resumen ordenado de la evidencia, no
  una predicción.
