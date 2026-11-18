from itertools import combinations, product

import numpy as np
import pytest

from paper11.bounds_experiment import LGD, TARGETS
from paper11.empirical import cashflow
from paper11.policy_information import check_information, cohort_experiment


def test_crossing_policies_recovered_from_redundant_reexpressed_measurements():
    # The policies overlap without nesting. The third entrant displaces another.
    decisions = np.array([[1, 1, 0, 0], [0, 1, 1, 0], [1, 0, 0, 1]])
    contrasts = np.stack([decisions[j] - decisions[i] for i, j in combinations(range(3), 2)])
    u, v = contrasts[:2]
    a = np.stack([u + v, 7 * (u - v), 13 * u, np.zeros_like(u)])
    info = check_information(contrasts, a)
    assert (info.contrast_rank, info.measurement_rank, info.additional_rank) == (2, 2, 0)
    assert info.identified.all()
    margins = np.array([.09, -.07, .01, -.03])
    # Independent reconstruction via a known factorization.
    first, second = a[:2] @ margins
    predicted = [(first + second / 7) / 2, (first - second / 7) / 2, -second / 7]
    np.testing.assert_allclose(contrasts @ margins, predicted, atol=1e-12)


def test_null_direction_preserves_groups_and_changes_margin_without_changing_sign():
    # The sum for applicant 1's risk group cannot determine applicant 1's margin.
    a = np.array([[1, 1, 0, 0], [0, 0, 1, 1]])
    c = np.array([[1, 0, 0, 0], [1, 1, 1, 1]])
    check = check_information(c, a)
    assert check.additional_rank == 1
    np.testing.assert_array_equal(check.identified, [False, True])
    direction = check.residuals[0]
    np.testing.assert_allclose(a @ direction, [0, 0], atol=1e-12)
    center = np.full(4, .04)
    x, y = center + .02 * direction, center - .02 * direction
    np.testing.assert_allclose(a @ x, a @ y)
    assert 0 < c[0] @ y < c[0] @ x < .10
    assert np.isclose(c[1] @ x, c[1] @ y)


def test_rank_drops_for_empty_hidden_band_and_unit_changes_preserve_sufficiency():
    bands = np.array([[1, 0, 0], [0, 0, 0], [0, 1, 0], [0, 0, 1]])
    cuts = np.vstack([np.zeros(3, dtype=int), bands.cumsum(axis=0)])
    contrasts = np.stack([cuts[j] - cuts[i] for i, j in combinations(range(5), 2)])
    check = check_information(contrasts, bands * np.array([1e-70, 1, 1e70, .5])[:, None])
    assert check.contrast_rank == check.measurement_rank == 3
    assert check.identified.all()
    missing = check_information(contrasts, bands[:3])
    assert missing.additional_rank == 1
    assert missing.identified.sum() == 6


def test_continuous_lower_bound_is_not_a_binary_encoding_lower_bound():
    c, a = np.eye(3), np.array([[1, 2, 4]])
    binary_states = np.array(list(product([0, 1], repeat=3)))
    assert len(np.unique(binary_states @ a.T)) == 2**3
    assert not check_information(c, a).identified.any()


def test_pairwise_binary_bounds_match_every_permitted_hidden_assignment():
    n = 100
    score = np.arange(n, dtype=float)
    prior = (np.arange(n) * 19 % n) / n
    visible = np.ones(n, bool)
    visible[[2, 10, 16, 21, 30, 34, 36, 40, 44, 46, 50, 82]] = False
    truth = ((3 * np.arange(n) + 2) % 7 < 3).astype(int)
    summary, rows = cohort_experiment(score, prior, visible, truth)
    assert len(summary) == 2 and len(rows) == 20
    cut = np.quantile(score, TARGETS, method="inverted_cdf")
    masks = score[None, :] <= cut[:, None]
    hidden = np.flatnonzero(~visible)
    groups = np.array_split(np.argsort(prior[hidden], kind="stable"), 10)
    matrices = {
        "prior_deciles": np.vstack([np.isin(np.arange(len(hidden)), g) for g in groups]),
        "expansion_bands": np.diff(masks[:, hidden].astype(int), axis=0),
    }
    binary = np.array(list(product([0, 1], repeat=len(hidden))))
    for design, measurements in matrices.items():
        totals = measurements @ truth[hidden]
        states = binary[np.all(binary @ measurements.T == totals, axis=1)]
        world = np.tile(truth, (len(states), 1))
        world[:, hidden] = states
        v = cashflow(world, 1, LGD) @ masks.T / n
        for row in [r for r in rows if r["design"] == design]:
            i, j = [np.flatnonzero(TARGETS == row[k])[0] for k in ("from_target", "to_target")]
            gains = v[:, j] - v[:, i]
            np.testing.assert_allclose([row["lower_gain"], row["upper_gain"]],
                                       [gains.min(), gains.max()], atol=1e-12)
            assert row["exact_at_actual_binary_totals"] == np.isclose(gains.min(), gains.max())


def test_audit_separates_design_from_extreme_realized_outcomes_and_handles_no_switchers():
    score = np.arange(100)
    prior = np.full(100, .25)
    history = np.arange(100) % 3 == 1
    mixed = np.arange(100) % 4 == 1
    extreme, _ = cohort_experiment(score, prior, history, np.zeros(100))
    changed, _ = cohort_experiment(score, prior, history, mixed)
    for x, y in zip(extreme, changed):
        for k in ["measurement_rank", "contrast_rank", "additional_independent_sums",
                  "pairs_identified_for_all_expected_margins"]:
            assert x[k] == y[k]
        assert x["pairs_exact_at_actual_binary_totals"] == 10
    tied, rows = cohort_experiment(np.zeros(100), prior, np.ones(100, bool), mixed)
    assert all(r["contrast_rank"] == 0 and r["decisions_settled_at_actual_binary_totals"] == 10 for r in tied)
    assert {r["decision_at_actual_binary_totals"] for r in rows} == {"retain"}
    with pytest.raises(ValueError, match="same hidden borrowers"):
        check_information([[1, 2]], [[1]])
    with pytest.raises(ValueError, match="finite"):
        check_information([[np.nan]], [[1]])
