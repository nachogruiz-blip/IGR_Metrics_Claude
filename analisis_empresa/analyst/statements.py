"""Análisis de los estados financieros: ratios por ejercicio, crecimiento, F-score de Piotroski,
Z-score de Altman y pilares «Balance y solvencia» y «Rentabilidad y crecimiento».

Entrada: ``income``, ``balance`` y ``cashflow`` normalizados por ``data.normalize_statement``
(una fila por ejercicio, ascendente). Todas las cifras en la moneda de la empresa; ratios en
fracciones.

Bancos y aseguradoras (``is_financial``): el circulante, la deuda/EBITDA y el Z de Altman no
tienen sentido (la deuda es su materia prima), así que se excluyen y se evalúan ROE, ROA,
margen y crecimiento.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .common import Item, Pillar, finite, piecewise, ramp

FINANCIAL_SECTORS = {"Financial Services", "Financial"}
FINANCIAL_WORDS = ("bank", "insurance", "banco", "seguro", "capital markets", "credit services")


def is_financial(info: dict) -> bool:
    ind = str(info.get("industry") or "").lower()
    return info.get("sector") in FINANCIAL_SECTORS or any(w in ind for w in FINANCIAL_WORDS)


def _div(a, b):
    """División elemento a elemento con NaN si el denominador es 0 o falta."""
    b = b.where(b != 0) if isinstance(b, pd.Series) else (b if b else np.nan)
    return a / b


def ratios(income: pd.DataFrame, balance: pd.DataFrame, cashflow: pd.DataFrame) -> pd.DataFrame:
    """Ratios por ejercicio (filas = años). Rentabilidades sobre saldos medios cuando hay año
    anterior; si no, sobre el saldo de cierre."""
    idx = income.index.union(balance.index).union(cashflow.index)
    i, b, c = (df.reindex(idx) for df in (income, balance, cashflow))

    def avg(s: pd.Series) -> pd.Series:
        return ((s + s.shift(1)) / 2).fillna(s)

    tax_rate = _div(i["tax_provision"], i["pretax_income"]).clip(0.0, 0.40).fillna(0.25)
    invested = b["equity"] + b["total_debt"].fillna(0) - b["cash"].fillna(0)
    fcf = c["fcf"].fillna(c["ocf"] + c["capex"])
    net_debt = b["total_debt"] - b["cash"]
    out = pd.DataFrame(index=idx)
    out["revenue_growth"] = i["revenue"].pct_change()
    out["eps_growth"] = _div(i["eps"] - i["eps"].shift(1), i["eps"].shift(1).abs())
    out["gross_margin"] = _div(i["gross_profit"], i["revenue"])
    out["ebit_margin"] = _div(i["ebit"], i["revenue"])
    out["net_margin"] = _div(i["net_income"], i["revenue"])
    out["fcf_margin"] = _div(fcf, i["revenue"])
    out["roe"] = _div(i["net_income"], avg(b["equity"]))
    out["roa"] = _div(i["net_income"], avg(b["total_assets"]))
    out["roic"] = _div(i["ebit"] * (1 - tax_rate), avg(invested))
    out["asset_turnover"] = _div(i["revenue"], avg(b["total_assets"]))
    out["current_ratio"] = _div(b["current_assets"], b["current_liabilities"])
    out["quick_ratio"] = _div(b["current_assets"] - b["inventory"].fillna(0), b["current_liabilities"])
    out["debt_to_equity"] = _div(b["total_debt"], b["equity"])
    out["net_debt_ebitda"] = _div(net_debt, i["ebitda"].where(i["ebitda"] > 0))
    out["interest_coverage"] = _div(i["ebit"], i["interest_expense"].abs())
    out["equity_ratio"] = _div(b["equity"], b["total_assets"])
    out["ocf_to_net_income"] = _div(c["ocf"], i["net_income"].where(i["net_income"] > 0))
    out["accruals"] = _div(i["net_income"] - c["ocf"], avg(b["total_assets"]))
    out["capex_to_revenue"] = _div(c["capex"].abs(), i["revenue"])
    out["payout"] = _div(c["dividends"].abs(), i["net_income"].where(i["net_income"] > 0))
    out["share_change"] = i["shares"].pct_change()
    out["fcf"] = fcf
    out["net_debt"] = net_debt
    return out


def cagr(s: pd.Series) -> float:
    """Crecimiento anual compuesto entre el primer y el último dato positivos."""
    s = s.dropna()
    if len(s) < 2 or s.iloc[0] <= 0 or s.iloc[-1] <= 0:
        return float("nan")
    years = (s.index[-1] - s.index[0]).days / 365.25
    return float((s.iloc[-1] / s.iloc[0]) ** (1 / max(years, 1e-9)) - 1)


# --------------------------------------------------------------------------- puntuaciones clásicas
@dataclass
class Piotroski:
    score: int              # 0–9
    available: int          # pruebas con dato
    tests: dict[str, bool | None]


PIOTROSKI_LABELS = {
    "roa_pos": "ROA > 0", "ocf_pos": "Flujo operativo > 0", "roa_up": "ROA mejora",
    "accruals": "Flujo operativo > beneficio", "leverage_down": "Baja la deuda a largo / activo",
    "liquidity_up": "Mejora el ratio de liquidez", "no_dilution": "No amplía capital",
    "margin_up": "Mejora el margen bruto", "turnover_up": "Mejora la rotación de activos",
}


def piotroski(income: pd.DataFrame, balance: pd.DataFrame, cashflow: pd.DataFrame) -> Piotroski:
    """F-score de Piotroski (2000): nueve pruebas binarias sobre los dos últimos ejercicios.

    8–9 = fortaleza; 0–2 = debilidad. Una prueba sin dato cuenta como no superada pero se
    informa en ``available``.
    """
    idx = income.index.intersection(balance.index).intersection(cashflow.index)
    tests: dict[str, bool | None] = {k: None for k in PIOTROSKI_LABELS}
    if len(idx) < 2:
        return Piotroski(0, 0, tests)
    i, b, c = income.loc[idx], balance.loc[idx], cashflow.loc[idx]
    t, p = idx[-1], idx[-2]

    def cmp(x, y, greater=True):
        if not (finite(x) and finite(y)):
            return None
        return bool(x > y) if greater else bool(x < y)

    roa = i["net_income"] / b["total_assets"]
    lev = b["long_term_debt"].fillna(b["total_debt"]) / b["total_assets"]
    cr = b["current_assets"] / b["current_liabilities"]
    gm = i["gross_profit"] / i["revenue"]
    turn = i["revenue"] / b["total_assets"]
    shares = b["shares_out"].fillna(i["shares"])
    tests["roa_pos"] = cmp(roa[t], 0.0)
    tests["ocf_pos"] = cmp(c.at[t, "ocf"], 0.0)
    tests["roa_up"] = cmp(roa[t], roa[p])
    tests["accruals"] = cmp(c.at[t, "ocf"] / b.at[t, "total_assets"], roa[t])
    tests["leverage_down"] = cmp(lev[t], lev[p], greater=False) if lev[t] != lev[p] else True
    tests["liquidity_up"] = cmp(cr[t], cr[p])
    tests["no_dilution"] = None if not (finite(shares[t]) and finite(shares[p])) else \
        bool(shares[t] <= shares[p] * 1.005)
    tests["margin_up"] = cmp(gm[t], gm[p])
    tests["turnover_up"] = cmp(turn[t], turn[p])
    avail = sum(v is not None for v in tests.values())
    return Piotroski(sum(bool(v) for v in tests.values()), avail, tests)


def altman_z(income: pd.DataFrame, balance: pd.DataFrame, market_cap: float) -> float:
    """Z-score de Altman (1968) para empresas no financieras cotizadas, último ejercicio:

    Z = 1.2·CC/A + 1.4·BR/A + 3.3·EBIT/A + 0.6·Cap.bursátil/Pasivo + 1.0·Ventas/A

    > 2.99 zona segura; 1.81–2.99 zona gris; < 1.81 riesgo de insolvencia.
    """
    if income.empty or balance.empty or not finite(market_cap):
        return float("nan")
    i, b = income.iloc[-1], balance.iloc[-1]
    ta, tl = b["total_assets"], b["total_liabilities"]
    if not (finite(ta) and ta > 0 and finite(tl) and tl > 0):
        return float("nan")
    wc = b["current_assets"] - b["current_liabilities"]
    re = b["retained_earnings"] if finite(b["retained_earnings"]) else 0.0
    parts = [1.2 * wc / ta, 1.4 * re / ta, 3.3 * i["ebit"] / ta, 0.6 * market_cap / tl,
             1.0 * i["revenue"] / ta]
    return float(sum(parts)) if all(finite(x) for x in parts) else float("nan")


def altman_zone(z: float) -> str:
    if not finite(z):
        return "sin dato"
    return "segura" if z > 2.99 else "gris" if z >= 1.81 else "de riesgo de insolvencia"


# --------------------------------------------------------------------------- pilares
def _last(r: pd.DataFrame, key: str) -> float:
    """Valor del último ejercicio (NaN si falta: no se arrastra un dato antiguo)."""
    return float(r[key].iloc[-1]) if key in r and len(r) else float("nan")


def _trend(r: pd.DataFrame, key: str) -> float:
    """Variación del ratio entre el primer y el último ejercicio disponibles."""
    s = r[key].dropna() if key in r else pd.Series(dtype=float)
    return float(s.iloc[-1] - s.iloc[0]) if len(s) >= 2 else float("nan")


def balance_pillar(income, balance, cashflow, info: dict) -> Pillar:
    """Solvencia y liquidez: deuda neta/EBITDA, cobertura de intereses, liquidez, autonomía
    financiera, Altman y Piotroski."""
    r = ratios(income, balance, cashflow)
    fin = is_financial(info)
    pil = Pillar("Balance y solvencia")
    pio = piotroski(income, balance, cashflow)
    if not fin:
        nde = _last(r, "net_debt_ebitda")
        nd = _last(r, "net_debt")
        if finite(nd) and nd < 0:
            pil.items.append(Item("net_debt_ebitda", "Deuda neta / EBITDA", nde, 1.0, "x",
                                  "Caja neta: más caja que deuda", 1.5))
        else:
            pil.items.append(Item("net_debt_ebitda", "Deuda neta / EBITDA", nde,
                                  piecewise(nde, [0.5, 1.5, 3.0, 4.5], [1, 0.5, -0.3, -1]), "x",
                                  "< 1.5× holgado; > 3× exigente; > 4.5× peligroso", 1.5))
        cov = _last(r, "interest_coverage")
        pil.items.append(Item("interest_coverage", "Cobertura de intereses (EBIT/intereses)", cov,
                              piecewise(cov, [1.0, 3.0, 8.0, 15.0], [-1, -0.2, 0.6, 1]), "x",
                              "< 3× vigilar; < 1.5× no cubre los intereses con holgura", 1.0))
        cr = _last(r, "current_ratio")
        pil.items.append(Item("current_ratio", "Liquidez (activo corriente / pasivo corriente)", cr,
                              piecewise(cr, [0.6, 1.0, 1.5, 2.5], [-1, -0.2, 0.6, 1]), "num",
                              "< 1: el pasivo a corto supera al activo a corto", 0.7))
        z = altman_z(income, balance, float(info.get("marketCap") or np.nan))
        pil.items.append(Item("altman_z", "Z de Altman", z,
                              piecewise(z, [1.2, 1.81, 2.99, 4.5], [-1, -0.4, 0.4, 1]), "num",
                              f"Zona {altman_zone(z)}", 1.0))
    eq = _last(r, "equity_ratio")
    pil.items.append(Item("equity_ratio", "Patrimonio / activo", eq,
                          ramp(eq, 0.04, 0.10) if fin else piecewise(eq, [0.1, 0.3, 0.5], [-1, 0.2, 1]),
                          "pct0", "Colchón de capital propio", 0.8))
    if pio.available >= 6:
        pil.items.append(Item("piotroski", "F-score de Piotroski (0–9)", pio.score,
                              ramp(pio.score, 2, 8), "int",
                              f"{pio.available} de 9 pruebas con dato; ≥ 7 fuerte, ≤ 3 débil", 1.0))
    q = _last(r, "ocf_to_net_income")
    pil.items.append(Item("ocf_to_net_income", "Calidad del beneficio (flujo operativo / beneficio)",
                          q, piecewise(q, [0.5, 0.8, 1.0, 1.3], [-1, -0.2, 0.4, 1]), "x",
                          "< 0.8: el beneficio contable no se convierte en caja", 0.0 if fin else 0.8))
    if fin:
        pil.notes.append("Entidad financiera: no se evalúan liquidez, deuda/EBITDA ni Altman.")
    dte = _trend(r, "net_debt_ebitda")
    if finite(dte) and not fin:
        pil.notes.append(f"Deuda neta/EBITDA {'sube' if dte > 0 else 'baja'} {abs(dte):.1f}× "
                         f"en el periodo analizado.")
    return pil


def profitability_pillar(income, balance, cashflow, info: dict) -> Pillar:
    """Rentabilidad (ROE/ROIC, márgenes), crecimiento (ventas, BPA, FCF) y su tendencia."""
    r = ratios(income, balance, cashflow)
    fin = is_financial(info)
    pil = Pillar("Rentabilidad y crecimiento")
    roe = _last(r, "roe")
    pil.items.append(Item("roe", "ROE", roe, piecewise(roe, [0.0, 0.08, 0.15, 0.25], [-1, -0.2, 0.6, 1]),
                          "pct0", "Beneficio sobre fondos propios", 1.0))
    if fin:
        roa = _last(r, "roa")
        pil.items.append(Item("roa", "ROA", roa, piecewise(roa, [0.0, 0.006, 0.012], [-1, 0, 1]),
                              "pct0", "En banca, ROA > 1 % es bueno", 1.0))
    else:
        roic = _last(r, "roic")
        pil.items.append(Item("roic", "ROIC", roic,
                              piecewise(roic, [0.0, 0.07, 0.12, 0.20], [-1, -0.1, 0.6, 1]), "pct0",
                              "Rentabilidad del capital invertido; > 10–12 % suele superar su coste", 1.2))
        em = _last(r, "ebit_margin")
        pil.items.append(Item("ebit_margin", "Margen EBIT", em,
                              piecewise(em, [0.0, 0.05, 0.15, 0.30], [-1, -0.2, 0.6, 1]), "pct0", "", 0.8))
        fm = _last(r, "fcf_margin")
        pil.items.append(Item("fcf_margin", "Margen de flujo de caja libre", fm,
                              piecewise(fm, [-0.02, 0.03, 0.10, 0.20], [-1, 0, 0.6, 1]), "pct0", "", 0.8))
    nm_tr = _trend(r, "net_margin")
    pil.items.append(Item("margin_trend", "Tendencia del margen neto", nm_tr, ramp(nm_tr, -0.04, 0.04),
                          "pct", "Variación en el periodo (puntos)", 0.7))
    g = cagr(income["revenue"]) if "revenue" in income else float("nan")
    pil.items.append(Item("revenue_cagr", "Crecimiento anual de ventas (TACC)", g,
                          piecewise(g, [-0.05, 0.0, 0.05, 0.15], [-1, -0.3, 0.4, 1]), "pct", "", 1.0))
    eg = cagr(income["net_income"]) if "net_income" in income else float("nan")
    if not finite(eg) and len(income["net_income"].dropna()) >= 2:
        ni = income["net_income"].dropna()
        eg = -0.5 if ni.iloc[-1] < ni.iloc[0] else 0.1  # pérdidas: sólo el sentido
    pil.items.append(Item("earnings_cagr", "Crecimiento anual del beneficio (TACC)", eg,
                          piecewise(eg, [-0.10, 0.0, 0.08, 0.20], [-1, -0.3, 0.4, 1]), "pct", "", 1.0))
    sc = r["share_change"].dropna().mean() if "share_change" in r else float("nan")
    pil.items.append(Item("share_change", "Variación anual de acciones", sc,
                          piecewise(sc, [-0.03, 0.0, 0.02, 0.05], [1, 0.3, -0.4, -1]), "pct",
                          "Negativa = recompras; positiva = dilución", 0.5))
    ni = income["net_income"].dropna() if "net_income" in income else pd.Series(dtype=float)
    if len(ni) and ni.iloc[-1] < 0:
        pil.notes.append("La empresa tiene pérdidas en el último ejercicio.")
    return pil
