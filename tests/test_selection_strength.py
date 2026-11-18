"""Selection-strength designs keep the acceptance share and the main design's random draws."""
import numpy as np
import pandas as pd
from scipy.special import expit

from paper11.data import Population
from paper11.selection_strength import DRAW_SEED, at_strength, bootstrap, run_split, summarize


def population(n=1600, seed=7):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 4))
    index = X[:, 0] - .5 * X[:, 1]
    propensity = .05 + .90 * expit(index)
    accepted = np.random.default_rng(DRAW_SEED).random(n) < propensity
    y = (rng.random(n) < expit(-1 - 1.2 * X[:, 0] + .6 * X[:, 2])).astype(int)
    rows = rng.permutation(n)
    split = (rows[:700], rows[700:950], rows[950:1250], rows[1250:])
    return Population(X, y, propensity, accepted, [split], ["a", "b", "c", "d"], {})


def test_strengths_match_the_acceptance_share_and_sharpen_selection():
    pop = population(6000)
    gaps = []
    for strength in ("0.5", "1", "4", "hard"):
        design = at_strength(pop, strength)
        assert abs(design.accepted.mean() - pop.accepted.mean()) < .03
        gaps.append(design.y[~design.accepted].mean() - design.y[design.accepted].mean())
    assert gaps == sorted(gaps)
    assert at_strength(pop, "main") is pop


def test_common_draws_make_sharper_rules_differ_only_near_the_boundary():
    pop = population(6000)
    soft, sharp = at_strength(pop, "1"), at_strength(pop, "4")
    u = np.random.default_rng(DRAW_SEED).random(len(pop.y))
    assert np.array_equal(soft.accepted, u < soft.propensity)
    assert np.array_equal(sharp.accepted, u < sharp.propensity)


def test_one_split_runs_and_summarizes_with_intervals():
    pop = at_strength(population(), "2")
    row, inputs = run_split(pop, pop.splits[0], 701)
    assert 0 < row["audited"] < (~pop.accepted).sum()
    for key in ("accepts_error", "bayes_logistic_error", "bayes_audited_error", "B+_test_abr"):
        assert np.isfinite(row[key])
    assert 0 <= row["logistic_reject_auc"] <= 1
    intervals = bootstrap(pop, [inputs], n_boot=5)
    rows = summarize("toy", "2", pd.DataFrame([dict(fold=1, **row)]), intervals)
    gap = next(r for r in rows if r["quantity"] == "B_minus_A")
    assert np.isclose(gap["estimate"], row["B_test_abr"] - row["A_test_abr"])
    assert gap["ci_low"] <= gap["ci_high"]
