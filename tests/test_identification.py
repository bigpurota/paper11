"""Exhaustive finite populations cross-check the compressed credit-policy game."""
import itertools

import numpy as np
import pytest
from scipy.optimize import linprog

from paper11.identification import (
    adverse_worlds, binary_solution, information_value, minimax, rounded_prior_counts,
    test_audit as audit_holdout, validation_game,
)


def all_completions(observed, decisions, quotas=None):
    y = np.asarray(observed).copy()
    hidden = np.isnan(y)
    states = []
    values = []
    for vector in itertools.product((0., 1.), repeat=int(hidden.sum())):
        y[hidden] = vector
        if quotas is not None:
            group, n = quotas
            observed_counts = [np.sum(y[hidden & (group == j)]) for j in range(len(n))]
            if not np.array_equal(observed_counts, n):
                continue
        states.append(y.copy())
        # Spell out the original cash flows independently.
        values.append(np.asarray(decisions) @ np.where(y == 1, -.45, .10) / len(y))
    return np.asarray(states), np.asarray(values)


def exhaustive_solution(values):
    regret = values.max(axis=1)[:, None] - values
    m, n = regret.shape
    # Independent, dual least-favorable-world distribution in place of primal lottery.
    result = linprog(np.r_[np.zeros(m), -1], A_ub=np.c_[-regret.T, np.ones(n)],
                     b_ub=np.zeros(n), A_eq=[np.r_[np.ones(m), 0.]], b_eq=[1.],
                     bounds=[(0, None)] * (m + 1), method="highs")
    assert result.success
    return -result.fun, regret.max(axis=0)


@pytest.mark.parametrize("mode", ["crossing", "nested", "nested_with_counts"])
def test_one_witness_per_oracle_is_exact_for_all_mixtures(mode):
    observed = np.array([1., 0., np.nan, np.nan, np.nan, np.nan, np.nan, np.nan])
    score = np.array([.2, .9, .1, .95, .4, .3, .5, .7])
    d = score[None, :] < np.array([.2, .4, .6, .8])[:, None]
    quotas = None
    if mode == "crossing":
        d[0, 7] = True
        d[2, 2] = False
    if mode == "nested_with_counts":
        quotas = np.array([-1, -1, 0, 0, 0, 1, 1, 1]), np.array([1, 2])
    game = adverse_worlds(observed, d, quotas)
    states, values = all_completions(observed, d, quotas)
    for world in game.worlds:
        assert (states == world).all(axis=1).any()
    for w in list(np.eye(len(d))) + [np.array([.56, .12, .32, 0]), np.ones(4)/4]:
        brute = (values - (values @ w)[:, None]).max(axis=0)
        np.testing.assert_allclose(game.regret @ w, brute, atol=5e-15)
    mixed, pure = exhaustive_solution(values)
    solution = minimax(game.regret)
    np.testing.assert_allclose(game.regret.max(axis=0), pure, atol=1e-14)
    assert solution.mixed_regret == pytest.approx(mixed)
    assert solution.pure_regret == pytest.approx(pure.min())
    assert solution.weights.sum() == pytest.approx(1)


def test_observed_data_and_group_default_counts_can_match_while_decision_flips():
    observed = np.array([0., 1., np.nan, np.nan, np.nan, np.nan, np.nan])
    # Two of four marginal missing borrowers can carry the same group's default.
    d = np.array([[1, 0, 0, 0, 0, 0, 0], [1, 0, 1, 1, 0, 0, 0]])
    group = np.array([-1, -1, 0, 0, 0, 0, 1])
    quotas = group, np.array([1, 0])
    game = adverse_worlds(observed, d, quotas)
    np.testing.assert_array_equal(game.worlds[:, :2], [[0, 1], [0, 1]])
    np.testing.assert_array_equal(game.worlds[:, group == 0].sum(axis=1), [1, 1])
    assert game.margins[0, 1] < game.margins[0, 0]
    assert game.margins[1, 1] > game.margins[1, 0]
    np.testing.assert_array_equal(game.margins.argmax(axis=1), [0, 1])


@pytest.mark.parametrize(("low", "high", "w", "r"), [
    (-.3, .1, .25, .075), (.1, .2, 1., 0.), (-.3, -.1, 0., 0.), (0., 0., 0., 0.)
])
def test_binary_formula_interior_and_dominance(low, high, w, r):
    x, value = binary_solution(low, high)
    assert (x, value) == pytest.approx((w, r))
    assert minimax([[0., -low], [high, 0.]]).mixed_regret == pytest.approx(r)


def test_quota_input_and_degenerate_policy_cases():
    observed = np.array([np.nan, 1., np.nan])
    strata, totals = rounded_prior_counts(observed, [.5, np.nan, .5], bins=4)
    np.testing.assert_array_equal(totals, [1, 1, 0, 0])
    all_same = np.array([[1, 0, 1], [1, 0, 1]])
    g = adverse_worlds(observed, all_same, (strata, totals))
    assert minimax(g.regret).pure_regret == minimax(g.regret).mixed_regret == 0.
    with pytest.raises(ValueError, match="infeasible"):
        adverse_worlds(observed, all_same, (strata, np.array([2, 1, 0, 0])))
    with pytest.raises(ValueError, match="nested"):
        adverse_worlds(observed, [[1, 1, 0], [0, 1, 1]], (strata, totals))
    complete = adverse_worlds(np.array([0., 1., 0.]), [[0, 1, 0], [1, 0, 0]])
    assert minimax(complete.regret).mixed_regret == 0
    assert minimax(complete.regret).pure_action == 1


def test_information_value_enumerates_attainable_signals_before_taking_worst_case():
    y = np.array([np.nan, 0., np.nan, np.nan, np.nan, 1., 0.])
    d = np.array([[1,0,0,0,0,0,0], [1,1,1,1,0,0,0], [1,1,1,1,1,1,0]])
    states, v = all_completions(y, d)
    before, _ = exhaustive_solution(v)
    info = information_value(y, d, before)
    for j, row in enumerate(info):
        observed_count = states[:, (d[j] != d[j+1]) & np.isnan(y)].sum(axis=1)
        conditional = [exhaustive_solution(v[observed_count == s])[0] for s in np.unique(observed_count)]
        assert row["worst_after"] == pytest.approx(max(conditional))
        assert row["guaranteed_regret_reduction"] == pytest.approx(before - max(conditional))
    two_before, _ = exhaustive_solution(v[:, [0,-1]])
    assert information_value(y, d[[0,-1]], two_before)[0]["worst_after"] < 1e-12


def test_changing_test_labels_does_not_change_validation_cutoffs_or_lottery():
    score = np.linspace(.01, .99, 30)
    observed = np.where(np.arange(30) % 3 == 0, 0., np.nan)
    cut, choices, _, _, _ = validation_game(score, observed, .2 * score)
    previous = [c["weights"].copy() for c in choices]
    good = audit_holdout(score, np.zeros(30), cut, choices)
    bad = audit_holdout(score, np.ones(30), cut, choices)
    for choice, original in zip(choices, previous):
        np.testing.assert_array_equal(choice["weights"], original)
    assert any(g["test_mixed_gain"] > b["test_mixed_gain"] for g,b in zip(good,bad))


def test_retrospective_oracle_discloses_totals_only_and_both_extreme_worlds_match_them():
    from paper11.identification import retrospective_counts

    y = np.full(41, np.nan)
    y[-1] = 1
    p = np.linspace(0, 1, len(y))
    # One hidden default in each of the 10 prior strata; move its identity.
    truth_a = np.zeros(41, dtype=int)
    truth_b = np.zeros(41, dtype=int)
    truth_a[:-1:4] = 1
    truth_b[1:-1:4] = 1
    truth_a[-1] = truth_b[-1] = 1
    groups_a, counts_a = retrospective_counts(y, truth_a, p)
    groups_b, counts_b = retrospective_counts(y, truth_b, p)
    np.testing.assert_array_equal(groups_a, groups_b)
    np.testing.assert_array_equal(counts_a, np.ones(10))
    np.testing.assert_array_equal(counts_a, counts_b)
    d = np.array([np.arange(41) % 4 == 2, np.arange(41) % 4 != 3])
    game = adverse_worlds(y, d, (groups_a, counts_a))
    for state in game.worlds:
        for group in range(10):
            assert state[groups_a == group].sum() == truth_a[groups_a == group].sum()
    assert game.margins[0,1] - game.margins[0,0] < 0 < game.margins[1,1] - game.margins[1,0]
    with pytest.raises(ValueError, match="agree"):
        retrospective_counts(y, 1-truth_a, p)


def test_decile_certificate_counts_equal_exhaustive_feasible_completions():
    from paper11.identification import decile_certificate

    observed = np.array([1., 0., np.nan, np.nan, np.nan, np.nan, np.nan, np.nan])
    strata = np.array([-1, -1, 0, 0, 0, 1, 1, 1])
    quotas = np.array([2, 1])
    switches = np.array([1, 1, 1, 1, 0, 0, 0, 1], dtype=bool)
    details = decile_certificate(observed, switches, strata, quotas)
    states, _ = all_completions(observed, [switches], (strata, quotas))
    for group, row in enumerate(details):
        group_defaults = states[:, switches & (strata == group)].sum(axis=1)
        assert row["min_hidden_switcher_defaults"] == group_defaults.min()
        assert row["max_hidden_switcher_defaults"] == group_defaults.max()
        assert row["known_switcher_defaults_fold"] == 1
        assert row["total_switchers_fold"] == 5
    totals = states[:, switches].sum(axis=1)
    assert totals.min() == 1 + sum(row["min_hidden_switcher_defaults"] for row in details)
    assert totals.max() == 1 + sum(row["max_hidden_switcher_defaults"] for row in details)
