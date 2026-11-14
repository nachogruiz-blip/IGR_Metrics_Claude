"""02 · Derivada de Malliavin: ¿cómo responde F a un 'empujón' del ruido en t?

Para cada funcional se compara la derivada discreta (diferencias finitas sobre los
incrementos brownianos) con la fórmula analítica, a lo largo de t ∈ [0, T].
"""

import matplotlib.pyplot as plt
import numpy as np

from malliavin import derivative, plotting
from malliavin.brownian import TimeGrid, brownian_increments, gbm_from_brownian, paths_from_increments, rng

plotting.setup()
grid = TimeGrid(1.0, 100)
dW = brownian_increments(grid, 1, rng(12))
W = paths_from_increments(dW)
t = grid.t[:-1]
sigma = 0.3

cases = [
    ("F = W_T³", lambda w: w[:, -1] ** 3, derivative.analytic_terminal_power(W, grid, 3)),
    ("F = ∫₀ᵀ W_s ds", lambda w: w[:, :-1].sum(1) * grid.dt, derivative.analytic_time_integral(W, grid)),
    ("F = max_{s≤T} W_s", lambda w: w.max(1), derivative.analytic_running_max(W, grid)),
    (
        "F = S_T (GBM, σ=0.3)",
        lambda w: gbm_from_brownian(w, grid, 100, 0.0, sigma)[:, -1],
        derivative.analytic_gbm_terminal(gbm_from_brownian(W, grid, 100, 0.0, sigma), sigma, grid),
    ),
]

fig, axes = plt.subplots(3, 2, figsize=(10, 9), gridspec_kw={"height_ratios": [1, 1, 1]})
ax = axes[0, 0]
ax.plot(grid.t, W[0], color=plotting.SERIES[0])
k = W[0].argmax()
ax.scatter([grid.t[k]], [W[0, k]], s=40, color=plotting.SERIES[1], zorder=3, label="τ* = argmax")
ax.set_title("Trayectoria browniana usada")
ax.legend()
axes[0, 1].axis("off")
axes[0, 1].text(0, 0.5, "D_t F ≈ ∂F/∂(ΔW_k),  t ∈ [t_k, t_{k+1})\n\n"
                "Línea: fórmula analítica\nPuntos: derivada discreta (dif. finitas)",
                fontsize=10, color=plotting.TEXT_2, va="center")
for ax, (name, F, Dex) in zip(axes[1:].ravel(), cases):
    Dnum = derivative.discrete_malliavin_derivative(F, dW, eps=1e-7)
    ax.plot(t, Dex[0], color=plotting.SERIES[0], label="analítica")
    ax.plot(t[::4], Dnum[0, ::4], "o", ms=4, color=plotting.SERIES[1], label="discreta")
    lo, hi = min(Dex.min(), 0.0), max(Dex.max(), 0.0)
    pad = 0.1 * (hi - lo) or 0.5
    ax.set_ylim(lo - pad, hi + pad)
    ax.ticklabel_format(axis="y", useOffset=False)
    ax.set_title(name)
    ax.set_xlabel("t")
    ax.set_ylabel("D_t F")
    ax.legend()
fig.suptitle("Derivada de Malliavin a lo largo del tiempo", fontweight="bold")
fig.tight_layout()
print("Figura:", plotting.save(fig, "02_derivada_malliavin"))
