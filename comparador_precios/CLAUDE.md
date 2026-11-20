# CLAUDE.md — comparador de precios (`comparador_precios/`)

Guía para agentes de IA (y personas) que revisen o modifiquen este proyecto. `AGENTS.md` es un
enlace a este archivo. Proyecto **independiente** de la librería `malliavin` y del resto de
carpetas del repositorio: dependencias propias (`requirements.txt`) y tests propios. Las reglas
de LaTeX/figuras del `AGENTS.md` raíz **no** le aplican. Documentación en español;
identificadores en inglés.

## Qué hace

Dado un producto («Sony WH-1000XM5»), busca las tiendas que lo venden y, para cada oferta, da:
precio, envío, precio final, **fiabilidad** de la tienda (0–100 + nivel), **media de opiniones**
de la tienda, **problemas reportados** (entrega, devolución, fraude, producto, atención),
si es **vendedor oficial** y **cupones/descuentos** activos. Recomienda la oferta más barata entre
las fiables. Interfaz Streamlit (`app.py`) y CLI (`python -m pricecheck`).

## Comandos (desde `comparador_precios/`)

```bash
pip install -r requirements.txt
pytest tests                              # ~5 s, SIN red; deben pasar siempre
PRICECHECK_DEMO=1 streamlit run app.py    # app con datos ficticios
streamlit run app.py                      # app real (necesita internet)
python -m pricecheck --demo               # informe Markdown sin red
python -m pricecheck "Sony WH-1000XM5" --brand sony [--json] [--include-used]
python -m pricecheck --demo > ejemplos/DEMO.md   # regenerar el ejemplo
```

CI: job «Tests del comparador de precios» en `.github/workflows/ci.yml` (tests + arranque de la
app en modo demo con `streamlit.testing`).

## Mapa

| Archivo | Responsabilidad | No debe |
|---|---|---|
| `pricecheck/models.py` | Dataclasses: `Offer`, `Coupon`, `Issue`, `Reputation`, `OfficialStatus`, `Reliability`, `Assessment`, `PriceReport`; etiquetas e iconos | hacer red ni puntuar |
| `pricecheck/http.py` | **Única salida a internet.** `HttpFetcher` (UA genérico, timeout, caché 30 min, 1 pet./s por host, robots.txt) y `FakeFetcher` para tests | — |
| `pricecheck/extract.py` | Ficha HTML → `PageProduct` (JSON-LD → microdatos → OpenGraph), `parse_price`, `match_score` | hacer red |
| `pricecheck/search.py` | Buscadores (`DuckDuckGoHtml`, `BraveSearch`), `SerpApiShopping`, `NOT_SHOPS`, `discover_offers` | puntuar |
| `pricecheck/reputation.py` | Trustpilot (JSON-LD), RDAP, quejas en buscador, `classify_issue` (palabras clave) | — |
| `pricecheck/official.py` | `registrable_domain`, `Registry` (marcas→dominios oficiales, marketplaces, minoristas), `classify` | — |
| `pricecheck/coupons.py` | Códigos/porcentajes/importes en texto libre; cupones de agregadores | — |
| `pricecheck/scoring.py` | Fiabilidad 0–100, niveles, vetos, precio anómalo. **Todas las constantes** | hacer red |
| `pricecheck/core.py` | `Sources` (inyección de fuentes), `live_sources`, `check` → `PriceReport` | importar streamlit |
| `pricecheck/demo.py` | Fuentes sintéticas sin red (marca «Aurora», tiendas `.example`) | usar nombres de empresas reales |
| `pricecheck/report.py` | Informe Markdown y formateo (`eur`, `seller_label`…) | — |
| `pricecheck/__main__.py` | CLI | — |
| `app.py` | Interfaz Streamlit (cacheada 30 min) | contener cálculos o umbrales |
| `METODOLOGIA.md` | Fórmulas, pesos, umbrales, reglas (se muestra en la pestaña «Metodología») | — |
| `README.md` | Guía de uso para personas | — |
| `ejemplos/DEMO.md` | Informe de la demo | editarse a mano (se regenera) |
| `tests/fixtures/` | HTML/JSON de ejemplo de cada fuente (formato real simplificado) | — |

## Flujo

```
check(query, Sources)
 ├─ Sources.offers(query, errors)  → [(Offer, texto visible de la ficha)]
 │    live: buscador ×2 consultas → shop_candidates (1 por dominio, sin NOT_SHOPS)
 │          → visitar ficha → extract_product → filtro match_score ≥ 0,6  (+ SerpAPI si hay clave)
 ├─ filtros: divisa ≠ EUR, usados/reacondicionados (salvo include_used); dedupe por (dominio, vendedor)
 ├─ marca: argumento > más frecuente en fichas > Registry.guess_brand(query)
 ├─ anomalies(totales) → mediana y marcas de precio anómalo
 ├─ por dominio, en paralelo: Sources.reputation(dominio, https) y Sources.coupons(dominio)
 ├─ por oferta: cupones de la ficha (verificados) + classify (oficial) + reliability
 └─ PriceReport (ordenado por precio final; recommended; cheapest; errors; notes)
```

Una fuente que falla **nunca** tumba el informe: se anota en `PriceReport.errors` y se sigue.

## Invariantes (vigiladas por tests)

1. Sin red en los tests. Todo lo que hace red pasa por un `Fetcher`; los tests usan
   `FakeFetcher` con `tests/fixtures/`. `test_live_pipeline_with_fake_fetcher` recorre la
   canalización real completa: si cambias URLs o parámetros de una fuente, actualiza sus rutas.
2. `None` = dato desconocido, nunca 0 (`shipping=None` ≠ envío gratis). Componentes sin dato son
   `NaN` y sus pesos se renormalizan. Porcentajes como fracción (0.10).
3. **Precio final** = precio + envío − mejor cupón **con código y verificado** (visto en la ficha).
   Descuentos sin código ⇒ ya incluidos en el precio. Cupones de agregadores ⇒ `verified=False`,
   se muestran pero no se restan (`price_with_any_coupon` es la cifra optimista).
4. Recomendada = menor precio final con nivel Alta/Media y `in_stock is not False`.
5. Vetos: ≥ 2 reportes de fraude ⇒ riesgo; dominio < 180 días + precio anómalo ⇒ riesgo;
   sin opiniones independientes ⇒ como mucho «baja»; sin HTTPS ⇒ puntuación ≤ 30.
6. La demo da resultados conocidos (docstring de `demo.py`, `test_demo_expected_outcomes`):
   recomendada `mercadoglobal.example`; `chollazo-outlet.example` en riesgo; oficial con AURORA10.
7. La demo sólo usa marcas y dominios **ficticios** (`.example`): no atribuir quejas a empresas reales.
8. Ninguna clave de API ni dato personal en código, UI, logs o peticiones: claves sólo por
   variables de entorno (`SERPAPI_KEY`, `BRAVE_API_KEY`); el User-Agent es genérico.
9. `HttpFetcher` respeta robots.txt para **páginas** (`get_text`) pero no para **APIs**
   (`get_json`, o `get_text(..., api=True)`): SerpAPI, Brave y RDAP son APIs documentadas.
10. Coincidencias por palabra completa: marca en el nombre del vendedor («LG» ≠ «Bulgaria»),
    plataforma («Amazon» ≠ «Amazonas»), palabra clave de cupón («code» ≠ «barcode»). El modelo
    se compara también sin separadores («WH1000XM5» = «WH-1000XM5»).
11. El precio anómalo se calcula sólo entre ofertas de producto nuevo.
12. La app arranca en modo demo (`tests/test_app.py`; se comprueba el título porque `AppTest` no
   informa de errores de sintaxis en `at.exception`).

## Recetas

- **Nueva marca con tienda oficial**: añadir `"marca": ("dominio.es", …)` a
  `official.BRAND_DOMAINS` (clave = `slug` de la marca: minúsculas sin símbolos).
- **Nuevo marketplace o minorista**: `official.MARKETPLACES` (con los nombres con los que la
  plataforma aparece como vendedor) o `official.KNOWN_RETAILERS`. Test en `test_official.py`.
- **Dominio que no es tienda y se cuela** (blog, comparador…): añadirlo a `search.NOT_SHOPS`.
- **Nueva fuente de ofertas** (otra API): clase con `__call__(query) -> list[Offer]` en
  `search.py`, engancharla en `core.live_sources` tras su variable de entorno, fixture JSON y test
  del parser. Las ofertas sin texto de ficha usan `""` como texto.
- **Nueva fuente de reputación**: función `parse_x(html|json, dominio) -> Reputation` en
  `reputation.py` con fixture y test; combinarla en `fetch_reputation` (acumular `issues`,
  `reviews_analyzed`, `sources`).
- **Nueva categoría de problema**: añadirla a `models.ISSUE_CATEGORIES` (el orden es la
  prioridad) y `ISSUE_LABELS`, palabras clave en `reputation.KEYWORDS` (sin tildes, minúsculas),
  aviso en `scoring.reliability` si procede y fila en `METODOLOGIA.md` §2.
- **Cambiar pesos, umbrales o vetos**: sólo en `scoring.py`; actualizar `METODOLOGIA.md` §4,
  `test_scoring.py`, comprobar `test_demo_expected_outcomes` y regenerar `ejemplos/DEMO.md`.
- **Un sitio cambia su HTML**: guardar un ejemplo nuevo en `tests/fixtures/`, ajustar el parser
  y añadir el caso al test correspondiente (no borrar los casos antiguos).

## Estilo de la app

Paleta `#2a78d6`, `#eb6834`, `#1baf7a`, `#eda100` en ese orden; niveles de fiabilidad con
icono + texto (✅ 🟡 🟠 ⛔), nunca sólo color; nunca doble eje Y. La app no calcula: llama a
`core.check` y formatea con `report`.

## Limitaciones conocidas / pendiente

- **El contenedor de desarrollo no tenía acceso a internet** (sólo a PyPI): el modo real está
  escrito según los formatos documentados de DuckDuckGo HTML, Brave Search API, SerpAPI Google
  Shopping, JSON-LD de schema.org/Trustpilot y RDAP, y probado con fixtures, **no con las webs
  reales**. Al probarlo de verdad, lo primero que puede fallar es el HTML de DuckDuckGo
  (`parse_ddg`) y Trustpilot (puede servir los datos en `__NEXT_DATA__` en vez de JSON-LD).
- DuckDuckGo HTML puede prohibirse en su robots.txt o limitar peticiones: entonces el error
  aparece en «Fuentes que fallaron» con la sugerencia de usar `BRAVE_API_KEY`/`SERPAPI_KEY`.
  Sin claves una búsqueda hace 2 + 2·N consultas al buscador a 1 pet./s: tarda ~30 s.
- Muchas tiendas grandes bloquean robots o renderizan el precio con JavaScript: no aparecerán sin
  `SERPAPI_KEY`. No hay navegador headless (decisión deliberada: dependencias ligeras).
- Problemas clasificados por palabras clave (ES/EN): falsos positivos/negativos posibles.
- Cupones de agregadores no se validan en la caja de la tienda.
- Sin conversión de divisas (sólo EUR) ni histórico de precios.
- En marketplaces la reputación es la de la plataforma, no la del vendedor externo (se avisa).
- Ideas: historial de precios con SQLite, alertas de bajada, valoración del vendedor externo del
  marketplace, más fuentes de quejas (OCU, Reclamaciones.com) respetando sus condiciones de uso.
