# AGENTS.md — curso de trader profesional

Guía para agentes de IA (y personas) que modifiquen `curso_trader/`. Proyecto **independiente** del
resto del repo: dependencias propias (`requirements.txt`), tests propios. Documentación y salidas de
consola en **español**; identificadores en inglés. `CLAUDE.md` es un enlace a este archivo.

## Estado (actualiza esta sección al terminar cada tarea)

- **Hecho (v0.1, nov. 2026)**: PDF de 46 págs. (`latex/main.pdf`, 15 capítulos + formulario + glosario
  + bibliografía); librería `trader/` con 14 módulos; 6 scripts de uso diario + generador de figuras;
  11 figuras; 54 tests (~15 s, sin red).
- **Pendiente / ideas**: capítulo de opciones con sonrisa SVI y P&L de gamma scalping simulado;
  índices de volatilidad (VIX, curva de futuros VIX); renta fija con curva cero bootstrap y futuros de
  bonos (CTD, factor de conversión); estacionalidad real con datos; app Streamlit opcional que envuelva
  los scripts; ejercicios resueltos en un apéndice; descarga opcional de datos COT/EIA.

## Mapa

| Ruta | Responsabilidad | Capítulo del PDF |
|---|---|---|
| `trader/data.py` | `load_prices` (CSV), `download` (yfinance opcional), generadores sintéticos deterministas | §2, §13 |
| `trader/indicators.py` | SMA/EMA, RSI y ATR de Wilder, Bollinger, MACD, Donchian (sin día actual), pivotes, vol realizada | §3 |
| `trader/risk.py` | Tamaño por stop/ATR, vol targeting, Kelly, ruina (MC vectorizado), VaR/ES, drawdown, contribuciones | §4 |
| `trader/performance.py` | CAGR, Sharpe, Sortino, Calmar, PSR, máximo Sharpe esperado, estadísticas por operación | §5 |
| `trader/backtest.py` | `backtest` sin look-ahead, estrategias SMA/Donchian/RSI, vol targeting, `trades`, walk-forward | §5 |
| `trader/journal.py` | Diario CSV, P&L, 1R y múltiplo R, resumen por setup | §6, §13 |
| `trader/equity.py` | MCO, beta/CAPM, factores, momentum 12-1, gaps, pares (β, half-life, ADF, z-score) | §7 |
| `trader/fx.py` | Pips, valor del pip, lotes, cruces vía USD, arbitraje triangular, CIP/forward, carry, PPA, sesiones | §8 |
| `trader/commodities.py` | `CONTRACTS` (especificaciones), coste de carry, conveniencia, roll yield, crack/crush/spark, back-adjust | §9 |
| `trader/rates.py` | Precio, TIR, duración, convexidad, DV01, cobertura DV01 | §10 |
| `trader/options.py` | BSM, Black-76, Garman–Kohlhagen, griegas, IV, movimiento esperado, payoffs | §11 |
| `trader/crypto.py` | Funding y base anualizados, cash & carry, precio de liquidación | §12 |
| `trader/plotting.py` | `setup()`, `save()`, paleta `SERIES` | figuras |
| `scripts/` | CLIs diarios: `premercado`, `tamano_posicion`, `informe_riesgo`, `backtest`, `diario`, `calculadoras`; `generar_figuras` | §13 |
| `latex/` | `main.tex` + `capitulos/NN_*.tex`; figuras desde `../figuras` | — |

## Comandos (desde `curso_trader/`)

```bash
pip install -r requirements.txt
pytest tests                                   # ~15 s; deben pasar siempre (job CI «Tests del curso de trader»)
python scripts/generar_figuras.py              # → figuras/*.png
cd latex && latexmk -pdf main.tex              # → latex/main.pdf (comprometer el PDF)
```

## Reglas

1. Toda fórmula nueva: sección en el capítulo LaTeX + función con docstring que cite «curso §N» +
   test contra valor cerrado, identidad o diferencias finitas.
2. Anti look-ahead: en backtests la posición de t se aplica a la rentabilidad de t+1; los niveles
   (Donchian, β de pares) se calculan sólo con el pasado. Hay tests que lo vigilan.
3. Sólo numpy/scipy/pandas/matplotlib. `yfinance` es opcional (import perezoso) y nada usa red en tests.
4. Vectorizar sobre trayectorias/activos; las recursiones de una sola serie (AR(1)) son aceptables.
5. Scripts: `argparse`, ayuda con ejemplos en el docstring, modo demo sintético sin argumentos, salida en
   español con coma decimal (`_comun.fmt/pct`). Añadir cada script nuevo a `tests/test_scripts.py`.
6. Figuras: `plotting.setup()/save()`, paleta `SERIES` en orden, nunca doble eje Y; regenerar y
   comprometer las figuras y el PDF tras cambiarlos.
7. Nunca comprometer datos personales (`datos/*.csv` está ignorado; repo público).
8. Es material educativo: mantener el aviso de no asesoramiento en el PDF y el README.

## Recetas

- **Nuevo instrumento de futuros**: entrada en `commodities.CONTRACTS` (multiplicador en $ por unidad
  cotizada, tick) + fila en la tabla de §9 (`capitulos/09_commodities.tex`) + caso en `test_contract_specs`.
- **Nueva estrategia de backtest**: función `-> pd.Series` de posiciones en `backtest.py`, opción en
  `scripts/backtest.py`, test de valores admisibles y de no look-ahead.
- **Nuevo capítulo**: `latex/capitulos/NN_nombre.tex`, `\input` en `main.tex`, fila en la tabla del plan
  de estudio (§14) y en el mapa de arriba.
