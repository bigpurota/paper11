"""Checks of sharpness, policy pairing, tipping and selection on masked labels."""
import itertools

import numpy as np
import pytest

from paper11.bounds import outcome_limits, policy_bounds, select_expansion, tipping_gamma
from paper11.bounds_experiment import design, evaluate_choices
from paper11.empirical import cashflow


def enumerated_statistics(observed, endpoint_options, a, b):
    mask = np.isnan(observed)
    outcomes = []
    for state in itertools.product(*endpoint_options):
        y = observed.copy()
        y[mask] = state
        value_a = cashflow(y, a, .50).mean()
        value_b = cashflow(y, b, .50).mean()
        outcomes.append([y[a].mean(), value_a, value_a - value_b])
    return np.asarray(outcomes)


@pytest.mark.parametrize("gamma", [1., 2., np.inf])
def test_paired_extrema_equal_exhaustive_binary_or_posterior_corner_enumeration(gamma):
    y = np.array([np.nan, 1., 0., np.nan, np.nan, 0.])
    p = np.array([.2, np.nan, np.nan, .4, .7, np.nan])
    # This also tests removals and positive/negative coefficients within one rule.
    a = np.array([1, 1, 0, 1, 0, 1], bool)
    b = np.array([1, 0, 0, 0, 1, 1], bool)
    options = []
    for q in p[np.isnan(y)]:
        if np.isinf(gamma):
            options.append((0., 1.))
        else:
            odds = q / (1 - q)
            options.append((odds / (gamma + odds), gamma * odds / (1 + gamma * odds)))
    trial = enumerated_statistics(y, options, a, b)
    intervals = policy_bounds(y, p, gamma, a, b)
    np.testing.assert_allclose([v.lower for v in intervals], trial.min(axis=0), atol=1e-14)
    np.testing.assert_allclose([v.upper for v in intervals], trial.max(axis=0), atol=1e-14)


def test_paired_placebo_cancels_uncertainty_on_common_approvals():
    y = np.array([0., np.nan, 1., np.nan])
    a = np.array([1, 1, 0, 1], bool)
    _, value, paired = policy_bounds(y, None, np.inf, a, a)
    assert value.upper - value.lower > .2
    assert paired.lower == paired.upper == 0.
    assert np.isinf(tipping_gamma(y, np.full(4, .3), a, a))


def test_empty_approval_and_complete_labels_and_extreme_gamma():
    a = np.array([False, False]); b = ~a
    y = np.array([0., 1.])
    abr, value, delta = policy_bounds(y, None, 1., a, b)
    assert np.isnan(abr.lower) and np.isnan(abr.upper)
    assert value.lower == value.upper == 0
    assert delta.lower == pytest.approx(-cashflow(y, b, .5).mean())
    y[:] = np.nan
    p = np.array([.02, .99])
    low, high = outcome_limits(y, p, 1.e20)
    np.testing.assert_allclose(low, 0., atol=1e-15)
    np.testing.assert_allclose(high, 1., atol=1e-15)
    with pytest.raises(ValueError, match="interior"):
        outcome_limits(y, [0., .2], 2.)


def test_tipping_radius_has_analytic_solution_and_marks_infeasible_prior():
    # Issue the only loan. Default must be <= .10/.55, equivalent to
    # upper odds <= 2/9. Prior odds = 1/9, giving a radius of exactly 2.
    assert tipping_gamma([np.nan], [.1], [1], [0]) == pytest.approx(2.)
    assert np.isnan(tipping_gamma([np.nan], [.2], [1], [0]))
    assert np.isinf(tipping_gamma([0], None, [1], [0]))
    assert tipping_gamma([np.nan], [.1], [1], [0], budget=.01) > 2.


def test_validation_choice_and_tie_break():
    target = [.3, .4, .5]
    assert select_expansion(target, [0, .02, .03], [0, -.001, -.003], .0025) == 1
    assert select_expansion(target, [0, .02, .03], [0, -.001, -.003], 0.) == 0
    assert select_expansion(target, [0, .02, .02], [0, 0., 0.], 0.) == 1


def test_finite_gamma_bounds_a_mean_and_do_not_bound_binary_realizations():
    y = np.array([np.nan])
    abr, _, _ = policy_bounds(y, [.1], 1., [1], [0])
    assert abr.lower == pytest.approx(.1) and abr.upper == pytest.approx(.1)
    assert 1. > abr.upper
    assert policy_bounds(y, None, np.inf, [1], [0])[0].upper == 1.


def test_test_outcomes_cannot_change_locked_policy_and_binary_endpoints_hold():
    rng = np.random.default_rng(8810)
    n = 60
    score = rng.random(n)
    prior = .01 + .15 * rng.random(n)
    observed = np.where(np.arange(n) % 2, np.nan, 0.)
    _, _, choices = design(score, observed, prior)
    y0, y1 = np.zeros(n), np.ones(n)
    # The test population deliberately has entirely hidden outcomes.
    rows0 = evaluate_choices(choices, score, prior, np.full(n, np.nan), y0)
    rows1 = evaluate_choices(choices, score, prior, np.full(n, np.nan), y1)
    for one, two in zip(rows0, rows1):
        assert one["cutoff"] == two["cutoff"] and one["target"] == two["target"]
        assert one["test_binary_gain_upper"] == pytest.approx(one["realized_test_gain"])
        assert two["test_binary_gain_lower"] == pytest.approx(two["realized_test_gain"])
    assert any(a["realized_test_gain"] != b["realized_test_gain"] for a, b in zip(rows0, rows1))
