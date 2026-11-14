"""03 · Integración por partes: E[⟨DF,u⟩] = E[F δ(u)] y la integral de Skorokhod.

(a) Convergencia de ambos lados con N para F = W_T², u = W_T (no adaptado).
(b) δ(W_T) = W_T² − T frente a la 'integral de Itô ingenua' W_T·W_T.
"""

import matplotlib.pyplot as plt
import numpy as np

from malliavin import plotting, skorokhod
from malliavin.brownian import TimeGrid, brownian_increments, paths_from_increments, rng

plotting.setup()
T = 1.0
grid = TimeGrid(T, 10)
dW = brownian_increments(grid, 400_000, rng(11))
WT = paths_from_increments(dW)[:, -1]
ones = np.ones(grid.n_steps)
delta_u = skorokhod.skorokhod_product(WT, np.ones_like(dW), ones, dW, grid.dt)  # = W_T² − T
lhs_s = 2 * WT**2 * T          # ⟨DF,u⟩ con DF = 2W_T, u = W_T
rhs_s = WT**2 * delta_u        # F δ(u)

Ns = np.unique(np.logspace(2, np.log10(WT.size), 30).astype(int))
fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
ax = axes[0]
for i, (s, lab) in enumerate([(lhs_s, "E[⟨DF, u⟩]"), (rhs_s, "E[F δ(u)]")]):
    m = np.array([s[:n].mean() for n in Ns])
    se = np.array([s[:n].std() / np.sqrt(n) for n in Ns])
    ax.plot(Ns, m, color=plotting.SERIES[i], label=lab)
    ax.fill_between(Ns, m - 1.96 * se, m + 1.96 * se, color=plotting.SERIES[i], alpha=0.15, lw=0)
ax.axhline(2 * T**2, color=plotting.NEUTRAL, lw=1, ls="--", label="valor exacto 2T²")
ax.set_xscale("log")
ax.set_xlabel("número de simulaciones N")
ax.set_title("Dualidad D–δ  (F = W_T², u = W_T)")
ax.legend()

ax = axes[1]
bins = np.linspace(-1.5, 6, 80)
ax.hist(WT**2, bins=bins, density=True, color=plotting.SERIES[1], alpha=0.55, label=f"W_T² (media {np.mean(WT**2):.2f})")
ax.hist(delta_u, bins=bins, density=True, color=plotting.SERIES[0], alpha=0.55, label=f"δ(W_T) = W_T² − T (media {delta_u.mean():.2f})")
ax.set_title("Skorokhod de un integrando no adaptado")
ax.set_xlabel("valor")
ax.legend()
fig.tight_layout()
print("Figura:", plotting.save(fig, "03_integracion_por_partes"))
