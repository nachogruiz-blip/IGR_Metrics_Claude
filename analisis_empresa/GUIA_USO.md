# Guía de uso del analizador de empresas

Esta guía explica cómo usar la herramienta y, sobre todo, **cómo leer lo que dice**. Las
fórmulas y los umbrales exactos están en [`METODOLOGIA.md`](METODOLOGIA.md).

> Herramienta de apoyo al análisis, no asesoramiento financiero. Resume la evidencia de forma
> ordenada; no predice el futuro. Los umbrales son heurísticos y no se han calibrado con datos
> históricos.

## 1. Instalación

Requiere Python ≥ 3.10.

```bash
pip install -r analisis_empresa/requirements.txt
```

Dependencias: `streamlit`, `plotly`, `yfinance`, `pandas`, `numpy`, `scipy`. Los datos vienen de
Yahoo Finance: hace falta conexión a internet (salvo en modo demo).

## 2. Elegir el ticker

Se usa el formato de Yahoo Finance: el código de la acción y un sufijo que indica la bolsa.

| Mercado | Sufijo | Ejemplos | Índice de referencia |
|---|---|---|---|
| Madrid (BME) | `.MC` | `SAN.MC`, `ITX.MC`, `IBE.MC`, `BBVA.MC`, `TEF.MC` | IBEX 35 |
| Ámsterdam | `.AS` | `ASML.AS`, `INGA.AS` | AEX |
| París | `.PA` | `MC.PA`, `TTE.PA` | CAC 40 |
| Fráncfort / Xetra | `.DE` | `SAP.DE`, `SIE.DE` | DAX |
| Milán | `.MI` | `ENEL.MI`, `ISP.MI` | FTSE MIB |
| Londres | `.L` | `SHEL.L`, `AZN.L` | FTSE 100 |
| Suiza | `.SW` | `NESN.SW` | SMI |
| Lisboa | `.LS` | `EDP.LS` | PSI |
| EE. UU. | (ninguno) | `AAPL`, `MSFT`, `NVDA`, `JPM` | S&P 500 |
| Materias primas (futuros) | `=F` | `GC=F` oro, `SI=F` plata, `CL=F` petróleo WTI, `HG=F` cobre | S&P 500 |
| Divisas | `=X` | `EURUSD=X`, `XAUUSD=X` (oro al contado) | S&P 500 |

Si no sabes el ticker, búscalo en finance.yahoo.com: es el código que aparece entre paréntesis
junto al nombre.

## 3. Formas de usarlo

### App web (recomendada)

```bash
streamlit run analisis_empresa/app.py
```

Se abre en el navegador. En la barra lateral:

- **Ticker**: la empresa a analizar.
- **Años de historia de precios** (2–10, por defecto 5): más años dan estadísticas de
  volatilidad y caídas más estables; menos años las hacen más representativas del momento actual.
- **Tipo libre de riesgo**: 0 = automático (bono de EE. UU. a 10 años descargado para valores en
  dólares; 2.7 % para el euro, 4.5 % para la libra, 0.7 % para el franco). Puedes fijarlo a mano;
  afecta al coste de capital y por tanto a la valoración DCF.
- **Datos sintéticos (demo)**: empresas inventadas para probar sin conexión.

Los datos descargados se guardan en caché una hora.

### Línea de comandos (informe Markdown)

```bash
cd analisis_empresa
python -m analyst ITX.MC                      # informe en la consola
python -m analyst SAN.MC --out informe.md     # guardado en un archivo
python -m analyst AAPL --rf 0.043 --years 10  # tipo sin riesgo y años de historia
python -m analyst DEMO-ESPERA --demo          # sin conexión
```

El informe es el mismo que se descarga desde la pestaña **Informe** de la app.

### Desde Python

```python
from analyst import core, data, report

a = core.analyze(data.fetch("ITX.MC"))     # o data.demo("DEMO-COMPRA")
a.verdict.action, a.verdict.headline, a.verdict.wait_for, a.verdict.levels
a.valuation.fair_value, a.timeseries.stats["garch_vol_1m"]
print(report.to_markdown(a))
```

(Ejecutar desde `analisis_empresa/` o añadir esa carpeta al `PYTHONPATH`.)

## 4. Cómo leer el resultado

### 4.1 El veredicto

| Veredicto | Significa | Qué hacer |
|---|---|---|
| ▲ **COMPRAR** | Empresa atractiva por fundamentales y precio que acompaña (o tendencia muy fuerte con fundamentales neutros: compra táctica). | Entrar; si el técnico es neutro, de forma escalonada. Respetar el stop. |
| ⏸ **ESPERAR** | Hay una tesis (normalmente de compra) pero algo aconseja no entrar todavía. | Mirar **«Qué esperar / disparadores»**: dice exactamente a qué esperar. |
| ● **MANTENER** | Sin ventaja clara en ningún sentido. | Si la tienes, mantener; si no, no hay prisa. Vigilar la ruptura de soporte o resistencia. |
| ▼ **VENDER** | Fundamentales débiles o caros y/o tendencia bajista clara. | Salir o reducir. Si está en sobreventa, mejor vender escalonado en los rebotes. |

La **intención de fondo** («compra», «venta», «neutral») aclara un ESPERAR: «ESPERAR · intención
compra» quiere decir «la quiero comprar, pero no ahora».

Motivos habituales de **ESPERAR**:

- **Buena empresa en tendencia bajista**: esperar a que el precio recupere la media de 50
  sesiones y el MACD gire, o entrar parcialmente en el soporte si hay sobreventa.
- **Resultados en 14 días o menos**: pueden mover el precio un 5–15 %. Esperar a publicarlos o
  entrar con media posición.
- **Precio sobreextendido** (RSI ≥ 70, por encima de Bollinger o a más de 2.5 ATR de su media de
  20): esperar un retroceso hacia la zona de entrada indicada.
- **Balance con riesgo de insolvencia**: no se compra aunque todo lo demás sea favorable, hasta
  que mejore la solvencia.

La **convicción** (alta / media / baja) mide la fuerza de la señal y si fundamentales y técnico
coinciden. Baja también si la volatilidad está en máximos. Úsala para el tamaño de la posición.

### 4.2 Las puntuaciones

Cada indicador se puntúa entre **−1 (desfavorable)** y **+1 (favorable)**; 0 es neutro. Los
bloques son medias ponderadas y se combinan así:

- **Calidad** = balance y solvencia + rentabilidad y crecimiento.
- **Atractivo fundamental** = calidad + valoración. *¿Es una buena empresa a buen precio?*
  Horizonte de años.
- **Momento técnico** = bloque técnico. *¿Acompaña el precio?* Horizonte de semanas o meses.
- **Riesgo** = bloque de series temporales. No da dirección: modula la convicción.
- **Compuesta** = resumen de todo (sólo informativa; el veredicto sale de la matriz de
  atractivo × momento descrita en la metodología).

Orientación: por encima de +0.25 es claramente favorable; por debajo de −0.25, claramente
desfavorable; entre medias, neutro.

En cada tabla, **«cobertura»** indica qué parte de los indicadores tenía dato. Una cobertura baja
(empresas recién cotizadas, filiales, datos incompletos en Yahoo) hace el bloque menos fiable.

### 4.3 Los niveles

| Nivel | Uso |
|---|---|
| Stop orientativo | Precio en el que la tesis deja de ser válida. Bajo el soporte (−0.5 ATR) o, si el soporte queda lejos, 2.5 ATR bajo el precio. |
| Distancia al stop | Lo que se perdería si salta. Ayuda a dimensionar: con un riesgo máximo del 1 % de la cartera y un stop al −8 %, la posición sería ~12.5 % de la cartera. |
| Zona de entrada | En ESPERAR por sobreextensión: dónde comprar si el precio retrocede. |
| Nivel de confirmación | En ESPERAR por tendencia bajista: el precio que debe recuperar. |
| Objetivos | Resistencia, valor estimado y objetivo de analistas por encima del precio, de menor a mayor. |
| Invalidación | En VENDER: si el precio supera este nivel con fuerza, la tesis bajista falla. |

### 4.4 Pestañas de la app

- **Balance y cuentas**: evolución de ventas, beneficio y flujo de caja libre; márgenes, ROE y
  ROIC; tabla de ratios por ejercicio; F-score de Piotroski prueba a prueba. Fíjate en las
  **tendencias** (¿mejora o empeora el margen? ¿sube la deuda?) más que en un año suelto.
- **Valoración**: valor intrínseco estimado y supuestos (crecimiento, WACC), tabla de
  sensibilidad y **DCF inverso**. Si el DCF inverso dice que el precio descuenta un 12 % de
  crecimiento y la empresa ha crecido históricamente un 4 %, el mercado es muy optimista. El DCF
  es **muy sensible** a sus supuestos: mira la tabla de sensibilidad antes de fiarte del número.
- **Técnico**: velas con medias de 50 y 200 sesiones, bandas de Bollinger y líneas de
  soporte/resistencia (con el número de veces que el precio ha girado ahí), RSI y MACD.
- **Series temporales**:
  - *Volatilidad*: la realizada, la EWMA y la GARCH. Si la actual está muy por encima de la
    línea de largo plazo, el mercado está nervioso con el valor; GARCH prevé cómo volverá a la
    normalidad (vida media de un choque).
  - *Distribución*: rendimientos diarios frente a una normal. Colas más anchas = días extremos
    más frecuentes de lo que sugiere la volatilidad.
  - *VaR 95 %*: pérdida diaria que se supera uno de cada veinte días; *CVaR*: pérdida media en
    esos días malos.
  - *Caída desde máximos*, *rentabilidad por año* y *estacionalidad* (esta última con sólo unas
    pocas observaciones por mes: es una curiosidad, no una señal).
  - *Rango de precio estimado*: entre qué precios estará la acción a 1 y 3 meses con un 68 %
    (16–84 %) y un 90 % (5–95 %) de probabilidad según la volatilidad prevista, sin suponer
    tendencia.
  - *Estadísticos*: Ljung-Box (¿son predecibles los rendimientos?), ratio de varianzas y Hurst
    (¿tendencia o reversión a la media?), β frente al índice.
- **Informe**: todo lo anterior en Markdown, descargable.
- **Metodología**: fórmulas, umbrales y esta guía.

## 5. Oro, materias primas y divisas

```bash
python -m analyst GC=F         # oro, futuro continuo de COMEX (el más fiable en Yahoo)
python -m analyst XAUUSD=X     # oro al contado (a veces Yahoo no tiene datos o volumen)
```

En la app basta con escribir el ticker. Un ETF de oro (`GLD`, `SGLD.L`, `4GLD.DE`) se analiza
como una acción sin cuentas; para el análisis macro usa `GC=F`.

Qué cambia frente a una acción:

- No hay pestañas de **Balance** ni **Valoración**: el oro no tiene beneficios ni flujos de caja.
  En su lugar aparece **Factores macro**.
- **Factores macro**: para cada factor (dólar, tipos a 10 años, bonos ligados a la inflación,
  S&P 500, VIX) se muestra cuánto se ha movido en 3 meses, la sensibilidad del oro (β) y la
  correlación de los últimos 2 años, y el **efecto implícito** (β × movimiento): positivo = el
  factor ha empujado al alza. Ejemplo: si el dólar ha caído un 6 % y la β del oro al dólar es
  −0.4, el efecto implícito es +2.4 %: viento a favor.
- **Relación inusual (⚠)**: la relación de los datos va contra la teoría (p. ej. oro y dólar
  subiendo juntos). Ocurre en cambios de régimen; esa relación no debe extrapolarse.
- **Valor relativo**: extensión del precio frente a su media de 3 años (por encima de z = 2 el
  oro está muy estirado y puntúa en contra) y ratio oro/plata (alto = oro caro frente a la plata).
- **Veredicto**: el eje «Factores macro» sustituye al atractivo fundamental. Con factores
  neutros, sólo una tendencia muy fuerte da COMPRAR o VENDER (táctico); si no, MANTENER. No hay
  aviso de resultados ni veto de solvencia. El objetivo de referencia es el extremo superior del
  rango de precio a 3 meses (no hay objetivo de analistas).
- **β frente al S&P 500** (pestaña Series temporales): en el oro suele ser cercana a 0 o
  negativa; si sube, el oro está cotizando como un activo de riesgo más que como refugio.

## 6. Ejemplos

La carpeta [`ejemplos/`](ejemplos/) contiene los informes completos de las cuatro empresas
sintéticas del modo demo, una por cada situación típica:

| Perfil | Situación | Veredicto |
|---|---|---|
| [`DEMO-COMPRA`](ejemplos/DEMO-COMPRA.md) | Buen balance, rentable, barata y en tendencia alcista | ▲ COMPRAR (convicción alta) |
| [`DEMO-ESPERA`](ejemplos/DEMO-ESPERA.md) | Buena empresa barata, pero el precio cae (cruce bajista de medias) | ⏸ ESPERAR a que recupere la media de 50 o a un soporte con sobreventa |
| [`DEMO-VENDE`](ejemplos/DEMO-VENDE.md) | Pérdidas, deuda neta/EBITDA > 13×, Z de Altman en zona de riesgo, tendencia bajista | ▼ VENDER (convicción alta) |
| [`DEMO-CARA`](ejemplos/DEMO-CARA.md) | Empresa sana pero cara (PER 38×), tendencia alcista y resultados en 9 días | ⏸ ESPERAR a los resultados |
| [`DEMO-ORO`](ejemplos/DEMO-ORO.md) | Oro en tendencia alcista; dólar y tipos bajando (a favor) pero precio muy estirado frente a su media de 3 años | ▲ COMPRAR táctico (convicción baja) |

Para regenerarlos tras cambiar el modelo:

```bash
cd analisis_empresa
for t in DEMO-COMPRA DEMO-ESPERA DEMO-VENDE DEMO-CARA DEMO-ORO; do python -m analyst $t --demo --out ejemplos/$t.md; done
```

## 7. Casos especiales

- **Bancos y aseguradoras** (sector *Financial Services*): no se calculan liquidez,
  deuda/EBITDA ni Z de Altman (la deuda es su negocio), ni DCF. La valoración usa el **P/VC
  justificado** = (ROE − g)/(kₑ − g): un banco con ROE del 12 % y coste de capital del 10 % «vale»
  algo más que su valor contable.
- **Empresas con pérdidas**: el PER no tiene sentido y puntúa −1; sin flujo de caja libre
  positivo no hay DCF y la valoración se apoya en VE/EBITDA, múltiplos y analistas.
- **Pocos analistas** (menos de 3): el consenso se muestra pero no puntúa.
- **Sin estados financieros** (ETF, índices, algunas filiales): sólo se analizan técnico y series
  temporales; el veredicto se apoya entonces casi solo en el precio.

## 8. Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| «Sin precios para X» | Ticker mal escrito o sin sufijo de bolsa | Comprobar en finance.yahoo.com (`ITX.MC`, no `ITX`). |
| Bloques con cobertura baja o «—» | Yahoo no da esa partida para el valor | Normal en algunos valores; el resto de pesos se reparte. |
| Aviso «No se pudo obtener…» | Yahoo limita peticiones o cambió un formato | Reintentar en unos minutos; si persiste, actualizar `yfinance`. |
| Valoración muy extrema (±100 %) | Flujo de caja de un año atípico o supuestos que no encajan | Revisar la tabla de sensibilidad y los ratios por ejercicio; no fiarse sólo del DCF. |
| Oro: «Sin precios para XAUUSD=X» | Yahoo no siempre sirve el contado | Usar `GC=F`. |
| Falta algún factor macro | Yahoo no devolvió esa serie (aviso «No se pudo obtener el factor…») | El pilar se calcula con el resto; reintentar más tarde. |
| Fecha de resultados ausente | Yahoo no la publica para ese valor | Consultarla en la web de relación con inversores de la empresa. |

## 9. Limitaciones

- Datos anuales de los últimos ~4 ejercicios (lo que da Yahoo), no trimestrales.
- No compara los múltiplos con los de su sector (el `dashboard/` del repositorio sí lo hace).
- No tiene en cuenta noticias, regulación, calidad del equipo directivo ni ventajas
  competitivas: lo cuantitativo es sólo una parte del análisis.
- Sin backtest del veredicto.
- En materias primas no se modelan inventarios, curva de futuros (contango/backwardation) ni el
  posicionamiento de los especuladores.
