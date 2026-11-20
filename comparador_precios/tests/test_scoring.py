import math

import pytest

from pricecheck import scoring as S
from pricecheck.models import Issue, OfficialStatus, Reputation

RET = OfficialStatus("minorista", "")


def rep(**kw):
    base = dict(domain="t.example", rating=4.0, review_count=50, reviews_analyzed=20,
                issues=[Issue("entrega", "x", "t")] * 5, domain_age_days=3 * 365, https=True)
    base.update(kw)
    return Reputation(**base)


def test_bayes_rating_closed_form():
    assert S.bayes_rating(4.0, 50) == pytest.approx(3.75)          # (50·4 + 50·3,5) / 100
    assert S.bayes_rating(5.0, 3) == pytest.approx((15 + 175) / 53)  # pocas opiniones ⇒ cerca de μ
    assert S.bayes_rating(None, 10) is None and S.bayes_rating(4.0, 0) is None


def test_components_and_weighted_score():
    c = S.components(rep(), RET)
    assert c["valoracion"] == pytest.approx(0.6875)
    assert c["volumen"] == pytest.approx(math.log10(51) / 4)
    assert c["problemas"] == pytest.approx(0.5)                     # 5/20 = 0,25 ⇒ 1 − 0,25/0,5
    assert c["antiguedad"] == 1.0 and c["oficial"] == 0.85
    expected = 100 * sum(S.WEIGHTS[k] * v for k, v in c.items()) / sum(S.WEIGHTS.values())
    assert S.reliability(rep(), RET).score == pytest.approx(expected)


def test_missing_components_renormalize():
    c = {"valoracion": 1.0, "volumen": float("nan"), "problemas": float("nan"),
         "antiguedad": 0.0, "oficial": float("nan")}
    assert S.weighted(c) == pytest.approx(100 * 0.40 / (0.40 + 0.15))


def test_levels():
    assert [S.level_for(x) for x in (90, 75, 60, 55, 40, 35, 10)] == \
        ["alta", "alta", "media", "media", "baja", "baja", "riesgo"]


def test_fraud_veto_and_new_domain_with_anomaly():
    good = rep(rating=4.8, review_count=10000, issues=[], domain_age_days=4000)
    assert S.reliability(good, RET).level == "alta"
    fraud = rep(rating=4.8, review_count=10000, issues=[Issue("fraude", "x", "t")] * 2, domain_age_days=4000)
    assert S.reliability(fraud, RET).level == "riesgo"
    young = rep(rating=4.8, review_count=10000, issues=[], domain_age_days=30)
    r = S.reliability(young, RET, price_anomaly=True)
    assert r.level == "riesgo" and any("anormalmente bajo" in w for w in r.warnings)


def test_no_reviews_caps_at_baja_and_no_https_caps_score():
    r = S.reliability(rep(rating=None, review_count=0, reviews_analyzed=0, issues=[]), OfficialStatus("oficial", ""))
    assert r.level == "baja" and r.score < 55
    r = S.reliability(rep(https=False), RET)
    assert r.score <= S.NO_HTTPS_CAP and r.level == "riesgo"


def test_anomalies():
    med, flags = S.anomalies([100, 105, 98, 50])
    assert med == pytest.approx(99.0) and flags == [False, False, False, True]
    assert S.anomalies([100, 10])[1] == [False, False]              # < 3 ofertas: no se marca
    assert S.anomalies([]) == (None, [])
