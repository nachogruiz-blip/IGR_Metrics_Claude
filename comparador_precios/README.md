# Comparador de precios

Dime un producto y te digo **dónde comprarlo**: todas las tiendas que lo venden que se puedan
encontrar, con

- precio, gastos de envío y **precio final**;
- **fiabilidad** de la tienda (0–100 y nivel ✅ Alta / 🟡 Media / 🟠 Baja / ⛔ Riesgo);
- **media de opiniones** de la tienda (Trustpilot) y nº de opiniones;
- **problemas reportados** (entregas, devoluciones, fraude, producto defectuoso, atención);
- si es **vendedor oficial** de la marca, minorista conocido o vendedor externo de un marketplace;
- **cupones y descuentos** activos (verificados en la web o encontrados en agregadores).

Y una recomendación: la tienda más barata entre las fiables.

Además avisa de las ofertas que **esconden un contrato** (precio «con tarifa», «al contratar
fibra», permanencia…: se marcan ⚠️ y no cuentan), no resta dos veces un cupón cuyo descuento
**ya está en el precio** de la ficha, y en la pestaña «Comparativa» puedes **elegir qué ofertas
y qué estadísticos** (mediana, media, mínimo, máximo, percentiles, desviación…) entran en el
cálculo: se recalcula al momento.

## Uso

```bash
cd comparador_precios
pip install -r requirements.txt

streamlit run app.py                          # app web
PRICECHECK_DEMO=1 streamlit run app.py        # app con datos ficticios, sin red

python -m pricecheck "Sony WH-1000XM5"                    # informe en Markdown
python -m pricecheck "Sony WH-1000XM5" --brand sony --json
python -m pricecheck --demo                               # sin red
```

Consejos: busca el **modelo exacto** («Sony WH-1000XM5», «iPhone 16 128GB»); si la marca no se
reconoce como oficial, indica su dominio con «Dominio oficial adicional» (`--official-domain`).

### Claves opcionales (variables de entorno)

| Variable | Para qué |
|---|---|
| `SERPAPI_KEY` | Añade Google Shopping (muchas más tiendas). serpapi.com |
| `BRAVE_API_KEY` | Usa Brave Search en vez de DuckDuckGo (más estable). api.search.brave.com |

Sin claves funciona con DuckDuckGo + visita de las fichas + Trustpilot + RDAP.

Cómo se calcula todo: [METODOLOGIA.md](METODOLOGIA.md). Ejemplo de informe:
[ejemplos/DEMO.md](ejemplos/DEMO.md).

> Es una ayuda automática: comprueba siempre los datos en la web de la tienda antes de pagar.
