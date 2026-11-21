"""Two exploratory diagnostics added after the selection-strength protocol.

1. Full-information benchmark at the hard cutoff. The paper measures how much of the
   gap between accepted-only training and training with every outcome BASL recovers
   (24.8% in its simulation). We compute the same share for BASL, the 5% audit and both
   together on the selection-strength splits, seeds and audits.
2. Score drift. The population stability index from lecture 3 compares the
   accepted-only scorecard's score distribution in the fitting sample with later
   samples. Prosper's windows are chronological; Taiwan's random folds act as a placebo.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer

from .data import PERIODS, load_population
from .methods import fit_scorecard, integrated_bad_rate
from .selection_strength import at_strength, run_split

MODELS = ("A", "B", "A+", "B+", "full")
ROLES = ("fit", "stop", "validation", "test")


def recovery(accepted_only, method, full_information):
    """Share of the accepted-only to full-information ABR gap that a method closes."""
    return (accepted_only - method) / (accepted_only - full_information)


def psi(development, current, bins=10, floor=1e-6):
    """Population stability index over development-score quantile bins.

    PSI = sum_k (a_k - e_k) ln(a_k / e_k), with e the development and a the current
    share in bin k. Empty bins are floored so that the index stays finite.
    """
    development, current = np.asarray(development, float), np.asarray(current, float)
    edges = np.unique(np.quantile(development, np.linspace(0, 1, bins + 1)[1:-1]))
    e = np.bincount(np.searchsorted(edges, development, side="right"), minlength=len(edges) + 1) / len(development)
    a = np.bincount(np.searchsorted(edges, current, side="right"), minlength=len(edges) + 1) / len(current)
    e, a = np.maximum(e, floor), np.maximum(a, floor)
    return float(np.sum((a - e) * np.log(a / e)))


def full_information_split(pop, split, seed):
    """The four selection-strength scorecards plus one trained on every fitting-split outcome."""
    row, inputs = run_split(pop, split, seed)
    fit, _, _, test = split
    X = SimpleImputer(strategy="median", keep_empty_features=True).fit(pop.X[fit]).transform(pop.X)
    tests = dict(inputs["tests"], full=fit_scorecard(X[fit], pop.y[fit], seed=seed).predict_proba(X[test])[:, 1])
    abr = {name: integrated_bad_rate(pop.y[test], tests[name]) for name in MODELS}
    for name in MODELS[:-1]:
        if not np.isclose(abr[name], row[f"{name}_test_abr"], rtol=0, atol=1e-12):
            raise RuntimeError(f"{name} differs from the selection-strength fit")
    return abr, dict(test=test, tests=tests)


def recovery_intervals(pop, parts, n_boot=499, seed=4343):
    """Shared Poisson borrower weights, fitted models held fixed, ratio of fold-mean ABRs."""
    rng = np.random.default_rng(seed)
    draws = []
    for b in range(n_boot + 1):
        w = np.ones(len(pop.y)) if b == 0 else rng.poisson(1, len(pop.y)).astype(float)
        mean = {name: np.mean([integrated_bad_rate(pop.y[p["test"]], p["tests"][name], w[p["test"]])
                               for p in parts]) for name in MODELS}
        draws.append({f"recovery_{name}": recovery(mean["A"], mean[name], mean["full"]) for name in ("B", "A+", "B+")})
    frame = pd.DataFrame(draws)
    return {k: (frame[k].iloc[0], frame[k].iloc[1:].quantile(.025), frame[k].iloc[1:].quantile(.975)) for k in frame}


def full_information(cache, n_boot=499):
    fold_rows, summary = [], []
    for dataset in ("taiwan", "prosper"):
        pop = at_strength(load_population(dataset, cache), "hard")
        parts = []
        for fold, split in enumerate(pop.splits, 1):
            print(f"{dataset}: full-information benchmark, split {fold}/{len(pop.splits)}", flush=True)
            abr, part = full_information_split(pop, split, 701 + fold)
            fold_rows.append(dict(dataset=dataset, strength="hard", fold=fold,
                                  **{f"{name}_test_abr": abr[name] for name in MODELS}))
            parts.append(part)
        folds = pd.DataFrame(fold_rows[-len(parts):])
        for name in MODELS:
            summary.append(dict(dataset=dataset, quantity=f"{name}_test_abr", estimate=folds[f"{name}_test_abr"].mean()))
        for quantity, (estimate, low, high) in recovery_intervals(pop, parts, n_boot).items():
            name = quantity.removeprefix("recovery_")
            per_fold = recovery(folds.A_test_abr, folds[f"{name}_test_abr"], folds.full_test_abr)
            summary.append(dict(dataset=dataset, quantity=quantity, estimate=estimate, ci_low=low, ci_high=high,
                                fold_min=per_fold.min(), fold_max=per_fold.max()))
    return pd.DataFrame(fold_rows), pd.DataFrame(summary)


def score_drift(cache):
    rows = []
    for dataset in ("taiwan", "prosper"):
        pop = load_population(dataset, cache)
        for fold, split in enumerate(pop.splits, 1):
            fit = split[0]
            accepted = fit[pop.accepted[fit]]
            X = SimpleImputer(strategy="median", keep_empty_features=True).fit(pop.X[fit]).transform(pop.X)
            model = fit_scorecard(X[accepted], pop.y[accepted], seed=701 + fold)
            development = model.predict_proba(X[fit])[:, 1]
            for k, (role, part) in enumerate(zip(ROLES, split)):
                window = dict(start=PERIODS[k][0], end=PERIODS[k][1]) if dataset == "prosper" else {}
                rows.append(dict(dataset=dataset, fold=fold, role=role, n=len(part), **window,
                                 mean_score=model.predict_proba(X[part])[:, 1].mean(),
                                 psi=psi(development, model.predict_proba(X[part])[:, 1])))
    return pd.DataFrame(rows)


def run(out, cache, n_boot=499):
    out.mkdir(parents=True, exist_ok=True)
    folds, summary = full_information(cache, n_boot)
    folds.to_csv(out / "full_information_folds.csv", index=False, float_format="%.10g")
    summary.to_csv(out / "full_information.csv", index=False, float_format="%.10g")
    score_drift(cache).to_csv(out / "score_drift.csv", index=False, float_format="%.10g")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    args = parser.parse_args()
    run(args.out, args.cache)
