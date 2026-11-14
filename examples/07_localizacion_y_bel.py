"""07 · Localización y Bismut–Elworthy–Li (PDF §12.4, §12.6–12.7).

(a) Reproduce la tabla de §12.7: delta digital con 50 repeticiones de N = 10⁵.
(b) Descomposición Φ = Φ_reg + Φ_sing usada en la localización.
(c) Delta digital en un modelo CEV (sin fórmula cerrada) por BEL vs diferencias finitas.
"""

import matplotlib.pyplot as plt
import numpy as np

from malliavin import bs, greeks, plotting
from malliavin.brownian import TimeGrid, rng

plotting.setup()
S0, K, T, r, sigma = 100.0, 100.0, 1.0, 0.05, 0.2
dig = greeks.digital_payoff(K)
reg, regp = greeks.sigmoid_regularization(K, width=5.0)
exact = bs.digital_greeks(S0, K, T, r, sigma)["delta"]

estimators = {
    "Dif. finitas h = 1": lambda w: greeks.greeks_finite_difference(dig, w, S0, T, r, sigma, h=1 / S0)["delta"].value,
    "Dif. finitas h = 0,1": lambda w: greeks.greeks_finite_difference(dig, w, S0, T, r, sigma, h=0.1 / S0)["delta"].value,
    "Malliavin": lambda w: greeks.greeks_malliavin(dig, w, S0, T, r, sigma)["delta"].value,
    "Malliavin localizado": lambda w: greeks.localized_delta(dig, reg, regp, w, S0, T, r, sigma).value,
}
gen = rng(70)
samples = {k: [] for k in estimators}
for _ in range(50):
    w = gen.standard_normal(100_000) * np.sqrt(T)
    for k, f in estimators.items():
        samples[k].append(f(w))

print(f"Delta exacta = {exact:.6f}")
print(f"{'Estimador':24s}{'Media':>10s}{'Desv. típica':>14s}")
for k, v in samples.items():
    print(f"{k:24s}{np.mean(v):10.6f}{np.std(v, ddof=1):14.2e}")

fig, axes = plt.subplots(1, 3, figsize=(14, 4.2))
ax = axes[0]
names = list(samples)
ax.boxplot([samples[k] for k in names], orientation="horizontal", widths=0.5,
           medianprops={"color": plotting.SERIES[1]}, boxprops={"color": plotting.TEXT_2},
           whiskerprops={"color": plotting.TEXT_2}, capprops={"color": plotting.TEXT_2}, flierprops={"markersize": 3})
ax.set_yticks(range(1, len(names) + 1), names)
ax.axvline(exact, color=plotting.SERIES[0], lw=1.2, ls="--", label="exacta")
ax.set_title("Delta digital: 50 repeticiones, N = 10⁵")
ax.legend(loc="lower right")

ax = axes[1]
s = np.linspace(60, 140, 400)
ax.plot(s, dig(s), color=plotting.NEUTRAL, lw=2.5, label="Φ = 1{S > K}")
ax.plot(s, reg(s), color=plotting.SERIES[0], label="Φ_reg (pathwise)")
ax.plot(s, dig(s) - reg(s), color=plotting.SERIES[1], label="Φ_sing (peso de Malliavin)")
ax.set_xlabel("S_T"); ax.set_title("Localización: Φ = Φ_reg + Φ_sing"); ax.legend()

ax = axes[2]
beta = 0.5
s0 = sigma * S0 ** (1 - beta)
b, db = (lambda x: r * x), (lambda x: r + 0 * x)
sg = lambda x: s0 * np.maximum(x, 1e-8) ** beta
dsg = lambda x: s0 * beta * np.maximum(x, 1e-8) ** (beta - 1)
grid = TimeGrid(T, 50)
Ns = [5_000, 10_000, 25_000, 50_000, 100_000, 200_000]
for i, (lab, fn) in enumerate([
    ("Bismut–Elworthy–Li", lambda n: greeks.bel_delta(dig, b, db, sg, dsg, S0, T, r, grid, n, seed=71)),
    ("Dif. finitas h = 1%", lambda n: greeks.euler_fd_delta(dig, b, sg, S0, T, r, grid, n, seed=72)),
]):
    est = [fn(n) for n in Ns]
    m = np.array([e.value for e in est]); se = np.array([e.stderr for e in est])
    ax.plot(Ns, m, "o-", ms=4, color=plotting.SERIES[i], label=lab)
    ax.fill_between(Ns, m - 1.96 * se, m + 1.96 * se, color=plotting.SERIES[i], alpha=0.15, lw=0)
ax.set_xscale("log"); ax.set_xlabel("N")
ax.set_title("Delta digital en CEV (β = 0,5)"); ax.legend()
fig.tight_layout()
print("Figura:", plotting.save(fig, "07_localizacion_y_bel"))
