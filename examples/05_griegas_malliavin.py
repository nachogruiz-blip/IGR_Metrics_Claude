"""05 · Griegas: pesos de Malliavin vs diferencias finitas vs pathwise.

(a) Delta de una digital: convergencia con N (Malliavin no necesita derivar el pago).
(b) Error total (sesgo + ruido) de delta/gamma digital frente al tamaño del bump h.
(c) Delta de una digital asiática con el peso de Malliavin.
"""

import matplotlib.pyplot as plt
import numpy as np

from malliavin import bs, greeks, plotting
from malliavin.brownian import TimeGrid, rng

plotting.setup()
S0, K, T, r, sigma = 100.0, 100.0, 1.0, 0.03, 0.2
WT = rng(31).standard_normal(400_000) * np.sqrt(T)
dig = greeks.digital_payoff(K)
ref = bs.digital_greeks(S0, K, T, r, sigma)

fig, axes = plt.subplots(1, 3, figsize=(14, 4.2))
ax = axes[0]
Ns = np.unique(np.logspace(3, np.log10(WT.size), 15).astype(int))
for i, (lab, fn) in enumerate([
    ("Malliavin", lambda w: greeks.greeks_malliavin(dig, w, S0, T, r, sigma)["delta"]),
    ("Dif. finitas h=1%", lambda w: greeks.greeks_finite_difference(dig, w, S0, T, r, sigma, h=1e-2)["delta"]),
]):
    est = [fn(WT[:n]) for n in Ns]
    m = np.array([e.value for e in est]); se = np.array([e.stderr for e in est])
    ax.plot(Ns, m, color=plotting.SERIES[i], label=lab)
    ax.fill_between(Ns, m - 1.96 * se, m + 1.96 * se, color=plotting.SERIES[i], alpha=0.15, lw=0)
ax.axhline(ref["delta"], color=plotting.NEUTRAL, ls="--", lw=1, label="Black–Scholes")
ax.set_xscale("log"); ax.set_xlabel("N"); ax.set_title("Delta digital: convergencia (IC 95%)"); ax.legend()

ax = axes[1]
hs = np.logspace(-3.5, -0.5, 14)
total = lambda e, ref_g: np.hypot(e.value - ref_g, e.stderr) / abs(ref_g)
for i, g in enumerate(["delta", "gamma"]):
    fd = [total(greeks.greeks_finite_difference(dig, WT, S0, T, r, sigma, h=h)[g], ref[g]) for h in hs]
    ml = total(greeks.greeks_malliavin(dig, WT, S0, T, r, sigma)[g], ref[g])
    ax.loglog(hs, fd, "o-", color=plotting.SERIES[i], label=f"{g} · dif. finitas")
    ax.axhline(ml, color=plotting.SERIES[i], ls="--", lw=1.2, label=f"{g} · Malliavin")
ax.set_xlabel("bump relativo h"); ax.set_ylabel("error relativo √(sesgo² + ee²)  (N = 4·10⁵)")
ax.set_title("Digital: h pequeño → ruido, h grande → sesgo"); ax.legend()

ax = axes[2]
grid = TimeGrid(T, 50)
adig = greeks.digital_payoff(K)
Ns2 = [2_000, 5_000, 10_000, 25_000, 50_000, 100_000, 200_000]
for i, (lab, fn) in enumerate([
    ("Malliavin", greeks.asian_delta_malliavin),
    ("Dif. finitas h=1%", greeks.asian_delta_fd),
]):
    est = [fn(adig, S0, T, r, sigma, grid, n, seed=40 + i) for n in Ns2]
    m = np.array([e.value for e in est]); se = np.array([e.stderr for e in est])
    ax.plot(Ns2, m, "o-", ms=4, color=plotting.SERIES[i], label=lab)
    ax.fill_between(Ns2, m - 1.96 * se, m + 1.96 * se, color=plotting.SERIES[i], alpha=0.15, lw=0)
ax.set_xscale("log"); ax.set_xlabel("N"); ax.set_title("Delta de digital asiática  1{A > K}"); ax.legend()
fig.tight_layout()
print("Figura:", plotting.save(fig, "05_griegas_malliavin"))

print("\nTabla (N = 4·10⁵, digital ATM):")
ml = greeks.greeks_malliavin(dig, WT, S0, T, r, sigma)
fd = greeks.greeks_finite_difference(dig, WT, S0, T, r, sigma, h=1e-2)
print(f"{'griega':8s}{'BS':>10s}{'Malliavin':>22s}{'Dif. finitas':>22s}")
for g in ("delta", "gamma", "vega", "rho"):
    print(f"{g:8s}{ref[g]:10.5f}{ml[g].value:12.5f} ± {1.96*ml[g].stderr:.5f}{fd[g].value:12.5f} ± {1.96*fd[g].stderr:.5f}")
