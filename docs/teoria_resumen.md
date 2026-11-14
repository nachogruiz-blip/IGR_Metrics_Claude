# Resumen de teoría (chuleta)

Notación: W browniano en [0,T], H = L²[0,T], W(h) = ∫h dW.

| Objeto | Definición / resultado clave |
|---|---|
| Caos de Wiener | F = Σ I_n(f_n), E[F²] = Σ n!‖f_n‖² ; para f(W_T): F = Σ a_n He_n(W_T/√T) |
| Derivada D | D f(W(h₁),…,W(h_n)) = Σ ∂_i f · h_i ; regla de la cadena ; D_t I_n(f_n) = n I_{n−1}(f_n(·,t)) |
| D^{1,2} | ‖F‖²_{1,2} = E[F²] + E‖DF‖²_H < ∞ ⟺ Σ n·n!‖f_n‖² < ∞ |
| Divergencia δ | E⟨DF,u⟩ = E[F δ(u)] ; δ(h) = W(h) ; δ(u) = ∫u dW si u adaptado ; δ(Gu) = Gδ(u) − ⟨DG,u⟩ |
| Clark–Ocone | F = E[F] + ∫ E[D_tF \| F_t] dW_t |
| Peso de IBP | E[φ'(F)G] = E[φ(F) δ(G u / ⟨DF,u⟩)] |
| Griegas BS | π_Δ = W_T/(S₀σT), π_V = W_T²/(σT) − W_T − 1/σ, π_Γ = π_V/(S₀²σT), π_ρ = W_T/σ − T |
| Densidad | p_F(x) = E[1_{F>x} δ(DF/‖DF‖²)] |

Detalle y demostraciones: `latex/main.tex`. Implementación: `docs/guia_libreria.md`.
