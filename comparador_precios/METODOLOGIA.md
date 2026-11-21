# Metodología

Cómo calcula el comparador cada columna. Las constantes viven en `pricecheck/scoring.py`; si
cambias una, cambia también esta página y `tests/test_scoring.py`.

## 1. Ofertas y precio final

1. Se buscan tiendas con tres consultas al buscador («<producto> comprar precio», «<producto>
   oferta tienda» y «"<producto>" precio», frase exacta). Se descartan redes sociales, foros,
   prensa, blogs de reseñas, comparadores, anuncios de particulares y webs de cupones
   (`search.NOT_SHOPS`) y las URL de artículos (`/blog/`, `/review`, `/comparativa`…). Por dominio
   se guardan hasta 2 URL, fichas antes que listados (`/buscar`, `/categoria`…): si la primera no
   es la ficha del producto se prueba la segunda (máximo de dominios configurable, 12 por defecto).
2. Se visita cada ficha y se lee el precio de los datos estructurados que publican las tiendas:
   JSON-LD `schema.org/Product` → microdatos → meta OpenGraph, en ese orden. Si la ficha
   tiene varias ofertas se prefiere la de producto **nuevo** más barata.
3. Se descarta la página si el título no contiene al menos el 60 % de las palabras buscadas o si
   falta alguna palabra con dígitos (el modelo: «XM5», «128GB»). También si es un **accesorio**
   para el producto: una palabra como «funda», «soporte», «compatible», «recambio»… aparece en el
   título *antes* del producto buscado («Funda para ghd chronos max»; pero «Plancha ghd chronos
   max con funda» sí vale). Así se evitan accesorios y modelos parecidos.
4. Con `SERPAPI_KEY`, se añaden además las ofertas de Google Shopping.
5. Se excluyen reacondicionados/usados (salvo que se pida) y precios en otra divisa.

6. **Ofertas ligadas a contratar un servicio** (`conditions.py`): si el dominio es de una
   operadora (`TELCO_DOMAINS`), o el título o una frase de la ficha que habla de precio dice «con
   tarifa», «al contratar fibra», «con tu línea móvil», «permanencia», «precio para clientes de
   fibra», «con suscripción»…, el precio no es comparable. La oferta se marca ⚠️, va al final de
   la lista y **no** cuenta para la mediana, el precio anómalo, «la más barata» ni la
   recomendación. No cuentan como condición la financiación («3 plazos de 83 €/mes») ni las
   newsletters («suscríbete y llévate un 10 %»).

**Precio final** = precio + envío − ahorro del mejor cupón **con código visto en la propia
ficha del vendedor** que no esté ya aplicado ni exija contratar nada. Los descuentos sin código
anunciados en la ficha se consideran ya incluidos en el precio mostrado. Los cupones de
agregadores aparecen como «sin verificar» y **no** se restan (muchos están caducados); la app
enseña también el precio «con cualquier cupón».

**Cupón ya aplicado** (`coupons.already_applied`, evita el doble descuento): muchas tiendas
publican el precio con el código ya descontado y además anuncian el código. Se considera que
el cupón ya está en el precio si:

- la frase lo dice («precio con el código», «descuento ya aplicado»…), o
- la frase cita un importe ≈ precio mostrado (tolerancia 1 %, mínimo 0,50 €), o
- hay un precio de referencia R —tachado en el JSON-LD (`priceType` StrikethroughPrice/ListPrice),
  «Antes/PVP/precio anterior» en el texto, `old_price` de Google Shopping o un importe de la frase
  mayor que el precio— tal que R − ahorro(R) ≈ precio, o la rebaja visible R − precio cubre ya al
  menos el 90 % del ahorro del cupón.

En la duda **no** se resta: es preferible sobrestimar el precio a prometer uno que no existe
(si una tienda permite acumular una rebaja y un código, el comparador dará el precio sin el
código; el cupón aparece igualmente con su estado).

## 1 bis. Estadísticos de la comparativa

En la pestaña «Comparativa» se marca qué ofertas entran (columna **Incluir**; por defecto todas
salvo las ligadas a un servicio y las de segunda mano), qué estadísticos se muestran y sobre qué
precio (final, precio + envío o precio). Se recalculan al momento (`stats.py`): mediana, media,
mínimo, máximo, percentiles 25 y 75 (interpolación lineal, como numpy/Excel), rango
intercuartílico, desviación típica (muestral, n − 1) y media recortada al 10 % (quita el 10 %
más bajo y más alto). También se recalcula la mejor opción fiable entre las marcadas. La
mediana del resumen superior y la detección de precios anómalos usan siempre la selección por
defecto (producto nuevo, sin servicio ligado, precio + envío).

## 2. Opiniones y problemas reportados

| Fuente | Qué aporta |
|---|---|
| Trustpilot (`es.trustpilot.com/review/<dominio>`) | Nota media de la tienda (0–5), nº de opiniones y reseñas recientes |
| Buscador («"<dominio>" opiniones problemas entrega estafa») | Fragmentos de foros y webs de quejas |
| RDAP (`rdap.org/domain/<dominio>`) | Fecha de registro del dominio |

Una reseña de Trustpilot cuenta como problema si tiene ≤ 2 estrellas **y** encaja en una
categoría por palabras clave (`reputation.KEYWORDS`). Un fragmento del buscador cuenta si menciona
la tienda, no procede de la propia tienda, suena negativo (`NEGATIVE_CUES`) y encaja en una
categoría. Categorías, por prioridad: **fraude**, **entrega**, **devolución/reembolso**,
**producto defectuoso**, **atención al cliente**.

La valoración del *producto* que aparece en la ficha se muestra aparte: no mide a la tienda.

## 3. Vendedor oficial

| Estado | Regla |
|---|---|
| Tienda oficial | El dominio está en `official.BRAND_DOMAINS` para la marca (o se indicó como dominio oficial), o en un marketplace el vendedor se llama como la marca |
| Marketplace (vendido por la plataforma) | Dominio en `MARKETPLACES` y el vendedor es la propia plataforma |
| Marketplace (vendedor externo) | Dominio en `MARKETPLACES` y vende un tercero o no consta quién vende |
| Minorista conocido | Dominio en `KNOWN_RETAILERS` |
| Tienda no catalogada | Ninguna de las anteriores. Si el dominio contiene la marca sin ser oficial se avisa de posible imitación |

La marca se toma de lo que indique el usuario; si no, de la más frecuente en las fichas; si no,
de la primera palabra de la búsqueda que esté en `BRAND_DOMAINS`.

## 4. Fiabilidad (0–100)

Media ponderada de cinco componentes en [0, 1]. Si falta un dato, su peso se reparte entre los
demás (renormalización).

| Componente | Peso | Fórmula |
|---|---:|---|
| Valoración | 0,40 | Media bayesiana r̄ = (n·r + m·μ)/(n + m) con μ = 3,5 y m = 50; componente = (r̄ − 1)/4 |
| Volumen | 0,10 | min(1, log₁₀(1 + n)/4) — 10 000 opiniones = 1 |
| Problemas | 0,20 | 1 − min(1, tasa/0,5), tasa = problemas / reseñas analizadas |
| Antigüedad del dominio | 0,15 | min(1, días / (3·365)) |
| Tipo de vendedor | 0,15 | oficial 1 · minorista 0,85 · marketplace directo 0,8 · marketplace externo 0,45 · no catalogada 0,4 |

La media bayesiana evita que una tienda con 3 opiniones de 5★ supere a una con 20 000 de 4,4★.

**Ajustes después de la media**

- Precio anómalo (total < 60 % de la mediana, con ≥ 3 ofertas): puntuación × 0,7 y aviso.
- Web sin HTTPS: puntuación máxima 30.

**Niveles**: ✅ Alta ≥ 75 · 🟡 Media ≥ 55 · 🟠 Baja ≥ 35 · ⛔ Riesgo < 35.

**Vetos** (fuerzan el nivel aunque la puntuación sea mayor):

- ≥ 2 reportes de fraude, o dominio de < 180 días **con** precio anómalo ⇒ ⛔ Riesgo.
- Sin ninguna opinión independiente de la tienda ⇒ como mucho 🟠 Baja.

## 5. Recomendación

**Mejor opción fiable** = la de menor precio final entre las de fiabilidad Alta o Media que no
estén marcadas sin stock ni exijan contratar un servicio. La **más barata sin filtrar** se enseña también, con su nivel, para que
se vea el riesgo que se asumiría.

## Limitaciones

- Las tiendas que no publican datos estructurados o que bloquean robots no aparecen. Para más
  cobertura, usa `SERPAPI_KEY` (Google Shopping).
- La clasificación de problemas es por palabras clave: puede haber falsos positivos y negativos.
  Lee siempre los textos en «Detalle por tienda».
- Los cupones de agregadores no se comprueban en la caja de la tienda.
- Es una ayuda automática, no una garantía: comprueba los datos antes de pagar.
