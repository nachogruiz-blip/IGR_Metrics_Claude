"""06 · Densidad de S_T vía integración por partes: p(x) = E[1_{S_T > x} δ(DF/||DF||²)].

Compara con la lognormal exacta y con un KDE: el estimador de Malliavin no tiene
ancho de banda y es insesgado en cada punto.
"""

import matplotlib.pyplot as plt
import numpy as np

from malliavin import bs, density, plotting
from malliavin.brownian import terminal_gbm, rng

plotting.setup()
S0, T, r, sigma = 100.0, 1.0, 0.03, 0.25
x = np.linspace(40, 200, 300)
exact = bs.lognormal_pdf(x, S0, T, r, sigma)

fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
WT, ST = terminal_gbm(5_000, T, S0, r, sigma, rng(51))
p, se = density.gbm_terminal_density(x, WT, ST, sigma, T)
ax = axes[0]
ax.plot(x, exact, color=plotting.NEUTRAL, lw=2.5, label="lognormal exacta")
ax.plot(x, p, color=plotting.SERIES[0], lw=1.5, label="Malliavin")
ax.fill_between(x, p - 1.96 * se, p + 1.96 * se, color=plotting.SERIES[0], alpha=0.15, lw=0)
ax.plot(x, density.gaussian_kde(ST, x), color=plotting.SERIES[1], lw=1.5, label="KDE (Silverman)")
ax.set_title("Densidad de S_T  (N = 5 000)"); ax.set_xlabel("x"); ax.legend()

ax = axes[1]
Ns = [500, 1000, 2000, 5000, 10_000, 20_000, 50_000]
err_m, err_k = [], []
for n in Ns:
    w, s = terminal_gbm(n, T, S0, r, sigma, rng(52))
    err_m.append(np.sqrt(np.mean((density.gbm_terminal_density(x, w, s, sigma, T)[0] - exact) ** 2)))
    err_k.append(np.sqrt(np.mean((density.gaussian_kde(s, x) - exact) ** 2)))
ax.loglog(Ns, err_m, "o-", color=plotting.SERIES[0], label="Malliavin")
ax.loglog(Ns, err_k, "o-", color=plotting.SERIES[1], label="KDE")
ax.set_xlabel("N"); ax.set_ylabel("RMSE en la malla"); ax.set_title("Error de estimación"); ax.legend()
fig.tight_layout()
print("Figura:", plotting.save(fig, "06_densidad_malliavin"))
