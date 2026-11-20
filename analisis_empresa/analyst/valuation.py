"""Valoración: coste de capital (CAPM/WACC), DCF en dos etapas, DCF inverso (qué crecimiento
descuenta el precio), P/VC justificado para financieras, múltiplos y consenso de analistas.

Fórmulas:
- Coste del capital: kₑ = r_f + β·PRM (prima de riesgo de mercado ``ERP``).
- WACC = E/(D+E)·kₑ + D/(D+E)·k_d·(1 − t).
- DCF: FCF_t = FCF₀·∏(1+g_s), con g = g₁ los años 1–5 y un descenso lineal hasta g_T en los
  años 6–10; valor terminal de Gordon FCF₁₀·(1+g_T)/(WACC − g_T). Con g₁ = g_T se reduce a
  FCF₀·(1+g)/(WACC − g) (test).
- Financieras: P/VC justificado = (ROE − g)/(kₑ − g) ⇒ valor = VC por acción × P/VC justificado.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import brentq

from .common import Item, Pillar, finite, piecewise, ramp
from .statements import cagr, is_financial, ratios

ERP = 0.055               # prima de riesgo del mercado de acciones
TAX = 0.25
STAGE1, STAGE2 = 5, 5     # años de crecimiento explícito y de convergencia


def terminal_growth(currency: str, rf: float) -> float:
    """Crecimiento a perpetuidad: ~ inflación + crecimiento real largo, nunca por encima de r_f."""
    base = 0.025 if currency == "USD" else 0.02
    return float(min(base, max(rf - 0.005, 0.01)))


def cost_of_equity(rf: float, beta: float) -> float:
    return rf + float(np.clip(beta if finite(beta) else 1.0, 0.5, 2.0)) * ERP


def wacc(rf: float, beta: float, market_cap: float, debt: float, interest: float) -> tuple[float, float]:
    """(WACC, kₑ). k_d = intereses/deuda acotado a [r_f + 0.5 %, r_f + 8 %]."""
    ke = cost_of_equity(rf, beta)
    debt = debt if finite(debt) and debt > 0 else 0.0
    if debt == 0 or not finite(market_cap) or market_cap <= 0:
        return ke, ke
    kd = abs(interest) / debt if finite(interest) and interest else rf + 0.02
    kd = float(np.clip(kd, rf + 0.005, rf + 0.08))
    e_w = market_cap / (market_cap + debt)
    return float(e_w * ke + (1 - e_w) * kd * (1 - TAX)), ke


def growth_path(g1: float, gT: float) -> np.ndarray:
    """Crecimientos de los años 1..STAGE1+STAGE2: g₁ constante y luego descenso lineal a g_T."""
    fade = np.linspace(g1, gT, STAGE2 + 1)[1:]
    return np.concatenate([np.full(STAGE1, g1), fade])


def dcf_ev(fcf0: float, g1: float, gT: float, rate: float) -> float:
    """Valor presente de los flujos (valor de empresa si ``rate`` = WACC)."""
    if rate <= gT:
        return float("nan")
    g = growth_path(g1, gT)
    flows = fcf0 * np.cumprod(1 + g)
    disc = (1 + rate) ** -np.arange(1, len(g) + 1)
    tv = flows[-1] * (1 + gT) / (rate - gT)
    return float((flows * disc).sum() + tv * disc[-1])


def implied_growth(price: float, shares: float, net_debt: float, fcf0: float, gT: float,
                   rate: float) -> float:
    """DCF inverso: g₁ que hace que el valor por acción iguale el precio (NaN si no hay raíz)."""
    if not (finite(price) and finite(shares) and shares > 0 and fcf0 > 0):
        return float("nan")
    nd = net_debt if finite(net_debt) else 0.0
    f = lambda g: (dcf_ev(fcf0, g, gT, rate) - nd) / shares - price  # noqa: E731
    try:
        return float(brentq(f, -0.5, 1.0))
    except ValueError:
        return float("nan")


@dataclass
class Valuation:
    method: str                    # "DCF (flujo de caja libre)", "P/VC justificado" o ""
    fair_value: float              # por acción
    margin: float                  # valor / precio − 1
    wacc: float
    ke: float
    g1: float
    gT: float
    implied_growth: float
    fcf0: float
    sensitivity: pd.DataFrame      # valor por acción: filas WACC, columnas g_T
    pillar: Pillar
    notes: list[str] = field(default_factory=list)


def _shares(info: dict, income: pd.DataFrame) -> float:
    s = info.get("sharesOutstanding")
    if finite(s) and s > 0:
        return float(s)
    if "shares" in income and income["shares"].notna().any():
        return float(income["shares"].dropna().iloc[-1])
    return float("nan")


def analyze(info: dict, income: pd.DataFrame, balance: pd.DataFrame, cashflow: pd.DataFrame,
            price: float, rf: float, beta: float | None = None) -> Valuation:
    """Valoración completa y pilar «Valoración»."""
    fin = is_financial(info)
    beta = beta if finite(beta) else info.get("beta")
    shares = _shares(info, income)
    mcap = float(info.get("marketCap") or (price * shares if finite(shares) else np.nan))
    r = ratios(income, balance, cashflow) if len(income) else pd.DataFrame()
    last_b = balance.iloc[-1] if len(balance) else pd.Series(dtype=float)
    debt = float(last_b.get("total_debt", np.nan))
    cash = float(last_b.get("cash", np.nan))
    net_debt = (debt if finite(debt) else 0.0) - (cash if finite(cash) else 0.0)
    interest = float(income["interest_expense"].iloc[-1]) if "interest_expense" in income and len(income) else np.nan
    gT = terminal_growth(str(info.get("currency") or ""), rf)
    w, ke = wacc(rf, beta, mcap, debt, interest)
    notes: list[str] = []
    method, fair, g1, ig, fcf0 = "", float("nan"), float("nan"), float("nan"), float("nan")
    sens = pd.DataFrame()

    if fin:
        roe = r["roe"].dropna().tail(3).mean() if "roe" in r else np.nan
        eq = float(last_b.get("equity", np.nan))
        if finite(roe) and finite(eq) and finite(shares) and eq > 0:
            roe = float(np.clip(roe, 0.0, 0.25))
            bvps = eq / shares
            fair = bvps * (roe - gT) / (ke - gT)
            method = "P/VC justificado"
            notes.append(f"Financiera: P/VC justificado = (ROE {roe:.1%} − g {gT:.1%}) / "
                         f"(kₑ {ke:.1%} − g) = {(roe - gT) / (ke - gT):.2f}×; VC/acción {bvps:.2f}.")
            rates = ke + np.array([-0.01, -0.005, 0.0, 0.005, 0.01])
            gs = np.array([gT - 0.01, gT - 0.005, gT, gT + 0.005])
            sens = pd.DataFrame([[bvps * (roe - g) / (k - g) if k > g else np.nan for g in gs]
                                 for k in rates], index=rates, columns=gs)
    else:
        fcf = r["fcf"].dropna().tail(3) if "fcf" in r else pd.Series(dtype=float)
        fcf0 = float(fcf.mean()) if len(fcf) else float("nan")
        if finite(fcf0) and fcf0 > 0 and finite(shares):
            hist = cagr(income["revenue"]) if "revenue" in income else np.nan
            g1 = float(np.clip(hist if finite(hist) else 0.03, -0.03, 0.12))
            fair = (dcf_ev(fcf0, g1, gT, w) - net_debt) / shares
            method = "DCF (flujo de caja libre)"
            ig = implied_growth(price, shares, net_debt, fcf0, gT, w)
            notes.append(f"DCF: FCF base {fcf0 / 1e6:,.0f} M (media de {len(fcf)} ejercicios), "
                         f"g₁ = {g1:.1%} (ventas históricas, acotado a [−3 %, 12 %]) durante "
                         f"{STAGE1} años, convergencia a g_T = {gT:.1%}, WACC = {w:.1%}.")
            if finite(ig):
                notes.append(f"DCF inverso: el precio actual descuenta un crecimiento del FCF de "
                             f"{ig:.1%} anual durante {STAGE1} años (histórico de ventas: {g1:.1%}).")
            rates = w + np.array([-0.01, -0.005, 0.0, 0.005, 0.01])
            gs = np.array([gT - 0.01, gT - 0.005, gT, gT + 0.005])
            sens = pd.DataFrame([[(dcf_ev(fcf0, g1, g, k) - net_debt) / shares for g in gs]
                                 for k in rates], index=rates, columns=gs)
        else:
            notes.append("Flujo de caja libre medio negativo o sin datos: no se hace DCF.")
    margin = fair / price - 1 if finite(fair) and price > 0 else float("nan")
    pillar = _pillar(info, r, price, rf, fin, margin, method, fcf0, mcap)
    return Valuation(method, fair, margin, w, ke, g1, gT, ig, fcf0, sens, pillar, notes)


def _pillar(info, r, price, rf, fin, margin, method, fcf0, mcap) -> Pillar:
    pil = Pillar("Valoración")
    pil.items.append(Item("margin_of_safety", f"Margen de seguridad ({method or 'sin modelo'})",
                          margin, ramp(margin, -0.4, 0.4), "pct",
                          "Valor intrínseco estimado frente al precio; muy sensible a supuestos", 1.2))
    pe = info.get("trailingPE")
    eps = info.get("trailingEps")
    if not finite(pe) and finite(eps) and eps < 0:
        pil.items.append(Item("pe", "PER", float("nan"), -1.0, "x", "Pérdidas: PER no significativo", 1.0))
    else:
        pil.items.append(Item("pe", "PER (últimos 12 meses)", pe,
                              piecewise(pe, [6, 12, 20, 30, 45], [1, 0.6, 0, -0.6, -1]) if finite(pe) and pe > 0 else float("nan"),
                              "x", "", 1.0))
    fpe = info.get("forwardPE")
    pil.items.append(Item("forward_pe", "PER estimado (12 meses vista)", fpe,
                          piecewise(fpe, [6, 12, 20, 30, 45], [1, 0.6, 0, -0.6, -1]) if finite(fpe) and fpe > 0 else float("nan"),
                          "x", "", 0.8))
    if finite(pe) and pe > 0:
        ey = 1 / pe - rf
        pil.items.append(Item("earnings_yield_spread", "Rentabilidad por beneficio − bono", ey,
                              ramp(ey, -0.01, 0.05), "pct",
                              "1/PER menos el tipo sin riesgo: prima que ofrece la acción", 0.8))
    if not fin:
        ev = info.get("enterpriseToEbitda")
        pil.items.append(Item("ev_ebitda", "VE / EBITDA", ev,
                              piecewise(ev, [4, 8, 12, 18, 25], [1, 0.5, 0, -0.6, -1]) if finite(ev) and ev > 0 else float("nan"),
                              "x", "", 0.8))
        fy = fcf0 / mcap if finite(fcf0) and finite(mcap) and mcap > 0 else float("nan")
        pil.items.append(Item("fcf_yield", "Rentabilidad por flujo de caja libre", fy,
                              piecewise(fy, [0.0, 0.03, 0.06, 0.10], [-1, 0, 0.6, 1]), "pct0",
                              "FCF medio / capitalización", 1.0))
    else:
        pb = info.get("priceToBook")
        pil.items.append(Item("pb", "Precio / valor contable", pb,
                              piecewise(pb, [0.5, 1.0, 1.5, 2.5], [1, 0.4, -0.2, -1]), "x",
                              "En banca, P/VC frente al ROE es el múltiplo clave", 0.8))
    peg = info.get("trailingPegRatio") or info.get("pegRatio")
    pil.items.append(Item("peg", "PEG (PER / crecimiento)", peg,
                          piecewise(peg, [0.5, 1.0, 1.5, 2.5], [1, 0.5, -0.2, -1]) if finite(peg) and peg > 0 else float("nan"),
                          "num", "< 1: crecimiento barato", 0.5))
    dy = (info.get("dividendRate") or 0) / price if price > 0 else float("nan")
    pil.items.append(Item("dividend_yield", "Rentabilidad por dividendo", dy,
                          piecewise(dy, [0.0, 0.02, 0.05, 0.08], [-0.2, 0.2, 0.6, 0.3]), "pct0",
                          "> 8 % a menudo anticipa un recorte", 0.3))
    tgt = info.get("targetMeanPrice")
    up = tgt / price - 1 if finite(tgt) and price > 0 else float("nan")
    n = info.get("numberOfAnalystOpinions") or 0
    pil.items.append(Item("analyst_upside", f"Potencial según analistas ({n} opiniones)", up,
                          ramp(up, -0.10, 0.30), "pct", "Precio objetivo medio / precio − 1",
                          0.7 if n >= 3 else 0.0))
    rec = info.get("recommendationMean")
    pil.items.append(Item("analyst_rec", "Recomendación media (1 compra fuerte – 5 venta)", rec,
                          piecewise(rec, [1.5, 2.5, 3.5], [1, 0, -1]), "num", "",
                          0.4 if n >= 3 else 0.0))
    return pil
