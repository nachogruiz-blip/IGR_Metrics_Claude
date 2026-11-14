"""08 · Esperanzas condicionales y opciones bermudas por Malliavin (PDF §14.1–14.2).

(a) E[S_t | S_s = x] estimada sin regresión: peso sin localizar vs localizado vs exacto.
(b) Put bermuda (10 fechas): estimador por valores (in-sample, ruidoso) frente al de la regla
    de ejercicio aplicada a trayectorias nuevas (cota inferior), y árbol binomial de referencia.
"""

import matplotlib.pyplot as plt
import numpy as np

from malliavin import bs, conditional, plotting
from malliavin.brownian import TimeGrid, brownian_paths, gbm_from_brownian, rng

plotting.setup()
S0, K, T, r, sigma = 100.0, 100.0, 1.0, 0.05, 0.2
s, t = 0.5, 1.0

fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
grid = TimeGrid(t, 2)
W = brownian_paths(grid, 5_000, rng(80))
S = gbm_from_brownian(W, grid, S0, r, sigma)
H = conditional.bs_conditional_weight(S[:, 1], W[:, 1], W[:, 2], s, t, sigma)
x = np.linspace(70, 140, 120)
ax = axes[0]
ax.plot(x, x * np.exp(r * (t - s)), color=plotting.NEUTRAL, lw=2.5, label="exacta x·e^{r(t−s)}")
ax.plot(x, conditional.conditional_expectation(S[:, 2], S[:, 1], H, x, localize=False), color=plotting.SERIES[1], lw=1.5, label="Malliavin sin localizar")
ax.plot(x, conditional.conditional_expectation(S[:, 2], S[:, 1], H, x, localize=True), color=plotting.SERIES[0], lw=1.5, label="Malliavin localizado")
ax.set_xlabel("x"); ax.set_title("E[S_t | S_s = x]   (N = 5 000, s = 0,5, t = 1)"); ax.legend()

ax = axes[1]
n_ex = 10
ref = conditional.bermudan_put_binomial(S0, K, T, r, sigma, n_ex)
euro = bs.call_price(S0, K, T, r, sigma) - S0 + K * np.exp(-r * T)
ests = [conditional.bermudan_put_malliavin(S0, K, T, r, sigma, n_ex, 2_000, seed=800 + i) for i in range(12)]
high = np.array([e.high for e in ests])
low = np.array([e.low for e in ests])
bins = np.linspace(5.5, 6.6, 23)
ax.hist(high, bins=bins, histtype="step", color=plotting.SERIES[1], lw=2.2,
        label=f"por valores, in-sample (media {high.mean():.3f})")
ax.hist(low, bins=bins, histtype="step", color=plotting.SERIES[0], lw=2.2,
        label=f"regla de ejercicio, caminos nuevos (media {low.mean():.3f})")
ax.axvline(ref, color=plotting.TEXT, lw=1.5, label=f"árbol binomial {ref:.3f}")
ax.axvline(euro, color=plotting.NEUTRAL, lw=1.5, ls="--", label=f"put europea {euro:.3f}")
ax.set_ylim(0, max(np.histogram(high, bins)[0].max(), np.histogram(low, bins)[0].max()) + 4)
ax.set_xlabel("precio"); ax.set_ylabel("semillas")
ax.set_title("Put bermuda, 10 fechas, N = 2 000 (12 semillas)")
ax.legend(loc="upper left", frameon=True, facecolor=plotting.SURFACE, edgecolor="none", framealpha=1)
fig.tight_layout()
print(f"Bermuda: binomial {ref:.4f} | por valores {high.mean():.4f} ± {1.96*high.std(ddof=1)/np.sqrt(len(high)):.4f}"
      f" | regla de ejercicio {low.mean():.4f} ± {1.96*low.std(ddof=1)/np.sqrt(len(low)):.4f}")
print("Figura:", plotting.save(fig, "08_esperanza_condicional_bermudas"))
