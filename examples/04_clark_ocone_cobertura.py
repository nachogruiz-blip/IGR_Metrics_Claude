"""04 · Clark–Ocone: replicar un pago con E[D_tF | F_t] como integrando.

(a) F = W_T³: trayectorias de M_t = E[F] + ∫ φ dW frente al pago final.
(b) Call europea: la fórmula recupera la cartera delta de Black–Scholes;
    error de replicación al refinar el rebalanceo.
"""

import matplotlib.pyplot as plt
import numpy as np

from malliavin import bs, clark_ocone, plotting
from malliavin.brownian import TimeGrid, brownian_increments, gbm_from_brownian, paths_from_increments, rng

plotting.setup()
S0, K, T, r, sigma = 100.0, 100.0, 1.0, 0.03, 0.2

fig, axes = plt.subplots(1, 3, figsize=(14, 4.2))

grid = TimeGrid(T, 500)
dW = brownian_increments(grid, 4, rng(21))
W = paths_from_increments(dW)
M = clark_ocone.reconstruct(0.0, clark_ocone.integrand_cubic(W, grid), dW)
ax = axes[0]
for i in range(4):
    ax.plot(grid.t, M[i], color=plotting.SERIES[i], lw=1.5)
    ax.scatter([T], [W[i, -1] ** 3], s=50, facecolor="none", edgecolor=plotting.SERIES[i], lw=2)
ax.set_title("F = W_T³ :  M_t = ∫₀ᵗ 3(W_s² + T − s) dW_s")
ax.set_xlabel("t")
ax.text(0.02, 0.95, "círculos = W_T³ exacto", transform=ax.transAxes, color=plotting.TEXT_2, va="top")

dW = brownian_increments(grid, 3, rng(22))
W = paths_from_increments(dW)
S = gbm_from_brownian(W, grid, S0, r, sigma)
phi = clark_ocone.integrand_call(S, grid, K, r, sigma)
delta = phi / (sigma * np.exp(-r * grid.t[:-1]) * S[:, :-1])
ax = axes[1]
for i in range(3):
    ax.plot(grid.t[:-1], delta[i], color=plotting.SERIES[i], lw=1.5, label=f"S_T = {S[i, -1]:.0f}")
ax.set_title("Δ_t = E[D_tF|F_t] / (σ e^{−rt} S_t)")
ax.set_xlabel("t")
ax.set_ylabel("acciones en cartera")
ax.legend()

ax = axes[2]
steps = [10, 25, 50, 100, 250, 500, 1000, 2000]
rmse = []
for n in steps:
    g = TimeGrid(T, n)
    d = brownian_increments(g, 4000, rng(23))
    Sx = gbm_from_brownian(paths_from_increments(d), g, S0, r, sigma)
    Mx = clark_ocone.reconstruct(bs.call_price(S0, K, T, r, sigma), clark_ocone.integrand_call(Sx, g, K, r, sigma), d)
    rmse.append(np.sqrt(np.mean((Mx[:, -1] - np.exp(-r * T) * np.maximum(Sx[:, -1] - K, 0)) ** 2)))
ax.loglog(steps, rmse, "o-", color=plotting.SERIES[0], label="error de replicación (RMSE)")
ax.loglog(steps, rmse[0] * np.sqrt(steps[0] / np.array(steps)), "--", color=plotting.NEUTRAL, lw=1, label="pendiente −1/2")
ax.set_title("Call: error de cobertura discreta")
ax.set_xlabel("número de rebalanceos")
ax.legend()
fig.tight_layout()
print("Figura:", plotting.save(fig, "04_clark_ocone_cobertura"))
