from itertools import combinations
from math import comb

import numpy as np

from paper11.decision_audit import (audit_distribution, positive_margin_threshold,
                                    stopping_boundaries, summarize)


def test_break_even_counts_as_keep_and_one_label_changes_the_sign():
    assert positive_margin_threshold(11, 0) == 1
    assert positive_margin_threshold(11, 2) == -1
    assert positive_margin_threshold(12, 1) == 1


def test_decision_without_sampling_and_census_only():
    for pool, threshold, count, expected in [(0, -1, 0, 0), (0, 0, 0, 1),
                                             (9, 9, 2, 1), (9, -1, 4, 0)]:
        path = audit_distribution(pool, count, stopping_boundaries(pool, threshold))
        assert path[0]["labels"] == 0 and path[0]["first_expand"] == expected
    rows = audit_distribution(5, 2, stopping_boundaries(5, 1))
    assert rows == [dict(labels=5, first_expand=0., first_retain=1., unresolved=0.)]


def test_first_stop_distribution_matches_all_possible_audit_orders():
    pool, threshold = 10, 3
    rules = stopping_boundaries(pool, threshold, looks=(3, 6, 8), alpha=.2)
    for count in range(pool + 1):
        enumerated = {n: np.zeros(2) for n in rules}
        for positions in combinations(range(pool), count):
            for n, (low, high) in rules.items():
                seen = sum(position < n for position in positions)
                if seen <= low or seen >= high:
                    enumerated[n][int(seen >= high)] += 1 / comb(pool, count)
                    break
        path = audit_distribution(pool, count, rules)
        for row in path:
            np.testing.assert_allclose([row["first_expand"], row["first_retain"]],
                                       enumerated[row["labels"]], atol=1e-12)
        expand, retain, pending = summarize(path, pool)
        assert pending == 0
        assert (retain if count <= threshold else expand) <= .2 + 1e-12


def test_wrong_direction_is_controlled_over_every_possible_population():
    pool = 47
    for threshold in (0, 8, 23, 46):
        rules = stopping_boundaries(pool, threshold, looks=(5, 11, 19, 32, 46))
        for count in range(pool + 1):
            path = audit_distribution(pool, count, rules)
            expand, retain, pending = summarize(path, pool)
            assert (retain if count <= threshold else expand) <= .05 + 1e-12
            np.testing.assert_allclose(expand + retain, 1.)
            assert pending == 0
