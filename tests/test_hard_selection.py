"""The hard-cutoff sensitivity keeps the acceptance share and removes overlap on the index."""
import numpy as np
from scipy.special import expit

from paper11.data import Population
from paper11.hard_selection import harden


def population(index, seed=3):
    rng = np.random.default_rng(seed)
    propensity = .05 + .90 * expit(index)
    accepted = rng.random(len(index)) < propensity
    y = (rng.random(len(index)) < expit(-index)).astype(int)
    return Population(index[:, None], y, propensity, accepted, [], ["index"], {})


def test_hard_rule_separates_accepts_from_rejects_on_the_index():
    index = np.random.default_rng(1).normal(size=4000)
    soft = population(index)
    hard = harden(soft)
    assert hard.X[hard.accepted, 0].min() > hard.X[~hard.accepted, 0].max()
    assert set(np.unique(hard.propensity)) == {0., 1.}
    assert abs(hard.accepted.mean() - soft.accepted.mean()) < 1 / len(index) + 1e-12
    assert np.array_equal(hard.y, soft.y)


def test_tied_index_values_stay_on_one_side():
    index = np.repeat(np.linspace(-2, 2, 9), 50)
    soft = population(index)
    hard = harden(soft)
    for value in np.unique(index):
        group = hard.accepted[index == value]
        assert group.all() or not group.any()
    shares = [(index >= v).mean() for v in np.unique(index)]
    assert abs(hard.accepted.mean() - soft.accepted.mean()) == min(abs(s - soft.accepted.mean()) for s in shares)


def test_prior_diagnostics_report_level_and_ranking_on_validation_rejects():
    from paper11.hard_selection import prior_diagnostics
    rng = np.random.default_rng(5)
    index = rng.normal(size=3000)
    pop = population(index)
    rows = rng.permutation(len(index))
    pop.splits = [(rows[:1500], rows[1500:1800], rows[1800:2400], rows[2400:])]
    out = prior_diagnostics(harden(pop))
    assert set(out) == {"reject_prior_mean", "reject_bad_rate_validation", "reject_prior_auc"}
    assert all(0 <= v <= 1 for v in out.values())
    rejected = pop.splits[0][2][~harden(pop).accepted[pop.splits[0][2]]]
    assert np.isclose(out["reject_bad_rate_validation"], pop.y[rejected].mean())
