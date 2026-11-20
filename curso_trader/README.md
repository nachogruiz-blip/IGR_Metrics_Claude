# Curso de Trader Profesional

Curso autocontenido para aprender a operar de forma profesional en **renta variable (equity)**,
**divisas (FX)**, **materias primas (commodities)**, además de **renta fija**, **opciones/volatilidad**
y **cripto**. Combina:

- 📘 **PDF del curso**: [`latex/main.pdf`](latex/main.pdf) (46 págs.): microestructura, estadística,
  análisis técnico, gestión del riesgo y tamaño de posición, backtesting y sobreajuste, psicología,
  un capítulo por clase de activo, rutina diaria, plan de 12 semanas, formulario y glosario.
- 🐍 **Librería `trader/`**: cada fórmula del PDF implementada y verificada por tests.
- 🛠️ **Scripts de uso diario** (`scripts/`), que funcionan con tus CSV o, sin argumentos, con datos sintéticos.

> Material educativo. No es asesoramiento financiero. Operar con apalancamiento puede hacer perder
> más que el capital depositado.

## Instalación

```bash
cd curso_trader
pip install -r requirements.txt
pytest tests                    # ~15 s, sin red
```

## Scripts

| Script | Uso |
|---|---|
| `premercado.py` | Checklist, sesiones FX abiertas, ATR, vol, RSI, régimen, pivotes y rango esperado |
| `tamano_posicion.py` | Tamaño por riesgo: `accion`, `fx`, `futuro`, `atr`, `cripto` |
| `informe_riesgo.py` | Vol de cartera, VaR/ES normal e histórico, contribuciones, correlaciones, estrés |
| `backtest.py` | SMA, Donchian, RSI(2), pares; costes, vol targeting, métricas, PSR, gráfico |
| `diario.py` | Diario de operaciones (`nueva`, `resumen`, `demo`) con estadísticas en R por setup |
| `calculadoras.py` | `opcion`, `iv`, `movimiento`, `forward`, `cruce`, `curva`, `crack`, `bono`, `funding` |
| `generar_figuras.py` | Regenera las figuras del PDF |

```bash
python scripts/tamano_posicion.py fx --capital 20000 --riesgo 1 --par EURUSD --tipo 1.0850 --stop-pips 25
python scripts/tamano_posicion.py futuro --capital 250000 --riesgo 0.75 --simbolo CL --entrada 74.2 --stop 72.6
python scripts/premercado.py --csv datos/SPY.csv --csv datos/EURUSD.csv
python scripts/backtest.py --estrategia donchian --vol-objetivo 0.10
python scripts/calculadoras.py curva --precios 78.1 77.4 76.9 76.5 --meses 1 2 3 4
```

Formato de los CSV: columna de fecha (`date`/`Date`/`fecha`) y `open, high, low, close[, volume]`;
para `informe_riesgo.py`, una columna de cierre por activo. Guárdalos en `datos/` (ignorado por git).

## Compilar el PDF

```bash
python scripts/generar_figuras.py
cd latex && latexmk -pdf main.tex
```

Para agentes de IA: ver [`AGENTS.md`](AGENTS.md) (también `CLAUDE.md`), con el estado y las reglas del proyecto.
