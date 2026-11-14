# Fuente LaTeX de la guía teórica (reconstruida)

Código LaTeX de *Cálculo de Malliavin: de los procesos estocásticos y la integral de Itô al estado
del arte* (`docs/pdf/Calculo_de_Malliavin_corregido.pdf`), **reconstruido a partir del PDF compilado**.
El PDF no incluía los `.tex` originales, así que el texto se ha transcrito página a página.

```bash
cd latex/guia && latexmk -pdf main.tex     # genera main.pdf (≈104 págs.)
```

## Estructura

```
main.tex              Documento (book): partes I–VII, apéndices A–B, bibliografía
preambulo.tex         Paquetes, cajas tcolorbox (teoremas, «Panorama», «Intuición»), macros
capitulos/00_*.tex    Portada y prefacio
capitulos/01–23_*.tex Un archivo por capítulo (mismo número que en el PDF)
capitulos/A_*, B_*    Formulario y guía de notación
capitulos/bibliografia.tex  thebibliography con las 63 entradas, en el mismo orden ([1]…[63])
```

## Fidelidad respecto al PDF original

- Misma numeración de capítulos, secciones, teoremas, ecuaciones y citas bibliográficas.
- Los capítulos 1–11 empiezan exactamente en la misma página que el original; a partir del
  capítulo 12 hay un desfase de 1–2 páginas por diferencias menores de maquetación.
- El estilo de las cajas, los colores y la portada (dibujo TikZ de `ω` y `ω + εh`) son una
  aproximación visual, no el código original.
- Al ser una transcripción, puede haber erratas puntuales. Si encuentras una diferencia con el PDF,
  el PDF manda.

## Macros principales (`preambulo.tex`)

`\E`, `\P`, `\Q`, `\F`, `\Hf` (𝔥), `\Hc`, `\Sc`, `\D` (𝔻), `\ind`, `\dd`, `\ip{a}{b}`, `\norm{x}`,
`\abs{x}`, `\cond{X}{\G}`, `\law`, `\tolaw`. Entornos: `teorema`, `proposicion`, `lema`, `corolario`,
`definicion`, `ejemplo`, `ejercicio`, `observacion`, `panorama`, `intuicion`.
