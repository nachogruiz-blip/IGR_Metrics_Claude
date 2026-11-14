"""09 · Volatilidad estocástica: descomposición de Alòs y skew en tiempo corto (PDF §14.3–14.4).

(a) Sonrisa de rough Bergomi: volatilidad implícita del precio Monte Carlo frente al término de
    Hull–White E[BS(0, X₀, v₀)] y a la fórmula completa de Alòs (Hull–White + corrección).
    Con ρ ≠ 0 Hull–White solo es casi plana; la corrección, construida con la derivada de
    Malliavin D^W σ², reproduce el skew.
(b) Skew ATM frente al vencimiento (log-log): Heston tiende a una constante (PDF T. 14.6(a)),
    rough Bergomi explota como T^{H−1/2} (PDF T. 14.6(b), Ejemplo 14.7).
"""

import matplotlib.pyplot as plt
import matplotlib.ticker  # noqa: F401
import numpy as np

from malliavin import plotting, stochvol
from malliavin.brownian import rng

plotting.setup()
S0, r = 100.0, 0.0
H, eta, xi0, rho = 0.1, 1.9, 0.04, -0.9           # rough Bergomi (Bayer–Friz–Gatheral)
v0, kappa, theta, nu, rho_h = 0.04, 1.5, 0.04, 0.5, -0.7  # Heston

fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))

# (a) Descomposición de Alòs a lo largo de la sonrisa
T = 1.0
p = stochvol.rough_bergomi_paths(T, 400, 30_000, H, eta, xi0, rng(90))
strikes = np.linspace(75, 125, 11)
iv = {"mc": [], "hw": [], "alos": []}
for K in strikes:
    d = stochvol.alos_decomposition_rbergomi(p, S0, K, r, rho, rng(91))
    for key, price in (("mc", d.price), ("hw", d.hull_white), ("alos", d.alos)):
        iv[key].append(stochvol.implied_vol(price, S0, K, T, r))
k = np.log(strikes / S0)
ax = axes[0]
ax.plot(k, iv["mc"], color=plotting.NEUTRAL, lw=3, label="Monte Carlo (precio del modelo)")
ax.plot(k, iv["hw"], "o--", ms=5, color=plotting.SERIES[1], lw=1.5, label="solo Hull–White  E[BS(v₀)]")
ax.plot(k, iv["alos"], "o-", ms=5, color=plotting.SERIES[0], lw=1.5, label="Hull–White + corrección de Alòs")
ax.set_xlabel("log-moneyness k = log(K/S₀)"); ax.set_ylabel("volatilidad implícita")
ax.set_title(f"Rough Bergomi, T = 1: fórmula de Alòs (H = {H}, ρ = {rho})")
ax.legend()

# (b) Skew ATM frente a T
Ts = np.geomspace(0.004, 1.0, 9)
sk_rb = [stochvol.atm_skew(stochvol.rough_bergomi_paths(T, 100, 100_000, H, eta, xi0, rng(92)), S0, r, rho) for T in Ts]
sk_he = [stochvol.atm_skew(stochvol.heston_paths(T, 100, 100_000, v0, kappa, theta, nu, rng(93)), S0, r, rho_h) for T in Ts]
ax = axes[1]
ax.loglog(Ts, -np.array(sk_rb), "o", ms=6, color=plotting.SERIES[0], label="rough Bergomi (MC)")
ax.loglog(Ts, -stochvol.rbergomi_skew_asymptotic(Ts, H, eta, rho), "--", color=plotting.SERIES[0], lw=1.3,
          label=r"asíntota $\propto T^{H-1/2}$")
ax.loglog(Ts, -np.array(sk_he), "s", ms=6, color=plotting.SERIES[1], label="Heston (MC)")
ax.axhline(-stochvol.heston_skew_limit(v0, nu, rho_h), ls="--", color=plotting.SERIES[1], lw=1.3,
           label=r"límite $\rho\nu/(4\sqrt{v_0})$")
ax.set_xlabel("vencimiento T (años)"); ax.set_ylabel("−∂ₖI en el dinero")
ax.set_title("Skew ATM en tiempo corto")
ax.yaxis.set_major_formatter(plt.matplotlib.ticker.FormatStrFormatter("%.1f"))
ax.yaxis.set_minor_formatter(plt.matplotlib.ticker.NullFormatter())
ax.set_yticks([0.3, 0.5, 1.0, 2.0, 3.0])
ax.legend()
fig.tight_layout()
print("Figura:", plotting.save(fig, "09_alos_skew"))

slope = np.polyfit(np.log(Ts[:5]), np.log(-np.array(sk_rb[:5])), 1)[0]
print(f"Pendiente log-log del skew de rough Bergomi (T ≤ 0,05): {slope:.3f}  (teoría H − 1/2 = {H - 0.5})")
print("Sonrisa (k, MC, HW, Alòs):")
for row in zip(k, iv["mc"], iv["hw"], iv["alos"]):
    print("  " + "  ".join(f"{x:7.4f}" for x in row))
