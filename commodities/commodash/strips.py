"""Tramos (*strips*) de la curva de futuros: 1A/2A/3A rolling y años de calendario A, A+1, A+2.

Convenciones
------------
* **Mes 0 = mes en curso, nunca cuenta.** En una fecha de noviembre-2026 el primer mes de
  entrega es diciembre-2026 (M+1). Así:

  - ``1A`` rolling = M+1 … M+12 (dic-26 … nov-27); ``2A`` = M+1 … M+24; ``3A`` = M+1 … M+36.
  - ``A`` (año en curso) = meses del año en curso posteriores a M0 (en noviembre, sólo dic-26;
    en diciembre queda vacío). ``A+1`` y ``A+2`` = los 12 meses del año siguiente / del otro.

* **Precio del strip** = media de los meses del tramo, simple (``equal``) o ponderada por días
  de entrega (``days``, habitual en gas y electricidad).
* **Huecos en la curva**: el último cierre de cada contrato se arrastra en el tiempo (festivos,
  contratos ya vencidos cuyo precio quedó fijado); los meses sin contrato cotizado (oro, maíz…)
  se interpolan linealmente entre vencimientos, y en los extremos se extrapola plano como mucho
  ``max_extrap`` meses. La *cobertura* indica qué fracción (ponderada) del tramo tiene cotización
  propia.
* **Variaciones like-for-like**: la variación a 1 semana de «1A rolling» compara el precio actual
  del tramo con el precio de **los mismos contratos** hace una semana (sin el salto de *roll*).
  La serie histórica del gráfico, en cambio, es la del tramo rolling tal y como se veía cada día.
* Los años de calendario son productos fijos (``A`` = año de la última fecha): su histórico es el
  de ese mismo año (p. ej. Cal-27 a lo largo de 2025 y 2026), siempre sin el mes 0 de cada día.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
HORIZONS = {"1D": 1, "1S": 5, "1M": 21, "3M": 63}
TRADING_DAYS = 252


def month_ord(x) -> np.ndarray:
    """Número de mes absoluto ``año·12 + mes − 1`` de fechas o periodos."""
    if isinstance(x, (pd.Timestamp, pd.Period)):
        return np.array(x.year * 12 + x.month - 1)
    idx = pd.Index(x)
    return np.asarray(idx.year * 12 + idx.month - 1, dtype=np.int64)


def ord_to_period(o: int) -> pd.Period:
    return pd.Period(year=int(o) // 12, month=int(o) % 12 + 1, freq="M")


# --------------------------------------------------------------------------- definición de tramos
@dataclass(frozen=True)
class Strip:
    key: str
    kind: str  # "rolling" | "calendar"
    n: int     # años del tramo rolling, o desfase del año de calendario

    def label(self, asof: pd.Timestamp) -> str:
        if self.kind == "rolling":
            return f"{self.n}A rolling"
        return f"Cal-{(asof.year + self.n) % 100:02d} ({self.key})"

    def include(self, date_ords: np.ndarray, col_ords: np.ndarray, ref_year: int) -> np.ndarray:
        """Matriz booleana (fechas × meses de entrega) de los meses que forman el tramo."""
        d = np.asarray(date_ords)[:, None]
        c = np.asarray(col_ords)[None, :]
        if self.kind == "rolling":
            return (c - d >= 1) & (c - d <= 12 * self.n)
        return (c // 12 == ref_year + self.n) & (c > d)

    def months(self, asof: pd.Timestamp) -> pd.PeriodIndex:
        """Meses de entrega del tramo vistos en la fecha ``asof``."""
        d = int(month_ord(asof))
        cand = np.arange(d + 1, d + 12 * 3 + 13)
        sel = cand[self.include(np.array([d]), cand, asof.year)[0]]
        return pd.PeriodIndex([ord_to_period(o) for o in sel], freq="M")


STRIPS: tuple[Strip, ...] = (
    Strip("1A", "rolling", 1), Strip("2A", "rolling", 2), Strip("3A", "rolling", 3),
    Strip("A", "calendar", 0), Strip("A+1", "calendar", 1), Strip("A+2", "calendar", 2),
)
ROLLING = STRIPS[:3]
CALENDAR = STRIPS[3:]


def describe_months(months: pd.PeriodIndex) -> str:
    if len(months) == 0:
        return "sin meses restantes"
    f = lambda p: f"{MESES[p.month - 1]}-{p.year % 100:02d}"  # noqa: E731
    return f(months[0]) if len(months) == 1 else f"{f(months[0])} – {f(months[-1])}"


# --------------------------------------------------------------------------- curvas preparadas
@dataclass
class Curves:
    """Curvas diarias listas para promediar (fechas × meses de entrega consecutivos)."""

    prices: pd.DataFrame        # interpolada; NaN en meses ≤ mes 0 de cada fecha
    quoted: pd.DataFrame        # True si el mes tenía cotización propia ese día
    weights: np.ndarray = field(repr=False)  # peso de cada mes de entrega
    weighting: str = "equal"
    listed: np.ndarray | None = field(default=None, repr=False)  # meses con contrato propio

    @property
    def dates(self) -> pd.DatetimeIndex:
        return self.prices.index

    @property
    def col_ords(self) -> np.ndarray:
        return month_ord(self.prices.columns)


def prepare(panel: pd.DataFrame, weighting: str = "equal", max_extrap: int = 3,
            listed_months: tuple[int, ...] = tuple(range(1, 13))) -> Curves:
    """Panel bruto (fechas × ``Period`` de entrega, cierres con NaN) → :class:`Curves`.

    ``listed_months``: meses del año con contrato propio (oro: pares; maíz: H K N U Z). La
    cobertura se mide sólo sobre ellos; el resto de meses se interpola siempre.
    """
    if panel.empty:
        raise ValueError("panel vacío")
    p = panel.sort_index().copy()
    p.columns = pd.PeriodIndex(p.columns, freq="M")
    cols = pd.period_range(p.columns.min(), p.columns.max(), freq="M")
    p = p.T.groupby(level=0).mean().T.reindex(columns=cols).astype(float).ffill()

    past = month_ord(cols)[None, :] <= month_ord(p.index)[:, None]
    p = p.mask(past)
    quoted = p.notna()
    p = (p.interpolate(axis=1, limit_area="inside")
          .bfill(axis=1, limit=max_extrap).ffill(axis=1, limit=max_extrap).mask(past))
    w = (np.asarray(cols.days_in_month, dtype=float) if weighting == "days"
         else np.ones(len(cols)))
    listed = np.isin(np.asarray(cols.month), listed_months)
    return Curves(p, quoted, w, weighting, listed)


def _average(P: np.ndarray, W: np.ndarray) -> np.ndarray:
    """Media ponderada por filas; NaN si algún mes del tramo falta o el tramo está vacío."""
    sw = W.sum(axis=1)
    inc = W > 0
    missing = (np.isnan(P) & inc).any(axis=1)
    num = (W * np.nan_to_num(P)).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = num / sw
    out[missing | (sw == 0)] = np.nan
    return out


def strip_weights(curves: Curves, strip: Strip, ref_year: int | None = None) -> np.ndarray:
    ref_year = curves.dates[-1].year if ref_year is None else ref_year
    inc = strip.include(month_ord(curves.dates), curves.col_ords, ref_year)
    return inc * curves.weights[None, :]


def strip_series(curves: Curves, strip: Strip, ref_year: int | None = None) -> pd.DataFrame:
    """Histórico diario del tramo: ``value``, ``coverage`` y ``ret`` (log-variación diaria
    like-for-like: mismos contratos ayer y hoy)."""
    W = strip_weights(curves, strip, ref_year)
    P = curves.prices.to_numpy()
    value = _average(P, W)
    prev = np.full_like(value, np.nan)
    prev[1:] = _average(P[:-1], W[1:])
    with np.errstate(invalid="ignore", divide="ignore"):
        Wl = W if curves.listed is None else W * curves.listed[None, :]
        coverage = (Wl * curves.quoted.to_numpy()).sum(axis=1) / Wl.sum(axis=1)
        ret = np.log(value / prev)
    return pd.DataFrame({"value": value, "coverage": coverage, "ret": ret}, index=curves.dates)


def like_for_like(curves: Curves, strip: Strip, lag: int) -> float:
    """Precio hace ``lag`` sesiones de los contratos que forman hoy el tramo."""
    W = strip_weights(curves, strip)
    if lag >= len(curves.dates):
        return np.nan
    P = curves.prices.to_numpy()[-1 - lag][None, :]
    return float(_average(P, W[-1][None, :])[0])


@dataclass
class StripStats:
    strip: Strip
    label: str
    months: pd.PeriodIndex
    value: float
    coverage: float
    changes: dict[str, float]      # variación relativa like-for-like por horizonte
    abs_changes: dict[str, float]  # variación absoluta like-for-like
    vol_1m: float
    vol_3m: float
    low_52w: float
    high_52w: float
    range_pos: float               # posición en el rango de 52 semanas (0 = mínimo, 1 = máximo)
    history: pd.DataFrame = field(repr=False)


def strip_stats(curves: Curves, strip: Strip) -> StripStats:
    asof = curves.dates[-1]
    hist = strip_series(curves, strip)
    v = float(hist["value"].iloc[-1])
    changes, abs_changes = {}, {}
    for name, lag in HORIZONS.items():
        past = like_for_like(curves, strip, lag)
        abs_changes[name] = v - past
        changes[name] = v / past - 1 if np.isfinite(past) and past != 0 else np.nan
    r = hist["ret"]
    last = hist["value"].iloc[-TRADING_DAYS:]
    lo, hi = float(last.min()), float(last.max())
    pos = (v - lo) / (hi - lo) if np.isfinite(v) and hi > lo else np.nan
    return StripStats(strip, strip.label(asof), strip.months(asof), v,
                      float(hist["coverage"].iloc[-1]), changes, abs_changes,
                      _vol(r, 21), _vol(r, 63), lo, hi, pos, hist)


def _vol(ret: pd.Series, n: int) -> float:
    """Volatilidad anualizada de las últimas ``n`` variaciones diarias (NaN si faltan muchas)."""
    tail = ret.iloc[-n:]
    return float(tail.std() * np.sqrt(TRADING_DAYS)) if tail.notna().sum() > n // 2 else np.nan


# --------------------------------------------------------------------------- curva y estructura
def forward_curve(curves: Curves, date: pd.Timestamp | None = None, n_months: int = 48
                  ) -> pd.DataFrame:
    """Curva de una fecha (por defecto la última): meses M+1 … M+n con ``price`` y ``quoted``."""
    i = len(curves.dates) - 1 if date is None else curves.dates.get_indexer([date], "ffill")[0]
    d = curves.dates[i]
    row, q = curves.prices.iloc[i], curves.quoted.iloc[i]
    mo = int(month_ord(d))
    keep = (curves.col_ords > mo) & (curves.col_ords <= mo + n_months)
    out = pd.DataFrame({"price": row[keep].to_numpy(), "quoted": q[keep].to_numpy()},
                       index=curves.prices.columns[keep])
    return out.dropna(subset=["price"])


def structure(curves: Curves, threshold: float = 0.01) -> tuple[str, float]:
    """Contango / backwardation según la pendiente M+12 frente a M+1 (relativa)."""
    fc = forward_curve(curves, n_months=12)
    if len(fc) < 2:
        return "Sin datos", np.nan
    slope = fc["price"].iloc[-1] / fc["price"].iloc[0] - 1
    if slope > threshold:
        return "Contango", slope
    if slope < -threshold:
        return "Backwardation", slope
    return "Plana", slope
