# Dashboard de seguimiento de commodities

App Streamlit que sigue commodities **por tramos de la curva de futuros**:

- **1A, 2A y 3A rolling**: próximos 12, 24 y 36 meses de entrega;
- **años de calendario A (en curso), A+1 y A+2**.

El **mes 0 (mes en curso) nunca cuenta**: en noviembre el primer mes es diciembre; Cal A es el
resto del año a partir de M+1 (en diciembre queda vacío). Detalles en
[`METODOLOGIA.md`](METODOLOGIA.md).

Es independiente de la librería `malliavin` y del dashboard de acciones; tiene sus propias
dependencias.

## Uso

```bash
pip install -r commodities/requirements.txt
streamlit run commodities/app.py                        # datos de Yahoo Finance
COMMODASH_DEMO=1 streamlit run commodities/app.py       # curvas sintéticas, sin red
pytest commodities/tests                                # tests (sin red)
```

La selección por defecto está en `commodities.json` («Guardar selección» en la barra lateral).
Curvas que no están en Yahoo (TTF, electricidad, CO2…) se cargan con un CSV
`fecha, commodity, entrega, precio`.

## Pantallas

- **Panel**: precio de cada tramo por commodity (más M+1 y estructura contango/backwardation) y
  variación like-for-like a 1D / 1S / 1M / 3M con avisos de cobertura.
- **Ficha**: precio y variación mensual de cada tramo; curva de futuros de hoy, hace una semana
  y hace un mes con los años de calendario superpuestos; histórico de los tramos rolling y de
  calendario; tabla con variaciones, volatilidad, rango de 52 semanas y cobertura; descarga CSV.
- **Metodología**.

## Estructura

```
commodities/
  app.py               Interfaz Streamlit
  commodash/
    contracts.py       Catálogo (Yahoo: raíz, mercado, meses cotizados, ponderación)
    strips.py          Definición de tramos, curvas preparadas, precio y estadísticas
    data.py            Yahoo contrato a contrato, CSV propio y generador demo
  tests/               Tramos (mes 0, dic/ene), medias, interpolación, histórico y datos
  commodities.json     Selección por defecto
  AGENTS.md            Guía para agentes que modifiquen el dashboard
```
