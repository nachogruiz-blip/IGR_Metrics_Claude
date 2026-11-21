import statistics

import pytest

from pricecheck import core, stats
from pricecheck.demo import DEMO_BRAND, DEMO_QUERY, demo_sources


def test_describe_matches_closed_values():
    xs = [10.0, 20.0, 30.0, 40.0]
    d = stats.describe(xs, list(stats.STATS))
    assert d["Mediana"] == 25 and d["Media"] == 25 and d["Mínimo"] == 10 and d["Máximo"] == 40
    assert d["Percentil 25"] == pytest.approx(17.5) and d["Percentil 75"] == pytest.approx(32.5)
    assert d["Rango intercuartílico"] == pytest.approx(15.0)
    assert d["Desviación típica"] == pytest.approx(statistics.stdev(xs))


def test_describe_only_requested_and_small_samples():
    assert list(stats.describe([5.0], ["Máximo", "Mediana"])) == ["Mediana", "Máximo"]   # orden de STATS
    assert stats.describe([5.0], ["Desviación típica"]) == {"Desviación típica": None}
    assert stats.describe([], ["Mediana"]) == {"Mediana": None}


def test_selection_recomputes_on_demo():
    r = core.check(DEMO_QUERY, demo_sources(), brand=DEMO_BRAND)
    sel = [a for a, m in zip(r.assessments, stats.default_selection(r.assessments)) if m]
    assert all(not a.requires_service for a in sel) and len(sel) == len(r.assessments) - 1
    full = stats.describe_offers(sel, ["Mediana"], "Precio + envío")["Mediana"]
    assert full == pytest.approx(r.median_total)               # misma mediana que el informe
    no_scam = [a for a in sel if a.offer.domain != "chollazo-outlet.example"]
    assert stats.describe_offers(no_scam, ["Mínimo"])["Mínimo"] == pytest.approx(313.99)
    assert core.recommend(no_scam).offer.domain == "mercadoglobal.example"
