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
| Valoración | 30 % | PER estimado e histórico, PEG, EV/EBITDA, rentabilidad FCF, precio/ventas |
| Calidad | 25 % | ROE, ROA, márgenes operativo, neto y bruto |
| Crecimiento | 20 % | Crecimiento interanual de ventas y BPA |
| Salud financiera | 15 % | Deuda neta/EBITDA, deuda/patrimonio, liquidez corriente |
| Analistas | 10 % | Potencial al precio objetivo y recomendación de consenso (sólo con ≥ 3 analistas) |

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

- Umbrales heurísticos (reglas usuales de análisis técnico y rangos típicos de ratios), **no
  calibrados con backtest** ni por sector: un PER de 30 es caro para un banco y normal para
  software. Bancos y aseguradoras carecen de EBITDA/deuda neta y su bloque de salud queda vacío.
- Los fundamentales vienen de Yahoo Finance (`yfinance`), con retrasos y huecos ocasionales.
- No es asesoramiento financiero.
