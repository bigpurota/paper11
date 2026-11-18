"""Exact sequential decision audit for a fixed 30% versus 50% credit expansion."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import hypergeom

from .bounds_experiment import score_inputs
from .data import load_population


INTERIM_LOOKS = (10, 25, 50, 100, 200)
ALPHA = .05


def positive_margin_threshold(switchers, visible_defaults):
    """Largest hidden default count giving strictly positive incremental margin.

    Margin per unit across the switchers is .10 - .55 * default_indicator.
    Use integer arithmetic so the break-even count belongs to the incumbent.
    """
    return (2 * switchers - 1) // 11 - visible_defaults


def stopping_boundaries(pool, threshold, looks=INTERIM_LOOKS, alpha=ALPHA):
    """At each review: expand at/below the low cutoff, retain at/above the high."""
    if not isinstance(pool, (int, np.integer)) or pool < 0 or not 0 < alpha < .5:
        raise ValueError("Expected a nonnegative integer pool and an error level in (0, 0.5).")
    if any(not isinstance(n, (int, np.integer)) or n <= 0 for n in looks):
        raise ValueError("Review sizes must be positive integers.")
    if threshold < 0:
        return {0: (-1, 0)}
    if threshold >= pool:
        return {0: (0, 1)}
    interim = sorted({int(n) for n in looks if 0 < n < pool})
    rules = {}
    for n in interim:
        counts = np.arange(n + 1)
        expand = counts[hypergeom.cdf(counts, pool, threshold + 1, n) <= alpha / len(interim)]
        retain = counts[hypergeom.sf(counts - 1, pool, threshold, n) <= alpha / len(interim)]
        rules[n] = (int(expand[-1]) if expand.size else -1,
                    int(retain[0]) if retain.size else n + 1)
    rules[pool] = (threshold, threshold + 1)
    return rules


def audit_distribution(pool, hidden_defaults, boundaries):
    """Exact first-stop probabilities over all random label orders, for a fixed truth."""
    if not 0 <= hidden_defaults <= pool:
        raise ValueError("Default count outside the hidden pool.")
    # live[k] is the joint probability of still auditing and having seen k defaults.
    live = np.ones(1)
    rows = []
    last_look = max(boundaries)
    for n in range(last_look + 1):
        counts = np.arange(len(live))
        if n in boundaries:
            low, high = boundaries[n]
            if low >= high:
                raise ValueError("Opposite decisions overlap.")
            p_expand = live[counts <= low].sum()
            p_retain = live[counts >= high].sum()
            live[(counts <= low) | (counts >= high)] = 0.
            rows.append(dict(labels=n, first_expand=p_expand, first_retain=p_retain,
                             unresolved=live.sum()))
        if n < last_look:
            supported = np.flatnonzero(live)
            next_default = (hidden_defaults - supported) / (pool - n)
            next_live = np.zeros(n + 2)
            next_live[supported] += live[supported] * (1 - next_default)
            next_live[supported + 1] += live[supported] * next_default
            live = next_live
    return rows


def summarize(paths, budget):
    frontier = [row for row in paths if row["labels"] <= budget]
    expand = sum(row["first_expand"] for row in frontier)
    retain = sum(row["first_retain"] for row in frontier)
    return expand, retain, frontier[-1]["unresolved"] if frontier else 1.


def run(out, cache):
    out.mkdir(parents=True, exist_ok=True)
    cohorts, trajectories = [], []
    for dataset in ("taiwan", "prosper"):
        pop = load_population(dataset, cache)
        for fold, split in enumerate(pop.splits, 1):
            validation = split[2]
            (score, _), _ = score_inputs(pop, split, 701 + fold)
            low, high = np.quantile(score, [.30, .50], method="inverted_cdf")
            switchers = (score > low) & (score <= high)
            visible = pop.accepted[validation]
            observed_defaults = int(pop.y[validation][switchers & visible].sum())
            hidden = switchers & ~visible
            pool = int(hidden.sum())
            threshold = positive_margin_threshold(int(switchers.sum()), observed_defaults)
            rules = stopping_boundaries(pool, threshold)
            # Retrospective assessment begins only after all stopping cutoffs are frozen.
            realized = int(pop.y[validation][hidden].sum())
            scenarios = {"retrospective_truth": realized}
            if 0 <= threshold < pool:
                scenarios.update(last_profitable=threshold, first_unprofitable=threshold + 1)
            for scenario, count in scenarios.items():
                path = audit_distribution(pool, count, rules)
                for row in path:
                    lo, hi = rules[row["labels"]]
                    trajectories.append(dict(dataset=dataset, fold=fold, scenario=scenario,
                                             default_count=count, expand_at_most=lo, retain_at_least=hi, **row))
                expand, retain, _ = summarize(path, pool)
                _, _, unresolved = summarize(path, 50)
                cohorts.append(dict(dataset=dataset, fold=fold, scenario=scenario,
                                    n_validation=len(score), switchers=int(switchers.sum()),
                                    visible_defaults=observed_defaults, hidden=pool, threshold=threshold,
                                    hidden_defaults=count, expand_profitable=count <= threshold,
                                    p_wrong=retain if count <= threshold else expand,
                                    p_unresolved_by_50=unresolved,
                                    mean_labels=sum(row["labels"] * (row["first_expand"] + row["first_retain"])
                                                    for row in path)))
    for name, rows in (("paths", trajectories), ("summary", cohorts)):
        pd.DataFrame(rows).to_csv(out / f"decision_audit_{name}.csv", index=False, float_format="%.12g")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    args = parser.parse_args()
    run(args.out, args.cache)
