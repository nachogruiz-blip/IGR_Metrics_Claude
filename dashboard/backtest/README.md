# Backtest de la señal del dashboard

Comprueba, con datos históricos, si la **puntuación técnica**, la **recomendación** y la
**perspectiva a 1–3 meses** del dashboard anticipan algo. El código está en
[`../stockdash/backtest.py`](../stockdash/backtest.py) y usa exactamente las mismas funciones
que la app (`technical.features` + `scoring.assess`), así que un cambio en umbrales o pesos se
refleja en ambos.

## Ejecutar (replicable)

Desde `dashboard/`:

```bash
pip install -r requirements.txt

# 1) Primera vez: descarga de Yahoo Finance, guarda los precios y genera el informe
python -m stockdash.backtest --name watchlist --start 2012-01-01

# 2) Repetir exactamente el mismo backtest sin red (mismos datos guardados)
python -m stockdash.backtest --name watchlist --offline

# Otro universo, p. ej. Ibex
python -m stockdash.backtest --name ibex --tickers "SAN.MC,BBVA.MC,ITX.MC,IBE.MC,TEF.MC,REP.MC,CABK.MC,AMS.MC,FER.MC,ACS.MC"

# Comprobar el proceso con datos sintéticos (sin red)
python -m stockdash.backtest --demo
```

Opciones: `--tickers` (por defecto los de `watchlist.json`), `--start`, `--end`, `--cost-bps`
(coste por unidad de rotación, 10 por defecto), `--offline`, `--demo`, `--name`.

**Para que sea replicable, sube al repositorio los datos y los resultados**:

```bash
git add backtest/datos/watchlist.csv.gz backtest/resultados/watchlist/
```

`resumen.json` guarda la configuración, el comando, las versiones de Python/numpy/pandas y el
**SHA-256** del CSV de precios: con `--offline` sobre ese CSV se obtienen los mismos
`observaciones.csv` y `resumen.json` (lo verifica `tests/test_backtest.py`).
Yahoo revisa a veces los precios ajustados, así que una descarga nueva puede variar
ligeramente; por eso el CSV guardado es la referencia.

## Qué produce

```
backtest/
  datos/<nombre>.csv.gz            Precios OHLCV ajustados (formato largo: date,ticker,…)
  resultados/<nombre>/
    INFORME.md                     Informe legible (también visible en la pestaña Metodología)
    resumen.json                   Métricas + configuración + metadatos de reproducción
    observaciones.csv              Una fila por (cierre de mes, valor): señal y rentabilidades
    carteras.png, por_senal.png, calibracion.png
```

Columnas de `observaciones.csv`: `date` (mes), `session` (sesión real), `ticker`, `benchmark`,
`price`, `score` (técnica), `outlook_score`, `signal`, `outlook`, `prob_up`, `lo_/hi_1m`,
`lo_/hi_3m` (rangos ±1σ), `s_3m`, `r_1m`/`r_3m` (rentabilidad a 21/63 sesiones),
`rb_*` (índice), `ex_*` (exceso), `price_1m`/`price_3m`, `r_next` (hasta el siguiente cierre de
mes).

## Metodología

1. **Fechas**: último día hábil de cada mes, tras 260 sesiones de calentamiento (SMA200 y
   momentum 12−1 necesitan un año).
2. **Sin anticipación**: `technical.features` sólo usa ventanas móviles y suavizados causales;
   el test `test_features_are_causal` comprueba que la fila *t* coincide con el cálculo sobre el
   histórico truncado en *t*.
3. **Sólo técnico**: Yahoo no ofrece fundamentales históricos *point-in-time*; usar los
   actuales sería sesgo de anticipación. Sin fundamentales, la puntuación del dashboard es la
   técnica, así que se evalúa esa configuración.
4. **Métricas**: IC de Spearman por fecha (media, t); rentabilidad media y acierto por señal y
   perspectiva; calibración de P(subida); cobertura de los rangos ±1σ (ideal ≈ 68 %); carteras
   mensuales no solapadas con costes (por señal, universo equiponderado, diferencial
   mejor − peor quintil/tercil).

### Cómo leer el resultado

- **IC medio > 0,02–0,03 con t > 2** a 21 o 63 sesiones: la puntuación ordena valores mejor que
  el azar. |t| < 2: no distinguible de cero.
- **Por señal**: la rentabilidad media debería decrecer de «Compra fuerte» a «Venta fuerte».
- **Calibración**: si la frecuencia observada se separa mucho de P(subida), ajustar `KAPPA`.
- **Cobertura**: muy por encima de 68 % ⇒ rangos demasiado anchos; muy por debajo ⇒ estrechos.

## Recalibrar sin engañarse

Los umbrales actuales **no** se han ajustado con datos (`scoring.py`). Si se ajustan:

1. Dividir el periodo: ajustar con datos hasta una fecha (`--end 2019-12-31`) y validar después
   (`--start 2018-01-01`, contando el calentamiento) **sin volver a tocar nada**.
2. Cambiar pocos parámetros (pesos de bloque, `KAPPA`, `OUTLOOK_THRESHOLD`), no cada umbral.
3. Guardar ambos informes con nombres distintos (`--name ajuste_2012_2019`, `--name validacion`).
4. Anotar el cambio y su motivo en `dashboard/AGENTS.md` (sección «Historial de cambios del
   modelo»).

## Limitaciones conocidas

- **Sesgo de supervivencia**: el universo son valores que existen hoy (y que probablemente se
  eligieron porque les ha ido bien).
- Observaciones a 63 sesiones tomadas cada mes ⇒ solapadas: los t del IC y los porcentajes
  de acierto están algo inflados. Las carteras usan rentabilidades mensuales no solapadas.
- Con pocos valores (< 10) el IC por fecha es ruidoso; conviene un universo de 20+ valores.
- `resultados/demo/` usa datos sintéticos con regímenes persistentes: sólo valida el proceso,
  sus cifras no significan nada.
