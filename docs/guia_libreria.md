# Guía de la librería `malliavin`

Documento de referencia para el usuario y para agentes de IA que trabajen en el repositorio.

## Estructura

```
src/malliavin/       Librería (importable tras `pip install -e .`)
  brownian.py        TimeGrid, incrementos, trayectorias, GBM exacto
  bs.py              Black–Scholes cerrado (precios, griegas, densidad lognormal) — referencia exacta
  chaos.py           Coeficientes de caos de f(W_T), truncaciones, energía por caos
  derivative.py      Derivada de Malliavin: discreta (dif. finitas sobre ΔW_k) y analítica
  skorokhod.py       MCEstimate, integrales de Itô/Wiener, δ(G h), chequeo de integración por partes
  clark_ocone.py     Integrandos E[D_tF|F_t] (cerrados y por cuadratura), reconstrucción
  greeks.py          Pesos de Malliavin (Δ, Γ, vega, ρ), diferencias finitas, pathwise, asiática
  density.py         Densidad vía p(x)=E[1_{F>x} δ(DF/||DF||²)], KDE para comparar
  plotting.py        Estilo matplotlib y paleta común; save() escribe en figures/
examples/            Un script por concepto; genera figures/NN_*.png
tests/               Identidades teóricas verificadas por Monte Carlo
latex/               Documento teórico (main.tex + capitulos/ + referencias.bib)
docs/                Esta guía, bibliografía, teoría resumida, PDF original (docs/pdf/)
```

## Convenciones

- **Formas de arrays**: trayectorias `(n_paths, n_steps+1)` incluyendo t=0; incrementos y
  derivadas de Malliavin `(n_paths, n_steps)` (valor en `[t_k, t_{k+1})`).
- **Funcionales**: `Callable[[W], np.ndarray]` que reciben trayectorias y devuelven `(n_paths,)`.
- **Estimaciones MC**: devuelven `MCEstimate(value, stderr)`; IC 95 % = `value ± 1.96·stderr`.
- **Medida**: siempre neutral al riesgo; `W` es browniano bajo Q; pagos descontados con `e^{-rT}`.
- **Semillas**: `brownian.rng(seed)`; los tests y ejemplos usan semillas fijas.
- Docstrings y documentación en español; identificadores en inglés.

## Mapa fórmula → función

| Fórmula | Función | Capítulo LaTeX |
|---|---|---|
| a_n = E[f(√T Z) He_n(Z)]/n! | `chaos.chaos_coefficients` | 2 |
| D_tF ≈ ∂φ/∂ΔW_k | `derivative.discrete_malliavin_derivative` | 3 |
| ⟨DF,h⟩ (Cameron–Martin) | `derivative.directional_derivative` | 3 |
| δ(Gh) = G W(h) − ⟨DG,h⟩ | `skorokhod.skorokhod_product` | 4 |
| E⟨DF,u⟩ = E[F δ(u)] | `skorokhod.integration_by_parts_check` | 4 |
| E[D_t f(W_T) \| F_t] | `clark_ocone.integrand_terminal_functional` | 5 |
| σ e^{-rt} S_t N(d₁) | `clark_ocone.integrand_call` | 5 |
| π_Δ, π_V, π_Γ, π_ρ | `greeks.malliavin_weights` | 6 |
| π_Δ asiática | `greeks.asian_delta_malliavin` | 6 |
| p(x) = E[1_{S_T>x}(W_T/(σT)+1)/S_T] | `density.gbm_terminal_density` | 7 |

## Derivación del peso asiático (resumen)

A = (1/T)∫S dt, D_sA = (σ/T)∫_s^T S_t dt. Con u_s = S_s: ⟨DA,u⟩ = σTA²/2.
Entonces Φ'(A)A = ⟨DΦ(A), 2u/(σTA)⟩ y, por dualidad,
E[Φ'(A)A] = E[Φ(A) δ(2u/(σTA))], con δ(Gu) = G∫S dW − ⟨DG,u⟩ = 2∫S dW/(σTA) + 1 y
∫S dW = (S_T − S_0 − rTA)/σ. Resultado: π = [2(S_T−S_0)/(σ²TA) − 2r/σ² + 1]/S_0.

## Cómo añadir un módulo nuevo (checklist para agentes)

1. Fórmula en `latex/capitulos/` (nuevo capítulo + `\input` en `main.tex`) y referencia en `referencias.bib`.
2. Implementación vectorizada en `src/malliavin/<modulo>.py` con docstring que cite la fórmula.
3. Test que compare con un valor cerrado o una identidad (tolerancia en múltiplos del error estándar, `k=4`).
4. Script `examples/NN_<nombre>.py` que use `plotting.setup()` / `plotting.save()`.
5. Actualizar la tabla de este documento y `README.md`.

## Ideas de extensión

- Localización y pesos óptimos (Fournié 2001, Benhamou 2003).
- Griegas en Heston / volatilidad local (derivada de Malliavin de una EDE vía proceso tangente Y_t).
- Fórmula de Hull–White anticipativa y skew de volatilidad implícita (Alòs et al.).
- Opciones americanas con esperanzas condicionadas vía Malliavin.
