### Cómo se calcula la señal

**1. Cada indicador → puntuación en [−1, +1]** (+1 = muy favorable) mediante una función lineal a
tramos con umbrales fijos. Los indicadores sin dato se omiten y los pesos se renormalizan; la
cobertura (% de indicadores disponibles) se muestra en la ficha.

**2. Bloques técnicos** (puntuación técnica *T*):

| Bloque | Peso | Indicadores |
|---|---|---|
| Tendencia | 35 % | Precio vs SMA200 y SMA50, cruce SMA50/SMA200, pendiente de la SMA50, dirección ADX (+DI/−DI) |
| Momentum | 30 % | Momentum 12−1 meses, rentabilidad 3 meses, histograma MACD, fuerza relativa vs índice |
| Osciladores | 15 % | RSI(14) (sobreventa puntúa +, sobrecompra −), %B de Bollinger |
| Volumen | 10 % | Pendiente del OBV a un mes (acumulación / distribución) |
| Riesgo | 10 % | Distancia al máximo de 52 semanas, volatilidad 3m frente a 12m |

**3. Bloques fundamentales** (puntuación fundamental *F*):

| Bloque | Peso | Indicadores |
|---|---|---|
| Valoración | 30 % | PER estimado e histórico, EV/EBITDA, precio/ventas y precio/valor contable **frente a su sector**; PEG y rentabilidad FCF |
| Calidad | 25 % | ROE, ROA, márgenes operativo, neto y bruto |
| Crecimiento | 20 % | Crecimiento interanual de ventas y BPA |
| Salud financiera | 15 % | Deuda neta/EBITDA, deuda/patrimonio, liquidez corriente |
| Analistas | 10 % | Potencial al precio objetivo y recomendación de consenso (sólo con ≥ 3 analistas) |

**Valoración relativa al sector.** Los múltiplos se comparan con la mediana aproximada del
sector de Yahoo (`stockdash/sectors.py`): puntuación = −log(múltiplo / mediana) / log(1,6),
recortada a [−1, 1]. Vale 0 en la mediana, +1 si cotiza 1,6 veces más barato y −1 si 1,6 veces
más caro; con pérdidas (PER ≤ 0), −1. Los múltiplos sin sentido en un sector no puntúan:
EV/EBITDA y precio/ventas en banca; precio/valor contable sólo cuenta en financieras e
inmobiliarias. La tabla de detalle muestra la mediana usada.

| Sector (Yahoo) | PER est. | PER hist. | EV/EBITDA | P/ventas | P/VC |
|---|---|---|---|---|---|
| Technology | 25 | 30 | 20 | 6,0 | — |
| Communication Services | 18 | 20 | 10 | 3,0 | — |
| Consumer Cyclical | 20 | 22 | 13 | 1,5 | — |
| Consumer Defensive | 19 | 21 | 13 | 1,3 | — |
| Healthcare | 18 | 24 | 15 | 3,5 | — |
| Industrials | 20 | 23 | 14 | 2,0 | — |
| Energy | 11 | 12 | 6 | 1,2 | — |
| Utilities | 16 | 18 | 11 | 2,5 | — |
| Basic Materials | 15 | 17 | 9 | 1,8 | — |
| Real Estate | 30 | 32 | 18 | 6,0 | 1,6 |
| Financial Services | 12 | 13 | — | — | 1,3 |
| Otro / desconocido | 18 | 21 | 12 | 2,5 | — |

Medianas aproximadas de grandes compañías (orden de magnitud de las tablas de Damodaran y de
los índices sectoriales MSCI, 2024–2026); conviene revisarlas una vez al año.

**4. Puntuación total** *S = w·T + (1 − w)·F*, con *w* = 60 % por defecto (ajustable en la barra
lateral). Para un horizonte de 1–3 meses el precio y su tendencia explican más que la valoración.

**5. Recomendación actual** según *S*: ≥ 0,45 Compra fuerte · ≥ 0,15 Comprar · entre −0,15 y 0,15
Mantener · ≤ −0,15 Vender · ≤ −0,45 Venta fuerte. Se añaden avisos de *timing*: comprar con RSI
> 70 (mejor escalonar o esperar retroceso), vender con RSI < 30 (probable rebote), discrepancia
fuerte entre técnico y fundamental, pocos datos.

**6. Perspectiva a 1–3 meses.** Si el ADX < 20 y el bloque de tendencia es débil, el mercado no
tiene tendencia y *S* se reduce a la mitad. Con la puntuación resultante *S′*:
Alcista si *S′* > 0,15, Bajista si *S′* < −0,15, Lateral en otro caso.

El **rango** modela la rentabilidad a *h* sesiones como normal con desviación
*s = σ₆₃·√(h/252)* (σ₆₃ = volatilidad realizada de 3 meses) y media *μ = 0,5·S′·s*: la señal
desplaza el centro como mucho media desviación típica. El rango mostrado es *P·e^{μ ± s}*
(≈ 68 %) y *P(subida) = Φ(0,5·S′)*, entre 31 % y 69 %: la incertidumbre de un valor individual a
1–3 meses es grande y el modelo no pretende lo contrario.

El **stop orientativo** es precio − 2·ATR(14).

### Limitaciones

- Umbrales heurísticos (reglas usuales de análisis técnico y rangos típicos de ratios). El
  backtest (`dashboard/backtest/`) evalúa la parte técnica; los fundamentales no tienen
  histórico y no se pueden validar así. Las medianas sectoriales son aproximadas y globales.
- Bancos y aseguradoras carecen de EBITDA/deuda neta y su bloque de salud queda casi vacío.
- Los fundamentales vienen de Yahoo Finance (`yfinance`), con retrasos y huecos ocasionales.
- No es asesoramiento financiero.
