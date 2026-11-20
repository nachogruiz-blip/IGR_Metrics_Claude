# Dashboard de seguimiento de acciones

App Streamlit que, para una lista de acciones, calcula indicadores **técnicos** (tendencia,
momentum, osciladores, volumen, riesgo) y **fundamentales** (valoración, calidad, crecimiento,
salud financiera, consenso de analistas), los agrega en una puntuación y da:

- una **recomendación actual** (Compra fuerte / Comprar / Mantener / Vender / Venta fuerte) con
  avisos de *timing*;
- una **perspectiva a 1–3 meses** (Alcista / Lateral / Bajista) con P(subida) y rango ±1σ a 1 y
  3 meses, y un stop orientativo (2×ATR).

Es independiente de la librería `malliavin` del repositorio y tiene sus propias dependencias.

## Uso

```bash
pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py                       # datos reales de Yahoo Finance
STOCKDASH_DEMO=1 streamlit run dashboard/app.py      # datos sintéticos, sin red
pytest dashboard/tests                               # tests (sin red)
```

La lista de valores se edita en la barra lateral («Guardar lista» escribe `watchlist.json`) o
directamente en `watchlist.json`. Los tickers siguen el formato de Yahoo: `AAPL`, `SAN.MC`
(Madrid), `ASML.AS` (Ámsterdam), `SAP.DE` (Fráncfort), `MC.PA` (París). El índice de referencia
para la fuerza relativa se elige por sufijo (`benchmarks` en `watchlist.json`).

## Pantallas

- **Panel**: tabla de la lista ordenada por puntuación, mapa técnico vs fundamental y avisos.
- **Ficha del valor**: señal, perspectiva y rangos; gráfico de precio con SMA50/200, Bollinger y
  cono de estimación a 3 meses, volumen, RSI y MACD; puntuación por bloques; qué indicadores
  empujan a favor y en contra; tablas de detalle con valor, puntuación y lectura de cada uno.
- **Metodología**: pesos, umbrales y limitaciones ([`METODOLOGIA.md`](METODOLOGIA.md)).

## Estructura

```
dashboard/
  app.py               Interfaz Streamlit
  stockdash/
    technical.py       SMA/EMA, RSI, MACD, Bollinger, ATR, ADX, OBV, volatilidad; snapshot()
    fundamental.py     Normaliza yfinance.info (fracciones, múltiplos, PER negativo, consenso)
    scoring.py         Catálogo de indicadores y umbrales, agregación, señal y perspectiva
    data.py            Descarga (yfinance, perezosa), watchlist, generador sintético para demo
  tests/               Identidades de indicadores y escenarios sintéticos (alcista, bajista, …)
  watchlist.json       Lista de seguimiento
```

Para ajustar el modelo, todos los umbrales y pesos están como datos en `stockdash/scoring.py`
(`TECHNICAL`, `FUNDAMENTAL`, `TECH_BLOCKS`, `FUND_BLOCKS`, `SIGNALS`, `KAPPA`).

> Herramienta de apoyo, no asesoramiento financiero. Los umbrales son heurísticos y no están
> validados con backtest.
