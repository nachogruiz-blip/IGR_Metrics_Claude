# AGENTS.md — analizador de empresas

Guía para agentes de IA (y personas) que modifiquen `analisis_empresa/`. Proyecto
**independiente** de la librería `malliavin` y del dashboard `dashboard/`: dependencias propias
(`requirements.txt`), tests propios. Documentación en español; identificadores en inglés.

## Mapa

| Archivo | Responsabilidad | No debe |
|---|---|---|
| `app.py` | Interfaz Streamlit (cacheada), gráficos y tablas | contener cálculos ni umbrales |
| `analyst/data.py` | `CompanyData`, descarga Yahoo (import perezoso), `ALIASES` de partidas, `asset_type`, `MACRO_DRIVERS`, demo (`DEMO-ORO` incluido) | puntuar |
| `analyst/statements.py` | Ratios por ejercicio, Piotroski, Altman, pilares de balance y rentabilidad | — |
| `analyst/valuation.py` | CAPM/WACC, DCF, DCF inverso, P/VC justificado, pilar de valoración | — |
| `analyst/technical.py` | Indicadores, niveles, cruces, avisos (`flags`), pilar técnico | — |
| `analyst/macro.py` | Factores macro de oro/materias primas/divisas: β, efecto implícito, valor relativo, pilar | — |
| `analyst/timeseries.py` | Estadísticos, contrastes, EWMA, GARCH, VaR, β, pilar de riesgo | — |
| `analyst/verdict.py` | Matriz A×T, reglas de timing/veto, niveles → `Verdict` | importar streamlit/yfinance |
| `analyst/core.py` | Orquesta todo → `Analysis` | — |
| `analyst/report.py` | Informe Markdown (CLI y descarga) | — |
| `GUIA_USO.md` | Guía para el usuario (se muestra en la pestaña «Guía de uso») | — |
| `METODOLOGIA.md` | Fórmulas, umbrales y matriz de decisión (pestaña «Metodología») | — |
| `ejemplos/` | Informes de los perfiles demo | editarse a mano (se regeneran) |

Flujo: `data.fetch`/`data.demo` → `core.analyze` → `Analysis` (pilares + `Verdict`) →
`app.py` / `report.to_markdown`.

Dos ramas según `CompanyData.asset_type`: `"equity"` (balance, rentabilidad, valoración, técnico,
riesgo) y `"commodity"`/`"fx"` (factores macro, técnico, riesgo; `Analysis.valuation is None`,
`Analysis.macro` relleno, `decide(..., macro=pilar)`). `app.py` y `report.py` muestran una u otra
según `A.macro`.

## Comandos (desde `analisis_empresa/`)

```bash
pip install -r requirements.txt
pytest tests                              # < 5 s, sin red; deben pasar siempre
ANALYST_DEMO=1 streamlit run app.py       # app sin red
python -m analyst DEMO-ESPERA --demo      # informe sin red
```

CI (`.github/workflows/ci.yml`, job «Tests del analizador de empresas») ejecuta los tests y
arranca la app en modo demo con `streamlit.testing`.

## Invariantes (vigiladas por tests)

1. Puntuaciones en [−1, 1], +1 = favorable para comprar. Indicador sin dato ⇒ `score` NaN y
   los pesos se renormalizan (`Pillar.score`). Peso 0 = informativo.
2. Fracciones, no porcentajes, en todo el cálculo; el formato es cosa de `common.fmt`.
3. Estados financieros: una fila por ejercicio, ascendente, columnas canónicas de `ALIASES`;
   cifras en unidades monetarias (no millones). Las rarezas de Yahoo se resuelven sólo en
   `data.normalize_statement` / `data.fetch`, con test.
4. Fórmulas cerradas con test: DCF con g₁ = g_T ⇒ Gordon; DCF inverso invierte el DCF; WACC sin
   deuda = kₑ; Altman; Piotroski 9/0; filtro GARCH = recursión explícita; GARCH recupera
   parámetros simulados; VaR normal = cuantil (tolerancia 4·stderr).
5. Perfiles demo ⇒ veredicto conocido: `DEMO-COMPRA` COMPRAR, `DEMO-ESPERA` ESPERAR (tendencia
   bajista), `DEMO-VENDE` VENDER, `DEMO-CARA` ESPERAR (resultados en 9 días). `DEMO-ORO`:
   sensibilidades simuladas (β dólar −0.5, β tipos −0.04/pp) con el signo correcto y sin
   «relación inusual».
7. La app arranca en modo demo con una acción y con el oro (`tests/test_app.py`; `AppTest` no
   informa de errores de sintaxis en `at.exception`, por eso se comprueba también el título).
6. Nada de red en tests (`data.demo`). Vectorizar sobre fechas; la única recursión temporal es
   la simulación GARCH de la demo (el filtro usa `lfilter`).

## Recetas

- **Nuevo indicador**: calcularlo en su módulo, añadir un `Item(key, etiqueta, valor,
  puntuación, formato, lectura, peso)` al pilar, test con valor cerrado y fila en
  `METODOLOGIA.md`.
- **Tras cambiar umbrales, pesos o el informe**: regenerar `ejemplos/` (comando en
  `GUIA_USO.md` §6) y revisar que la tabla de ejemplos de la guía sigue siendo cierta.
- **Cambiar la decisión**: constantes `A_BUY`, `A_SELL`, `T_UP`, `T_DOWN`, `T_TACTICAL`,
  `EARNINGS_DAYS` y pesos en `verdict.py`; actualizar la tabla de `METODOLOGIA.md` y
  `test_decision_matrix`.
- **Nuevo factor macro o nueva materia prima**: añadir `(ticker, tipo, signo esperado)` a
  `data.MACRO_DRIVERS` (o un conjunto nuevo y su detección en `driver_set`); tipos `price`,
  `yield`, `level`, `ratio`. Actualizar la tabla de la sección 7 de `METODOLOGIA.md`.
- **Nueva partida de Yahoo**: añadir alias en `data.ALIASES` (el primero presente gana).
- **Paleta**: azul `#2a78d6`, naranja `#eb6834`, aqua `#1baf7a`, ámbar `#eda100` en ese orden;
  diverging azul (+) / rojo (−); el veredicto usa icono + texto, nunca sólo color; nunca doble
  eje Y.

## Limitaciones conocidas / pendiente

- Sin comparación sectorial de múltiplos (se podría reutilizar `dashboard/stockdash/sectors.py`).
- Sin backtest del veredicto; los fundamentales de Yahoo no tienen histórico punto en el tiempo.
- El contenedor de desarrollo no tenía acceso a Yahoo: el modo real está escrito según el
  formato documentado de `yfinance` (≥ 0.2.40, probado con 1.8) pero no se ha probado con
  datos reales en este repositorio.
