"""Which exact aggregates determine policy margin differences on a fixed cohort?"""
import argparse
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from .bounds_experiment import LGD, TARGETS, score_inputs
from .data import load_population
from .empirical import INTEREST, cashflow
from .identification import rounded_prior_counts


@dataclass(frozen=True)
class InformationCheck:
    measurement_rank: int
    contrast_rank: int
    additional_rank: int
    identified: np.ndarray
    # For a nonidentified contrast, the corresponding residual is a direction
    # that leaves the measurements fixed and changes this contrast.
    residuals: np.ndarray


def row_basis(matrix):
    """Orthonormal basis for the row space, invariant to row units."""
    rows, columns = matrix.shape
    if not rows or not columns:
        return np.empty((0, columns))
    scales = np.max(np.abs(matrix), axis=1)
    scaled = matrix[scales > 0] / scales[scales > 0, None]
    if len(scaled) == 0:
        return np.empty((0, columns))
    scaled /= np.linalg.norm(scaled, axis=1, keepdims=True)
    _, singular, vt = np.linalg.svd(scaled, full_matrices=False)
    tolerance = np.finfo(float).eps * max(scaled.shape) * singular[0]
    return vt[singular > tolerance]


def check_information(contrasts, measurements):
    """Check row-space containment of each contrast in fixed linear measurements."""
    c, a = (np.asarray(value, dtype=float) for value in (contrasts, measurements))
    if c.ndim != 2 or a.ndim != 2 or c.shape[1] != a.shape[1]:
        raise ValueError("two matrices over the same hidden borrowers are required")
    if not np.isfinite(c).all() or not np.isfinite(a).all():
        raise ValueError("matrix entries must be finite")
    basis = row_basis(a)
    scales = np.max(np.abs(c), axis=1, initial=0, keepdims=True)
    scaled = c / np.where(scales > 0, scales, 1)
    residuals = scaled - (scaled @ basis.T) @ basis
    # Relative error per contrast, with exact zero rows resolved automatically.
    identified = np.linalg.norm(residuals, axis=1) <= (
        np.finfo(float).eps * max(1, *c.shape, *a.shape) * np.linalg.norm(scaled, axis=1)
    )
    joint_rank = len(row_basis(np.vstack([a, c])))
    return InformationCheck(len(basis), len(row_basis(c)), joint_rank - len(basis),
                            identified, residuals * scales)


def cohort_experiment(score, prior, historical_approval, truth):
    """Freeze designs from scores and mask, then reveal aggregate binary outcomes."""
    score, prior, historical_approval, truth = map(np.asarray, (score, prior, historical_approval, truth))
    if score.ndim != 1 or not score.size or any(
        v.shape != score.shape for v in (prior, historical_approval, truth)
    ):
        raise ValueError("scores, prior, historical decisions and repayments must be aligned vectors")
    if not np.isfinite(score).all() or not np.isin(historical_approval, [0, 1]).all():
        raise ValueError("finite scores and binary historical decisions required")
    if not np.isin(truth, [0, 1]).all():
        raise ValueError("retrospective repayments must be binary")
    historical_approval = historical_approval.astype(bool)
    truth = truth.astype(int)
    hidden = ~historical_approval
    cutoffs = np.quantile(score, TARGETS, method="inverted_cdf")
    policies = score[None, :] <= cutoffs[:, None]
    pairs = list(combinations(range(len(TARGETS)), 2))
    differences = np.stack([policies[j] & ~policies[i] for i, j in pairs])
    contrasts = differences[:, hidden].astype(int)
    # Prior ranks use only the missingness pattern. No known or hidden value is
    # required to choose either set of questions asked of the oracle.
    groups, _ = rounded_prior_counts(np.where(hidden, np.nan, 0.), prior)
    by_decile = groups[hidden] == np.arange(10)[:, None]
    by_band = np.diff(policies[:, hidden].astype(int), axis=0).astype(bool)
    summary, details = [], []
    n = len(truth)
    interest = Fraction(str(INTEREST))
    loss_per_default = (1 + interest) * Fraction(str(LGD))
    for design, groups_matrix in [("prior_deciles", by_decile), ("expansion_bands", by_band)]:
        check = check_information(contrasts, groups_matrix)
        # From here outcomes are opened by the retrospective oracle. Groups
        # may omit borrowers outside the four changed bands. Such borrowers
        # never contribute to the policy differences under this second design.
        measured = groups_matrix.astype(int)
        sizes = measured.sum(axis=1)
        default_counts = measured @ truth[hidden]
        pair_rows = []
        for (i, j), switched, c, identified in zip(pairs, differences, contrasts, check.identified):
            members = measured @ c
            if members.sum() != c.sum():
                raise ValueError("every switcher must belong to one measured group")
            # Min/max defaults among switchers, given actual group totals and
            # group capacities. Disjoint groups attain their endpoints jointly.
            known = int(truth[switched & historical_approval].sum())
            lo = known + np.maximum(0, default_counts - (sizes - members)).sum()
            hi = known + np.minimum(default_counts, members).sum()
            # Decimal loan terms admit exact comparisons at break-even.
            count = int(switched.sum())
            low_total = interest * count - loss_per_default * int(hi)
            high_total = interest * count - loss_per_default * int(lo)
            low, high = float(low_total / n), float(high_total / n)
            actual = float((cashflow(truth, policies[j], LGD) - cashflow(truth, policies[i], LGD)).mean())
            if not (low - 1e-12 <= actual <= high + 1e-12):
                raise AssertionError("fully observed margin falls outside aggregate bounds")
            if bool(identified) and lo != hi:
                raise AssertionError("linear reconstruction and sharp binary bounds disagree")
            pair_rows.append(dict(
                design=design, from_target=TARGETS[i], to_target=TARGETS[j],
                hidden_switchers=int(c.sum()), identified_for_all_expected_margins=bool(identified),
                lower_gain=low, upper_gain=high, fully_observed_gain=actual,
                exact_at_actual_binary_totals=bool(lo == hi),
                decision_at_actual_binary_totals=("expand" if low_total > 0 else
                                                 "retain" if high_total <= 0 else "undetermined"),
            ))
        rank = check.contrast_rank
        summary.append(dict(
            design=design, n_validation=n, n_hidden=int(hidden.sum()), n_policy_pairs=len(pairs),
            reported_sums=len(measured), measurement_rank=check.measurement_rank, contrast_rank=rank,
            additional_independent_sums=check.additional_rank,
            pairs_identified_for_all_expected_margins=int(check.identified.sum()),
            pairs_exact_at_actual_binary_totals=sum(r["exact_at_actual_binary_totals"] for r in pair_rows),
            decisions_settled_at_actual_binary_totals=sum(
                r["decision_at_actual_binary_totals"] != "undetermined" for r in pair_rows),
        ))
        details.extend(pair_rows)
    return summary, details


def run(out, cache):
    summary, pairs = [], []
    for name in ("taiwan", "prosper"):
        pop = load_population(name, cache)
        for fold, split in enumerate(pop.splits, 1):
            val = split[2]
            (score, prior), _ = score_inputs(pop, split, 701 + fold)
            by_design, by_pair = cohort_experiment(score, prior, pop.accepted[val], pop.y[val])
            for target, records in ((summary, by_design), (pairs, by_pair)):
                target.extend(dict(dataset=name, fold=fold, **row) for row in records)
    out.mkdir(parents=True, exist_ok=True)
    for suffix, rows in (("summary", summary), ("pairs", pairs)):
        pd.DataFrame(rows).to_csv(out / f"policy_information_{suffix}.csv", index=False,
                                  float_format="%.10g")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    args = parser.parse_args()
    run(args.out, args.cache)
