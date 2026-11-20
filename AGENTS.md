# AGENTS.md — guía para agentes de IA

Proyecto: cálculo de Malliavin y aplicaciones en finanzas (teoría en LaTeX + librería Python
`malliavin` + visualizaciones). Idioma de la documentación: **español**; identificadores de código en inglés.

## Antes de tocar nada
1. Lee `docs/guia_libreria.md` (estructura, convenciones de arrays, mapa fórmula → función).
2. La fuente teórica es `docs/pdf/Calculo_de_Malliavin_corregido.pdf` (105 págs., 23 capítulos).
   `docs/mapa_pdf.md` dice qué capítulo está implementado dónde y qué falta. Sigue su notación
   (H_n de Hermite, ϕ_t de cobertura, etc.) y cita su numeración (`\guia{Teorema 8.9}` en LaTeX;
   «PDF §12.4» en docstrings). Su fuente LaTeX reconstruida está en `latex/guia/` (un archivo por
   capítulo, `capitulos/NN_*.tex`): es la forma más cómoda de leerla o buscar en ella.
3. `docs/bibliografia.md` indica qué referencia respalda cada módulo.

## Comandos
- Instalar: `pip install -e ".[dev]"`
- Tests: `pytest` (rápidos, < 15 s). Deben pasar siempre; GitHub Actions (`.github/workflows/ci.yml`) los ejecuta junto con la compilación de los dos LaTeX en cada push a `main` y en cada PR.
- Figuras: `for f in examples/*.py; do python "$f"; done` → `figures/`
- LaTeX compañero: `cd latex && latexmk -pdf main.tex` (las figuras se cargan desde `../figures`).
- LaTeX de la guía: `cd latex/guia && latexmk -pdf main.tex`.

## Reglas
- Toda fórmula nueva: capítulo LaTeX + función con docstring que la cite + test contra valor
  cerrado o identidad (tolerancia `4·stderr`) + ejemplo con `plotting.setup()/save()`.
- No introducir dependencias más allá de numpy/scipy/matplotlib sin motivo.
- Vectorizar sobre trayectorias; nada de bucles por trayectoria.
- Paleta de figuras: usar `plotting.SERIES` en orden fijo; nunca doble eje Y.
- Regenerar las figuras afectadas y comprometerlas junto con el código.
- `latex/main.tex` es un compañero numérico de la guía: no copiar demostraciones largas, enlazar a la guía.
- `latex/guia/` es la transcripción de la guía: reproduce su contenido, pero **corrige** las erratas y errores
  del original (no se conservan). Cada corrección se anota en `latex/guia/ERRATAS.md`.
- Recompilar `latex/main.pdf` tras cambiar `latex/` y comprometer el PDF.

## Dashboard de acciones (`dashboard/`)
Proyecto independiente de la librería (sus propias dependencias y tests: `pytest dashboard/tests`).
Antes de modificarlo, lee `dashboard/AGENTS.md`. Las reglas de LaTeX/figuras de arriba no le aplican.

## Analizador de empresas (`analisis_empresa/`)
Proyecto independiente (sus propias dependencias y tests: `pytest analisis_empresa/tests`).
Antes de modificarlo, lee `analisis_empresa/AGENTS.md`. Las reglas de LaTeX/figuras de arriba no le aplican.

## Estudio de vídeo (`estudio_video/`)
Proyecto independiente (sus propias dependencias y tests: `pytest estudio_video/tests`).
Antes de modificarlo, lee `estudio_video/AGENTS.md`. Las reglas de LaTeX/figuras de arriba no le aplican.

## Curso de trader (`curso_trader/`)
Proyecto independiente (sus propias dependencias y tests: `pytest curso_trader/tests`).
Antes de modificarlo, lee `curso_trader/AGENTS.md` (incluye la sección «Estado»). Las reglas de LaTeX/figuras
de arriba no le aplican; tiene las suyas (su PDF es `curso_trader/latex/main.pdf`).
