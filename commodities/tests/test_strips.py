"""Definición de tramos, precio de strip y coherencia del histórico vectorizado."""

import numpy as np
import pandas as pd
import pytest

from commodash import data, strips
from commodash.contracts import CATALOG
from commodash.strips import STRIPS, describe_months, month_ord

BY_KEY = {s.key: s for s in STRIPS}
P = lambda s: pd.Period(s, freq="M")  # noqa: E731


# --------------------------------------------------------------------------- meses de cada tramo
@pytest.mark.parametrize("day", ["2026-11-01", "2026-11-20", "2026-11-30"])
def test_month_zero_never_counts(day):
    asof = pd.Timestamp(day)
    for s in STRIPS:
        assert all(m > P("2026-11") for m in s.months(asof)), s.key


def test_november_example():
    asof = pd.Timestamp("2026-11-20")
    m = {k: s.months(asof) for k, s in BY_KEY.items()}
    assert (m["1A"][0], m["1A"][-1], len(m["1A"])) == (P("2026-12"), P("2027-11"), 12)
    assert (m["2A"][0], m["2A"][-1], len(m["2A"])) == (P("2026-12"), P("2028-11"), 24)
    assert (m["3A"][0], m["3A"][-1], len(m["3A"])) == (P("2026-12"), P("2029-11"), 36)
    assert list(m["A"]) == [P("2026-12")]
    assert (m["A+1"][0], m["A+1"][-1], len(m["A+1"])) == (P("2027-01"), P("2027-12"), 12)
    assert (m["A+2"][0], m["A+2"][-1], len(m["A+2"])) == (P("2028-01"), P("2028-12"), 12)
    assert describe_months(m["1A"]) == "dic-26 – nov-27"
    assert BY_KEY["A+1"].label(asof) == "Cal-27 (A+1)"


def test_december_leaves_current_year_empty_and_january_starts_in_february():
    assert len(BY_KEY["A"].months(pd.Timestamp("2026-12-10"))) == 0
    assert describe_months(BY_KEY["A"].months(pd.Timestamp("2026-12-10"))) == "sin meses restantes"
    jan = BY_KEY["A"].months(pd.Timestamp("2027-01-05"))
    assert (jan[0], jan[-1], len(jan)) == (P("2027-02"), P("2027-12"), 11)
    assert BY_KEY["1A"].months(pd.Timestamp("2026-12-10"))[0] == P("2027-01")


# --------------------------------------------------------------------------- precio del strip
def _panel(fn, dates, months):
    """Panel con F(t, T) = fn(i_t, ord(T)) para todos los contratos."""
    d = np.arange(len(dates))[:, None]
    m = month_ord(months)[None, :]
    return pd.DataFrame(fn(d, m).astype(float), index=dates, columns=months)


DATES = pd.bdate_range("2026-09-01", "2026-11-20")
MONTHS = pd.period_range("2026-09", "2030-12", freq="M")


def test_strip_is_average_of_its_months():
    panel = _panel(lambda d, m: 100 + (m - month_ord(P("2026-12"))) + 0 * d, DATES, MONTHS)
    cv = strips.prepare(panel)
    # curva lineal en el mes: la media de M+1…M+12 es el valor del punto medio (5.5 meses)
    assert strips.strip_stats(cv, BY_KEY["1A"]).value == pytest.approx(105.5)
    assert strips.strip_stats(cv, BY_KEY["A"]).value == pytest.approx(100.0)
    assert strips.strip_stats(cv, BY_KEY["A+1"]).value == pytest.approx(101 + 5.5)
    assert strips.strip_stats(cv, BY_KEY["3A"]).value == pytest.approx(100 + 17.5)


def test_days_weighting():
    months = pd.period_range("2026-12", "2028-12", freq="M")
    panel = pd.DataFrame([[1.0 if m.month == 2 else 0.0 for m in months]],
                         index=[pd.Timestamp("2026-11-20")], columns=months)
    eq = strips.strip_stats(strips.prepare(panel, "equal"), BY_KEY["A+1"]).value
    days = strips.strip_stats(strips.prepare(panel, "days"), BY_KEY["A+1"]).value
    assert eq == pytest.approx(1 / 12)
    assert days == pytest.approx(28 / 365)


def test_interpolation_between_listed_months_and_coverage():
    months = pd.period_range("2026-12", "2028-12", freq="M")
    vals = [float(i) if m.month in (3, 6, 9, 12) else np.nan for i, m in enumerate(months)]
    panel = pd.DataFrame([vals], index=[pd.Timestamp("2026-11-20")], columns=months)
    cv = strips.prepare(panel, listed_months=(3, 6, 9, 12))
    st = strips.strip_stats(cv, BY_KEY["A+1"])  # interpolación lineal exacta: meses 1..12
    assert st.value == pytest.approx(np.mean(np.arange(1, 13)))
    assert st.coverage == pytest.approx(1.0)  # todos los meses cotizables tienen precio
    cv_all = strips.prepare(panel)  # si se esperaban los 12 meses, sólo hay 4
    assert strips.strip_stats(cv_all, BY_KEY["A+1"]).coverage == pytest.approx(4 / 12)


def test_far_end_extrapolation_is_limited():
    months = pd.period_range("2026-12", "2027-12", freq="M")  # curva sólo hasta dic-27
    panel = pd.DataFrame(np.ones((1, len(months))), index=[pd.Timestamp("2026-11-20")],
                         columns=months)
    cv = strips.prepare(panel, max_extrap=3)
    assert np.isfinite(strips.strip_stats(cv, BY_KEY["1A"]).value)
    assert np.isnan(strips.strip_stats(cv, BY_KEY["A+2"]).value)  # 2028 no existe


def test_expired_contract_keeps_its_settlement():
    """WTI dic-26 vence a mediados de noviembre: su último cierre sigue contando en Cal A."""
    dates = pd.bdate_range("2026-11-02", "2026-11-20")
    months = pd.period_range("2026-12", "2027-12", freq="M")
    panel = pd.DataFrame(50.0, index=dates, columns=months)
    panel.loc["2026-11-12":, P("2026-12")] = np.nan
    panel.loc["2026-11-11", P("2026-12")] = 42.0
    cv = strips.prepare(panel)
    assert strips.strip_stats(cv, BY_KEY["A"]).value == pytest.approx(42.0)


# --------------------------------------------------------------------------- histórico
@pytest.fixture(scope="module")
def demo_curves():
    c = CATALOG["natgas"]
    panel = data.demo_panel(c, pd.Timestamp("2026-11-20"), history_years=1)
    return strips.prepare(panel, c.weighting, listed_months=c.months)


def test_history_matches_pointwise_computation(demo_curves):
    """Cada punto de la serie vectorizada = strip recalculado con la curva de ese día."""
    cv = demo_curves
    for s in (BY_KEY["1A"], BY_KEY["3A"], BY_KEY["A+1"]):
        hist = strips.strip_series(cv, s)["value"]
        for i in (10, 100, len(cv.dates) - 1):
            d = cv.dates[i]
            months = s.months(d) if s.kind == "rolling" else [
                m for m in pd.period_range(f"{2026 + s.n}-01", f"{2026 + s.n}-12", freq="M")
                if m > d.to_period("M")]
            row = cv.prices.iloc[i]
            w = np.array([m.days_in_month for m in months], float)
            expected = np.dot(w, row[pd.PeriodIndex(months)].to_numpy()) / w.sum()
            assert hist.iloc[i] == pytest.approx(expected), (s.key, d)


def test_rolling_rolls_at_month_change(demo_curves):
    """El 1A rolling del último día de octubre y del primero de noviembre usa conjuntos
    distintos; la variación like-for-like no incluye ese salto."""
    cv = demo_curves
    h = strips.strip_series(cv, BY_KEY["1A"])
    i = cv.dates.get_loc(pd.Timestamp("2026-11-02"))
    jump = np.log(h["value"].iloc[i] / h["value"].iloc[i - 1])
    assert not np.isclose(jump, h["ret"].iloc[i])


def test_like_for_like_change_identity(demo_curves):
    cv = demo_curves
    st = strips.strip_stats(cv, BY_KEY["2A"])
    past = strips.like_for_like(cv, BY_KEY["2A"], 5)
    assert st.changes["1S"] == pytest.approx(st.value / past - 1)
    assert st.abs_changes["1S"] == pytest.approx(st.value - past)
    # dentro del mismo mes, like-for-like = variación de la serie rolling
    assert past == pytest.approx(st.history["value"].iloc[-6])
    # la suma de log-variaciones diarias like-for-like de la semana = log-variación semanal
    assert st.history["ret"].iloc[-5:].sum() == pytest.approx(np.log(st.value / past))
    assert 0 <= st.range_pos <= 1 and st.low_52w <= st.value <= st.high_52w


def test_structure_detects_contango_and_backwardation():
    up = _panel(lambda d, m: 100 * 1.01 ** (m - 600) + 0 * d, DATES, MONTHS)
    down = _panel(lambda d, m: 100 * 0.99 ** (m - 600) + 0 * d, DATES, MONTHS)
    assert strips.structure(strips.prepare(up))[0] == "Contango"
    assert strips.structure(strips.prepare(down))[0] == "Backwardation"
