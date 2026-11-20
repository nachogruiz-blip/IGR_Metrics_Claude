"""Signaturas (curso §15): identidades exactas, valores cerrados y estimadores con tolerancia 4·stderr."""
import numpy as np
import pandas as pd
import pytest

from trader import backtest as bt
from trader import data, signature as sg


@pytest.fixture(scope="module")
def walk():
    rng = np.random.default_rng(11)
    return np.cumsum(rng.standard_normal((300, 3)), axis=0)


def test_straight_line_is_tensor_exponential():
    d = np.array([0.7, -1.2, 2.0])
    s1, s2, s3 = sg.signature(np.vstack([np.zeros(3), d]), 3)
    np.testing.assert_allclose(s1, d)
    np.testing.assert_allclose(s2, np.einsum("i,j->ij", d, d) / 2)
    np.testing.assert_allclose(s3, np.einsum("i,j,k->ijk", d, d, d) / 6)


def test_chen_identity(walk):
    a, b = walk[:120], walk[119:]
    sa, sb, s = sg.signature(a, 3), sg.signature(b, 3), sg.signature(walk, 3)
    np.testing.assert_allclose(s[0], sa[0] + sb[0])
    np.testing.assert_allclose(s[1], sa[1] + np.einsum("i,j->ij", sa[0], sb[0]) + sb[1])
    s3 = (sa[2] + np.einsum("ij,k->ijk", sa[1], sb[0]) + np.einsum("i,jk->ijk", sa[0], sb[1]) + sb[2])
    np.testing.assert_allclose(s[2], s3, rtol=1e-10, atol=1e-8)


def test_shuffle_identities(walk):
    s1, s2, s3 = sg.signature(walk, 3)
    np.testing.assert_allclose(s2 + s2.T, np.outer(s1, s1))           # S^i S^j = S^ij + S^ji
    lhs = np.einsum("i,jk->ijk", s1, s2)                              # S^i S^jk = S^ijk + S^jik + S^jki
    rhs = s3 + np.swapaxes(s3, 0, 1) + np.transpose(s3, (2, 0, 1))
    np.testing.assert_allclose(lhs, rhs, rtol=1e-10, atol=1e-8)


def test_reparametrization_and_translation_invariance(walk):
    """Pausas (puntos repetidos), subdivisión de tramos y traslación no cambian la signatura."""
    rng = np.random.default_rng(5)
    stalls = walk[np.sort(np.concatenate([np.arange(len(walk)), rng.integers(0, len(walk), 200)]))]
    mid = 0.5 * (walk[1:] + walk[:-1])
    refined = np.empty((2 * len(walk) - 1, 3))
    refined[0::2], refined[1::2] = walk, mid
    ref = sg.signature(walk, 3)
    for other in (stalls, refined, walk + np.array([5.0, -3.0, 1.0])):
        for x, y in zip(ref, sg.signature(other, 3)):
            np.testing.assert_allclose(x, y, rtol=1e-10, atol=1e-8)


def test_time_channel_breaks_invariance(walk):
    stalls = np.repeat(walk, 2, axis=0)
    stalls = np.vstack([stalls[:300], walk[150:]])  # misma trayectoria, ritmo distinto
    a = sg.signature(sg.add_time(walk), 2)[1]
    b = sg.signature(sg.add_time(stalls), 2)[1]
    assert np.abs(a - b).max() > 1e-3
    np.testing.assert_allclose(sg.signature(walk, 2)[1], sg.signature(stalls, 2)[1], atol=1e-8)


def test_levy_area_unit_square():
    sq = np.array([[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]], dtype=float)
    a = sg.levy_area(sq)
    assert a[0, 1] == pytest.approx(1.0) and a[1, 0] == pytest.approx(-1.0)
    assert sg.levy_area(sq[::-1])[0, 1] == pytest.approx(-1.0)


def test_log_signature2_matches_shuffle(walk):
    s1, s2 = sg.signature(walk, 2)
    l1, area = sg.log_signature2(walk)
    np.testing.assert_allclose(s2, 0.5 * np.outer(l1, l1) + area)


def test_lead_lag_area_is_half_quadratic_variation():
    x = np.cumsum(np.random.default_rng(1).normal(0, 0.01, 500))
    a = sg.levy_area(sg.lead_lag(x))
    assert a[0, 1] == pytest.approx(0.5 * np.sum(np.diff(x) ** 2), rel=1e-12)
    assert sg.lead_lag(x).shape == (999, 2)


def test_batch_matches_single(walk):
    batch = np.stack([walk[:100], walk[100:200], walk[200:]])
    out = sg.signature(batch, 3)
    for k in range(3):
        for x, y in zip(sg.signature(batch[k], 3), out):
            np.testing.assert_allclose(x, y[k], rtol=1e-12, atol=1e-10)


@pytest.mark.parametrize("rho", [0.0, 0.5, -0.4])
def test_lead_lag_score_closed_form(rho):
    """r^y_t = ρ r^x_{t−1} + √(1−ρ²) ε_t ⇒ esperanza de la puntuación = ρ (sólo desfase de 1 periodo)."""
    rng = np.random.default_rng(int(10 * rho) + 20)
    rx = rng.standard_normal(60_001)
    ry = rho * rx[:-1] + np.sqrt(1 - rho**2) * rng.standard_normal(60_000)
    score, se = sg.lead_lag_score(rx[1:], ry, window=10)
    assert abs(score - rho) < 4 * se
    rev, _ = sg.lead_lag_score(ry, rx[1:], window=10)
    assert rev == pytest.approx(-score)


def test_lead_lag_score_rejects_bad_input():
    with pytest.raises(ValueError):
        sg.lead_lag_score(np.ones(10), np.ones(9))
    with pytest.raises(ValueError):
        sg.lead_lag_score(np.arange(10.0), np.arange(10.0), window=20)


def test_window_features_shape_and_past_only():
    c = data.synthetic_ohlc(300, seed=4)["close"]
    f = sg.window_features(c, 20, 2)
    assert f.shape == (300, 2 + 2 + 6) and f.iloc[:19].isna().all().all() and f.iloc[19:].notna().all().all()
    c2 = c.copy()
    c2.iloc[150:] *= 1.5
    pd.testing.assert_frame_equal(f.iloc[:150], sg.window_features(c2, 20, 2).iloc[:150])


def test_signature_inputs_validated():
    c = data.synthetic_ohlc(200, seed=4)["close"]
    with pytest.raises(ValueError):
        sg.window_features(c, 2)
    with pytest.raises(ValueError):
        sg.sig_momentum(c, train=500)


def test_sig_momentum_values_and_no_lookahead():
    c = data.synthetic_ohlc(1200, seed=9)["close"]
    pos = bt.signature_momentum(c, train=400, refit=50)
    assert set(pos.unique()) <= {-1.0, 0.0, 1.0}
    assert (pos.iloc[:420] == 0).all() and (pos.iloc[420:] != 0).all()
    k = 800
    c2 = c.copy()
    c2.iloc[k + 1:] = c2.iloc[k + 1:] * np.exp(np.linspace(0, 1, len(c) - k - 1))
    pd.testing.assert_series_equal(pos.iloc[: k + 1], bt.signature_momentum(c2, train=400, refit=50).iloc[: k + 1])


def test_sig_momentum_learns_autocorrelation():
    """Con rentabilidades AR(1) (φ = 0,3) la estrategia gana fuera de muestra; con paseo aleatorio, no hay ventaja."""
    rng = np.random.default_rng(3)
    eps = 0.01 * rng.standard_normal(3000)
    r = np.zeros(3000)
    for t in range(1, 3000):  # recursión AR(1) de una sola serie
        r[t] = 0.3 * r[t - 1] + eps[t]
    c = pd.Series(100 * np.exp(np.cumsum(r)), index=pd.bdate_range("2015-01-01", periods=3000))
    res = bt.backtest(c, bt.signature_momentum(c, window=10), cost_bps=0.0).iloc[600:]
    s = res["strategy"]
    assert s.mean() > 4 * s.std() / np.sqrt(len(s))
