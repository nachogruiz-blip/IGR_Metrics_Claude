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
| Densidad | p_F(x) = E[1_{F>x} δ(DF/‖DF‖²)]  (guía T. 10.1) |
| Localización | Δ = E[Φ_reg'(F)G] + E[Φ_sing(F)π]  (guía §12.6) |
| Bismut–Elworthy–Li | ∂_x E[Φ(X_T)] = E[Φ(X_T)(1/T)∫σ^{-1}(X_t)Y_t dW_t]  (guía T. 12.3) |
| Esperanza condicional | E[Φ(G)\|F=x] = E[Φ(G)1_{F>x}δ(u)]/E[1_{F>x}δ(u)], ⟨DF,u⟩=1, ⟨DG,u⟩=0  (guía T. 14.1) |
| Cobertura | ϕ_t = E_Q[D̃_t H̃ \| F_t]/(σ_t S̃_t)  (guía T. 13.1) |
| Alòs | V_t = E_t[BS(t,X_t,v_t)] + (ρ/2) E_t∫ e^{-r(s-t)} H(s,X_s,v_s) Λ_s ds  (guía T. 14.5, pendiente de implementar) |

Demostraciones: guía PDF (`docs/pdf/`), apéndice A (formulario). Compañero numérico: `latex/main.tex`. Implementación: `docs/guia_libreria.md`.
