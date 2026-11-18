"""Independent, hand-worked or library references for the two paper algorithms."""
import itertools

import numpy as np
import pytest
from scipy.integrate import quad
from sklearn.metrics import brier_score_loss, roc_auc_score

from paper11.methods import (
    BASLConfig, bad_rate, bayesian_metrics, fit_basl, fit_hard_cutoff, fit_ipw,
    fit_scorecard, integrated_bad_rate, metrics,
)


def test_metrics_match_reference_for_weighted_ties_and_default_orientation():
    # Reversing classes for pAUC restricts false approval of defaulters (FNR).
    y = np.array([1, 0, 0, 1, 0, 1, 1, 0])
    pd = np.array([.15, .15, .4, .45, .45, .6, .75, .9])
    w = np.array([4., 3., 1., 6., 8., 2., 4., 0.])
    m = metrics(y, pd, w)
    assert m["auc"] == pytest.approx(roc_auc_score(y, pd, sample_weight=w))
    assert m["brier"] == pytest.approx(brier_score_loss(y, pd, sample_weight=w))
    correct = roc_auc_score(1 - y, 1 - pd, max_fpr=.2, sample_weight=w)
    assert m["pauc"] == pytest.approx(correct)
    assert abs(m["pauc"] - roc_auc_score(y, pd, sample_weight=w, max_fpr=.2)) > .05


def test_integrated_policy_matches_hand_integral_and_is_permutation_invariant():
    # The safest PD ties cover 1/4 of the mass and are half bad. The second
    # group is all good, so the numerator across [.25,.4] stays at 1/8.
    y = np.array([0, 1, 0, 0, 1, 1, 0, 1])
    p = np.array([.1, .1, .2, .2, .7, .8, .8, .9])
    expected = (.5 * .05 + .125 * np.log(.4 / .25)) / .2
    assert integrated_bad_rate(y, p) == pytest.approx(expected)
    assert bad_rate(y, p, .125) == pytest.approx(.5)
    assert bad_rate(y, p, .4) == pytest.approx(.125 / .4)
    assert integrated_bad_rate(y[::-1], p[::-1]) == pytest.approx(expected)
    assert bad_rate(y, p, 1.) == pytest.approx(y.mean())
    assert metrics(y, p)["abr"] == pytest.approx(expected)


def test_exact_integral_matches_quadrature_with_arbitrary_weights():
    rng = np.random.default_rng(243)
    y = rng.integers(0, 2, size=30)
    p = rng.integers(0, 8, size=30) / 8
    w = rng.random(30)

    def literal_abr(q):
        accepted, defaults = 0., 0.
        for risk in np.unique(p):
            group = p == risk
            share = np.clip((q * w.sum() - accepted) / w[group].sum(), 0., 1.)
            defaults += share * (w[group] * y[group]).sum()
            accepted += share * w[group].sum()
        return defaults / (q * w.sum())

    cuts = np.cumsum([w[p == risk].sum() for risk in np.unique(p)]) / w.sum()
    expected, _ = quad(literal_abr, .2, .4, points=cuts[(cuts > .2) & (cuts < .4)])
    assert integrated_bad_rate(y, p, w) == pytest.approx(expected / .2, abs=1e-10)


def test_no_rejects_perfect_prior_and_single_class():
    p = np.array([.05, .85, .1, .91])
    y = np.array([0., 1., 0., 1.])
    exact = metrics(y, p)
    assert bayesian_metrics(y, p, np.full_like(p, np.nan)) == exact
    assert bayesian_metrics([np.nan, 1., 0., np.nan], p, y) == exact
    m = metrics(np.zeros(4), p)
    assert np.isnan(m["auc"]) and np.isnan(m["pauc"])
    assert m["abr"] == 0


def test_bayesian_monte_carlo_matches_exhaustive_enumeration():
    p = np.array([.26, .25, .75, .35, .91, .40])
    y = np.array([0., 1., np.nan, 0., np.nan, 1.])
    prior = np.array([np.nan, np.nan, .75, np.nan, .35, np.nan])
    missing = np.isnan(y)
    reference = {k: 0. for k in ("auc", "brier", "pauc", "abr")}
    for state in itertools.product([0, 1], repeat=2):
        realized = y.copy()
        realized[missing] = state
        prob = np.prod(np.where(state, prior[missing], 1 - prior[missing]))
        for key, value in metrics(realized, p).items():
            reference[key] += prob * value
    result = bayesian_metrics(y, p, prior, seed=160, min_draws=2500, max_draws=2500)
    assert result == pytest.approx(reference, abs=.006)
    assert reference["abr"] == pytest.approx(integrated_bad_rate(np.where(missing, prior, y), p))


def test_bayesian_inputs_reject_invalid_observed_labels_and_priors():
    with pytest.raises(ValueError, match="binary"):
        bayesian_metrics([3., np.nan], [.1, .2], [.1, .7])
    with pytest.raises(ValueError, match="prior"):
        bayesian_metrics([0., np.nan], [.1, .2], [.1, np.nan])
    with pytest.raises(ValueError, match="aligned"):
        metrics([0., 1.], [.1, .2, .3])
    with pytest.raises(ValueError, match="acceptance"):
        bad_rate([0., 1.], [.1, .2], 0.)


def test_basl_rounds_share_fixed_cutoffs_and_select_best_validation_risk():
    rng = np.random.default_rng(32)
    X = rng.normal(size=(850, 4))
    X[300:650, 0] += .5
    risk = 1 / (1 + np.exp(-X[:, 0] + X[:, 1]))
    y = rng.random(len(X)) < risk
    xa, xr, xv = X[:300], X[300:650], X[650:]
    val_y = np.where(np.arange(200) % 3 == 0, np.nan, y[650:])
    config = BASLConfig(rho=.8, gamma=.05, theta=2., max_rounds=3)
    fit = fit_basl(xa, y[:300], xr, xv, val_y, risk[650:], seed=7, config=config)
    assert len(fit.history) >= 2
    assert fit.best_round == 1 + np.argmin([r["validation_abr"] for r in fit.history[1:]])
    assert fit.history[1]["n_bad"] >= fit.history[1]["n_good"] > 0
    for before, after in zip(fit.history, fit.history[1:]):
        assert before["remaining"] - after["remaining"] == after["n_bad"] + after["n_good"]
        assert after["low"] == fit.history[1]["low"]
        assert after["high"] == fit.history[1]["high"]
    expected = integrated_bad_rate(np.where(np.isnan(val_y), risk[650:], val_y),
                                   fit.model.predict_proba(xv)[:, 1])
    assert expected == pytest.approx(fit.history[fit.best_round]["validation_abr"])
    assert fit.stop_reason in {"max_rounds", "no_validation_improvement", "no_confident_labels", "empty_pool"}


def test_empty_reject_pool_and_equal_ipw_return_accepted_scorecard():
    rng = np.random.default_rng(2776)
    X = rng.normal(size=(100, 3))
    y = np.arange(100) % 2
    xa, xv = X[:80], X[80:]
    reference = fit_scorecard(xa, y[:80], seed=4).predict_proba(xv)
    result = fit_basl(xa, y[:80], X[:0], xv, y[80:], np.full(20, np.nan), seed=4)
    assert result.best_round == 0 and result.stop_reason == "empty_pool"
    np.testing.assert_array_equal(reference, result.model.predict_proba(xv))
    np.testing.assert_array_equal(reference, fit_ipw(xa, y[:80], np.full(80, .5), seed=4).predict_proba(xv))
    np.testing.assert_array_equal(reference, fit_hard_cutoff(xa, y[:80], X[:0], seed=4).predict_proba(xv))


def test_first_augmented_candidate_vs_conservative_round_zero():
    rng = np.random.default_rng(4003)
    X = rng.normal(size=(500, 2))
    y = rng.random(150) < 1 / (1 + np.exp(-2 * X[:150, 0]))
    # An all-good inspection set gives every candidate exactly the same ABR.
    # Only the conservative variant may choose zero when augmentation succeeds.
    args = (X[:150], y, X[150:450], X[450:], np.zeros(50), np.full(50, np.nan))
    strict = fit_basl(*args, seed=1, config=BASLConfig(gamma=.05))
    safe = fit_basl(*args, seed=1, config=BASLConfig(gamma=.05, allow_round_zero=True))
    assert len(strict.history) >= 2
    assert strict.best_round == 1
    assert safe.best_round == 0
