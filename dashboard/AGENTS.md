# AGENTS.md — dashboard de acciones

Guía para agentes de IA (y personas) que vayan a modificar `dashboard/`. Es un proyecto
**independiente** de la librería `malliavin` del repositorio: tiene sus propias dependencias
(`requirements.txt`) y sus propios tests. Documentación en español; identificadores en inglés.

## Mapa

| Archivo | Responsabilidad | No debe |
|---|---|---|
| `app.py` | Interfaz Streamlit: carga (cacheada), tablas, gráficos | contener lógica de cálculo o umbrales |
| `stockdash/technical.py` | Indicadores (`indicator_frame`) y variables de la señal (`features`, causal; `snapshot` = última fila) | mirar al futuro (ver test de causalidad) |
| `stockdash/fundamental.py` | Normaliza `yfinance.info` a fracciones y múltiplos | puntuar |
| `stockdash/sectors.py` | Medianas de múltiplos por sector y puntuación relativa | — |
| `stockdash/scoring.py` | Catálogo de indicadores (umbrales, pesos), agregación, señal, perspectiva, rangos | importar streamlit/yfinance |
| `stockdash/data.py` | Descarga (yfinance, import perezoso), watchlist, datos demo | — |
| `stockdash/backtest.py` | Backtest replicable + CLI `python -m stockdash.backtest` | duplicar la lógica de `scoring` |
| `METODOLOGIA.md` | Explicación para el usuario (se muestra en la pestaña Metodología) | — |
| `backtest/README.md` | Cómo ejecutar, reproducir y leer el backtest | — |
| `backtest/datos/`, `backtest/resultados/` | Precios guardados e informes generados | editarse a mano |

Flujo: `data` → `technical.features`/`snapshot` + `fundamental.extract` → `scoring.assess`
→ `Assessment` (lo que pinta `app.py` y lo que evalúa `backtest.py`).

## Comandos (desde `dashboard/`)

```bash
pip install -r requirements.txt
pytest tests                                   # < 10 s, sin red; deben pasar siempre
STOCKDASH_DEMO=1 streamlit run app.py          # app sin red
streamlit run app.py                           # app con Yahoo Finance
python -m stockdash.backtest --demo            # backtest sintético (regenera resultados/demo)
python -m stockdash.backtest --name watchlist  # backtest real (necesita red)
python -m stockdash.backtest --name watchlist --offline   # reproducir con datos guardados
```

CI (`.github/workflows/ci.yml`, job «Tests del dashboard») ejecuta los tests y arranca la app
en modo demo con `streamlit.testing`.

## Invariantes (los tests los vigilan)

1. **Puntuaciones en [−1, 1]**, +1 = favorable. Los indicadores sin dato (NaN) se omiten y los
   pesos se renormalizan dentro del bloque y entre bloques.
2. **Suma de aportaciones = puntuación compuesta** (`test_contributions_sum_to_composite`).
3. **Causalidad**: `features(df).iloc[i] == snapshot(df.iloc[:i+1])` (`test_features_are_causal`).
   Cualquier variable nueva debe calcularse con ventanas/`shift` hacia atrás.
4. **Valoración relativa al sector** para `pe_forward`, `pe_trailing`, `ev_ebitda`, `ps`, `pb`
   (`sectors.RELATIVE_KEYS`); `None` en `SECTOR_MULTIPLES` = el múltiplo no aplica y se excluye
   (también de la cobertura).
5. **Escenarios sintéticos**: tendencia alcista ⇒ compra y «Alcista»; bajista ⇒ venta y
   «Bajista»; lateral ⇒ «Mantener»/«Lateral» (`test_regimes_are_recognised`).
6. **Reproducibilidad del backtest**: misma entrada ⇒ mismos `observaciones.csv` y métricas.

## Recetas

**Añadir un indicador técnico**
1. Calcular su serie en `technical.features` (causal) — `snapshot` lo hereda.
2. Añadir un `Indicator(key, etiqueta, bloque, peso, función, formato, ayuda)` a
   `scoring.TECHNICAL`. Funciones disponibles: `ramp(lo, hi)` (lineal, invertible),
   `piecewise(xs, ys)`, `positive_multiple(lo, hi)`.
3. Test con valor cerrado o identidad en `tests/test_technical.py`.
4. Correr `pytest tests` y el backtest; actualizar la tabla de `METODOLOGIA.md`.

**Añadir un indicador fundamental**: extraerlo en `fundamental.extract` (en fracciones), añadir
su `Indicator` a `scoring.FUNDAMENTAL`, test en `test_scoring.py`, y `METODOLOGIA.md`.
Si es un múltiplo que depende del sector, añadir su clave a cada fila de
`sectors.SECTOR_MULTIPLES` y a `DEFAULT_MULTIPLES`.

**Actualizar las medianas sectoriales**: editar `sectors.SECTOR_MULTIPLES` (claves de sector
de Yahoo, en inglés). Indicar fuente y fecha en el docstring del módulo y en el historial de
abajo. `SPREAD` controla cuánto hay que desviarse de la mediana para puntuar ±1.

**Cambiar pesos, umbrales de señal o perspectiva**: `TECH_BLOCKS`, `FUND_BLOCKS`, `SIGNALS`,
`OUTLOOK_THRESHOLD`, `KAPPA` en `scoring.py`. Validar con el backtest siguiendo «Recalibrar sin
engañarse» en `backtest/README.md` (ajuste y validación en periodos separados).

**Cambiar la watchlist por defecto o los índices**: `watchlist.json` (`benchmarks` se asigna
por sufijo de ticker; `default` para el resto).

## Convenciones

- Fracciones, no porcentajes, en todo el cálculo (0.15 = 15 %); el formato es cosa de `app.py`.
- Paleta de gráficos: azul `#2a78d6`, naranja `#eb6834`, aqua `#1baf7a` en ese orden; diverging
  azul (+) / rojo (−); las señales usan icono + texto, nunca sólo color. Nunca doble eje Y.
- Nada de llamadas de red en tests; usar `data.demo_prices`/`demo_info`.
- Yahoo cambia formatos (`dividendYield`, `debtToEquity` en %…): normalizar sólo en
  `fundamental.extract` y cubrirlo con un test.

## Limitaciones conocidas / trabajo pendiente

- Umbrales heurísticos sin calibrar; el backtest real todavía no se ha ejecutado en el repo
  (el contenedor de desarrollo no tenía acceso a Yahoo). Primer paso: ejecutar
  `python -m stockdash.backtest --name watchlist` y subir `backtest/datos` y
  `backtest/resultados/watchlist`.
- Fundamentales sin histórico ⇒ el backtest sólo valida el bloque técnico.
- Medianas sectoriales aproximadas y globales (no distinguen EE. UU./Europa).

## Historial de cambios del modelo

| Fecha | Cambio | Motivo / evidencia |
|---|---|---|
| 2026-11-20 | Versión inicial: catálogo técnico y fundamental, pesos 60/40, `KAPPA = 0.5` | Heurística, sin backtest |
| 2026-11-20 | PER, EV/EBITDA, P/ventas y P/VC relativos a la mediana del sector (`sectors.py`) | Un mismo PER no significa lo mismo en banca que en tecnología |
| 2026-11-20 | Backtest replicable (`stockdash/backtest.py`) | Validar la señal; pendiente de ejecución con datos reales |
