# AGENTS.md — dashboard de commodities

Proyecto **independiente** de la librería `malliavin` y del dashboard de acciones (`dashboard/`):
dependencias en `requirements.txt` y tests propios. Documentación en español; identificadores
en inglés.

## Mapa

| Archivo | Responsabilidad | No debe |
|---|---|---|
| `app.py` | Interfaz Streamlit: carga cacheada, tablas, gráficos | contener lógica de tramos |
| `commodash/strips.py` | `Strip` (meses de cada tramo), `prepare` (curvas), `strip_series`/`strip_stats`, `forward_curve`, `structure` | importar streamlit/yfinance |
| `commodash/contracts.py` | `CATALOG` de commodities y tickers de Yahoo | — |
| `commodash/data.py` | `fetch_panel` (Yahoo, import perezoso), `read_csv`, `demo_panel`, configuración | — |
| `METODOLOGIA.md` | Explicación para el usuario (pestaña Metodología) | — |

Flujo: panel (fechas × mes de entrega) → `strips.prepare` → `Curves` → `strip_stats` por tramo.

## Comandos (desde la raíz del repo)

```bash
pip install -r commodities/requirements.txt
pytest commodities/tests
COMMODASH_DEMO=1 streamlit run commodities/app.py
```

CI (`.github/workflows/ci.yml`, job «Tests del dashboard de commodities») ejecuta los tests y
arranca la app en modo demo con `streamlit.testing`.

## Invariantes (los tests los vigilan)

1. **El mes 0 nunca cuenta**, sea cual sea el día del mes (`test_month_zero_never_counts`).
2. Noviembre-2026: 1A = dic-26…nov-27, Cal A = {dic-26}; diciembre ⇒ Cal A vacío; enero ⇒
   Cal A = feb…dic.
3. El histórico vectorizado coincide punto a punto con el cálculo del día
   (`test_history_matches_pointwise_computation`).
4. Variaciones like-for-like: misma cesta de contratos en ambas fechas; la suma de
   log-variaciones diarias de la semana = log-variación semanal.
5. Nada de red en los tests: usar `data.demo_panel`.

## Recetas

**Añadir una commodity de Yahoo**: una línea en `contracts.CATALOG` (raíz, mercado, meses
cotizados, unidad, ponderación) y, para el modo demo, parámetros en `data._DEMO`. Comprobar que
`Commodity.ticker` da el ticker que usa Yahoo.

**Añadir un tramo** (p. ej. trimestres): nuevo `Strip` con su `include` (matriz fechas × meses)
y `months`; añadirlo a `STRIPS` y a la tabla de `METODOLOGIA.md`; test con el ejemplo de
noviembre.

**Cambiar la regla del mes 0** (p. ej. contar M0 hasta su vencimiento): está en
`Strip.include` y en la máscara `past` de `prepare`.

## Limitaciones conocidas

- Tickers de Yahoo por contrato **no verificados desde el contenedor de desarrollo** (sin acceso a
  Yahoo): revisar al primer uso que `CLF27.NYM`, `GCZ26.CMX`, `ZCH27.CBT`… devuelven datos.
- Yahoo puede no conservar contratos vencidos ⇒ el principio del histórico rolling puede tener
  poca cobertura.
- Electricidad: la ponderación correcta es por horas (pico/base); `days` es una aproximación
  para base load.
