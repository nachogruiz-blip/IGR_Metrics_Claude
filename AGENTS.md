# AGENTS.md — guía para agentes de IA

Proyecto: cálculo de Malliavin y aplicaciones en finanzas (teoría en LaTeX + librería Python
`malliavin` + visualizaciones). Idioma de la documentación: **español**; identificadores de código en inglés.

## Antes de tocar nada
1. Lee `docs/guia_libreria.md` (estructura, convenciones de arrays, mapa fórmula → función).
2. Si hay un PDF en `docs/pdf/`, es la fuente teórica de referencia del usuario: la notación de
   `latex/` debe seguirlo.
3. `docs/bibliografia.md` indica qué referencia respalda cada módulo.

## Comandos
- Instalar: `pip install -e ".[dev]"`
- Tests: `pytest` (rápidos, < 10 s). Deben pasar siempre.
- Figuras: `for f in examples/*.py; do python "$f"; done` → `figures/`
- LaTeX: `cd latex && latexmk -pdf main.tex` (las figuras se cargan desde `../figures`).

## Reglas
- Toda fórmula nueva: capítulo LaTeX + función con docstring que la cite + test contra valor
  cerrado o identidad (tolerancia `4·stderr`) + ejemplo con `plotting.setup()/save()`.
- No introducir dependencias más allá de numpy/scipy/matplotlib sin motivo.
- Vectorizar sobre trayectorias; nada de bucles por trayectoria.
- Paleta de figuras: usar `plotting.SERIES` en orden fijo; nunca doble eje Y.
- Regenerar las figuras afectadas y comprometerlas junto con el código.
