# Analizador de empresas cotizadas

Le das un ticker (mercado español, europeo o estadounidense) y analiza la **empresa** y la
**acción** para decir si es momento de **COMPRAR**, **VENDER**, **ESPERAR** (y a qué) o
**MANTENER**:

1. **Balance y solvencia**: deuda neta/EBITDA, cobertura de intereses, liquidez, Z de Altman,
   F-score de Piotroski, calidad del beneficio; tabla de ratios por ejercicio.
2. **Rentabilidad y crecimiento**: ROE, ROIC, márgenes, crecimiento de ventas y beneficio,
   recompras/dilución.
3. **Valoración**: DCF en dos etapas con WACC (CAPM), DCF inverso, tabla de sensibilidad,
   P/VC justificado (banca), PER, VE/EBITDA, rentabilidad por FCF y dividendo, consenso.
4. **Técnico**: medias 50/200 y cruces, momentum, fuerza relativa frente al índice, RSI, MACD,
   Bollinger, ADX, volumen, soportes y resistencias.
5. **Series temporales**: rentabilidad, volatilidad (realizada, EWMA, **GARCH(1,1)** con
   previsión), VaR/CVaR (histórico, normal, Cornish-Fisher), caídas, Sharpe/Sortino/Calmar,
   β frente al índice, Ljung-Box, ratio de varianzas, Hurst, estacionalidad y cono de precios.

El **veredicto** combina atractivo fundamental (¿buena empresa a buen precio?) y momento técnico
(¿acompaña el precio?), y aplica reglas de *timing*: resultados inminentes, sobrecompra,
solvencia y régimen de volatilidad. Da los disparadores a vigilar y niveles de entrada, stop y
objetivos. Detalle en [`METODOLOGIA.md`](METODOLOGIA.md).

Es independiente de la librería `malliavin` y del dashboard `dashboard/` del repositorio.

## Uso

```bash
pip install -r analisis_empresa/requirements.txt

# App web
streamlit run analisis_empresa/app.py                    # datos reales (Yahoo Finance)
ANALYST_DEMO=1 streamlit run analisis_empresa/app.py     # empresas sintéticas, sin red

# Línea de comandos (informe Markdown)
cd analisis_empresa
python -m analyst ITX.MC                                 # a la consola
python -m analyst SAN.MC --out informe_san.md            # a un archivo
python -m analyst AAPL --rf 0.043                        # fijando el tipo libre de riesgo
python -m analyst DEMO-ESPERA --demo                     # sin red

pytest analisis_empresa/tests                            # tests (sin red, ~3 s)
```

Tickers con el formato de Yahoo: `SAN.MC`, `ITX.MC`, `IBE.MC` (Madrid), `ASML.AS` (Ámsterdam),
`SAP.DE` (Fráncfort), `MC.PA` (París), `ENEL.MI` (Milán), `AAPL`, `MSFT` (EE. UU.). El índice de
referencia se elige por sufijo (`data.BENCHMARKS`). Perfiles demo: `DEMO-COMPRA`, `DEMO-ESPERA`,
`DEMO-VENDE`, `DEMO-CARA`.

## Pantallas de la app

- **Cabecera**: veredicto con convicción, puntuación de cada eje, disparadores y avisos, razones
  a favor y en contra, niveles.
- **Balance y cuentas**: ventas, beneficio y FCF por año; márgenes y rentabilidad; ratios por
  ejercicio; Piotroski; tablas de puntuación.
- **Valoración**: valor estimado, supuestos, sensibilidad, precio frente a referencias.
- **Técnico**: velas con medias, Bollinger y soportes/resistencias; RSI; MACD.
- **Series temporales**: volatilidad realizada/EWMA/GARCH, distribución de rendimientos frente a
  la normal, caídas, rentabilidad anual, estacionalidad, cono y estadísticos.
- **Informe**: el mismo informe que la CLI, descargable en Markdown.

## Estructura

```
analisis_empresa/
  app.py                 Interfaz Streamlit
  analyst/
    data.py              Descarga (yfinance, perezosa), normalización de estados, demo
    statements.py        Ratios, Piotroski, Altman, pilares de balance y rentabilidad
    valuation.py         CAPM/WACC, DCF, DCF inverso, P/VC justificado, múltiplos
    technical.py         Indicadores, soportes/resistencias, cruces, pilar técnico
    timeseries.py        Estadísticos, Ljung-Box, VR, Hurst, EWMA, GARCH, VaR, β
    verdict.py           Matriz de decisión y reglas de timing → Verdict
    core.py              CompanyData → Analysis
    report.py            Informe Markdown
    __main__.py          CLI
  tests/                 Identidades y valores cerrados, escenarios demo, CLI
  METODOLOGIA.md         Explicación de indicadores, umbrales y veredicto
  AGENTS.md              Guía para agentes que modifiquen el proyecto
```

> Herramienta de apoyo, no asesoramiento financiero. Umbrales heurísticos sin backtest; los
> datos de Yahoo pueden tener errores, huecos o retrasos.
