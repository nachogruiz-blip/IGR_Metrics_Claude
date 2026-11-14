"""01 · Caos de Wiener: aproximación de pagos por polinomios de Hermite.

Muestra cómo f(W_T) se descompone en caos de orden creciente y qué parte de la
varianza aporta cada uno. Una digital (discontinua) concentra energía en caos altos.
"""

import matplotlib.pyplot as plt
import numpy as np

from malliavin import chaos, plotting

plotting.setup()
T = 1.0
w = np.linspace(-3, 3, 400)
payoffs = {
    "Call (W_T − 0)⁺": lambda x: np.maximum(x, 0.0),
    "Digital 1{W_T > 0}": lambda x: (x > 0).astype(float),
}

fig, axes = plt.subplots(2, 2, figsize=(10, 7))
for col, (name, f) in enumerate(payoffs.items()):
    a = chaos.chaos_coefficients(f, T, 25)
    ax = axes[0, col]
    ax.plot(w, f(w), color=plotting.NEUTRAL, lw=2.5, label="pago exacto")
    for i, n in enumerate([1, 3, 7, 25]):
        ax.plot(w, chaos.chaos_truncation(a, w, T, n), color=plotting.SERIES[i], label=f"hasta caos {n}")
    ax.set_title(name)
    ax.set_xlabel("W_T")
    ax.legend()

    e = chaos.chaos_energy(a)[1:]
    ax = axes[1, col]
    ax.bar(np.arange(1, len(e) + 1), e / e.sum(), color=plotting.SERIES[0], width=0.8)
    ax.set_title(f"{name}: % de varianza por caos")
    ax.set_xlabel("orden n")
    ax.set_ylabel("n!·a_n² / Var(F)")

fig.suptitle("Descomposición en caos de Wiener", fontweight="bold")
fig.tight_layout()
print("Figura:", plotting.save(fig, "01_caos_de_wiener"))
