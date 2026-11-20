import io

import numpy as np
import pandas as pd

from commodash import data
from commodash.contracts import CATALOG


def test_yahoo_tickers():
    assert CATALOG["wti"].ticker(pd.Period("2027-01", freq="M")) == "CLF27.NYM"
    assert CATALOG["gold"].ticker(pd.Period("2026-12", freq="M")) == "GCZ26.CMX"


def test_demo_panel_shape_and_listing():
    c = CATALOG["corn"]
    p = data.demo_panel(c, pd.Timestamp("2026-11-20"), history_years=1)
    assert set(m.month for m in p.columns) <= set(c.months)
    assert p.index[-1] == pd.Timestamp("2026-11-20")
    last = p.iloc[-1].dropna()
    assert last.index.min() > pd.Period("2026-11", freq="M")
    assert (last > 0).all() and np.isfinite(last).all()
    # reproducible
    q = data.demo_panel(c, pd.Timestamp("2026-11-20"), history_years=1)
    pd.testing.assert_frame_equal(p, q)


def test_contract_range_covers_longest_strip():
    first, last = data.contract_range(pd.Timestamp("2026-11-20"), 2)
    assert first == pd.Period("2024-12", freq="M")
    assert last >= pd.Period("2029-11", freq="M")  # 3A rolling
    assert last >= pd.Period("2028-12", freq="M")  # Cal A+2


def test_read_csv_long_format():
    csv = ("fecha;commodity;entrega;precio\n"
           "2026-11-19;TTF;2026-12;31.5\n2026-11-19;TTF;2027-01;32.0\n"
           "2026-11-20;TTF;2026-12;31.0\n2026-11-20;TTF;2027-01;31.8\n"
           "2026-11-20;PWR_ES;2027-01;70\n")
    out = data.read_csv(io.StringIO(csv))
    assert set(out) == {"TTF", "PWR_ES"}
    ttf = out["TTF"]
    assert list(ttf.columns) == [pd.Period("2026-12", freq="M"), pd.Period("2027-01", freq="M")]
    assert ttf.loc["2026-11-20", pd.Period("2027-01", freq="M")] == 31.8
