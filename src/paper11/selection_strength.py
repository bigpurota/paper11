"""Selection strength, the reject model and a random audit of rejects.

Design, hypotheses and criteria: docs/selection-strength-protocol.md. The acceptance
share, splits, seeds, scorecards and metrics follow the main public experiment; only
the sharpness of historical selection and the information about rejects change.
"""
import argparse
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.special import expit, logit
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .data import load_population
from .hard_selection import FLOOR, SPAN, harden
from .methods import BASLConfig, fit_basl, fit_scorecard, integrated_bad_rate

STRENGTHS = ("main", "0.5", "1", "2", "4", "hard")
AUDIT_SHARE, AUDIT_WEIGHT = .05, 20.
DRAW_SEED = 1012  # the main design's acceptance draws: load_population's seed plus one
MODELS = ("A", "B", "A+", "B+")
ESTIMATORS = ("accepts", "bayes_logistic", "bayes_audited")


def at_strength(pop, strength):
    """Historical acceptance expit(s (index - c)) with the main design's acceptance share."""
    if strength == "main":
        return pop
    if strength == "hard":
        return harden(pop)
    s = float(strength)
    index = logit((pop.propensity - FLOOR) / SPAN)
    share = pop.accepted.mean()
    c = brentq(lambda c: expit(s * (index - c)).mean() - share, index.min() - 60 / s, index.max() + 60 / s)
    probability = expit(s * (index - c))
    accepted = np.random.default_rng(DRAW_SEED).random(len(index)) < probability
    return replace(pop, accepted=accepted, propensity=probability)


def logistic(X, y, weight=None):
    model = make_pipeline(StandardScaler(), LogisticRegression(C=1., max_iter=1500))
    return model.fit(X, y, logisticregression__sample_weight=weight)


def run_split(pop, split, seed):
    """Fit the four scorecards and three evaluators on one split; return a row and bootstrap inputs."""
    fit, stop, val, test = split
    X = SimpleImputer(strategy="median", keep_empty_features=True).fit(pop.X[fit]).transform(pop.X)
    a, y = pop.accepted, pop.y
    labels = np.where(a, y, np.nan)
    accepted, rejected = fit[a[fit]], fit[~a[fit]]
    audit = np.sort(np.random.default_rng(2026 + seed).choice(
        rejected, int(round(AUDIT_SHARE * len(rejected))), replace=False))
    # BASL samples positions in this pool. Keep the shared rejects in fit-split
    # order so that an empty audit gives exactly the unaudited treatment.
    unaudited = rejected[~np.isin(rejected, audit)]
    plus = np.r_[accepted, audit]
    weight = np.r_[np.ones(len(accepted)), np.full(len(audit), AUDIT_WEIGHT)]
    priors = {"logistic": logistic(X[accepted], y[accepted]), "audited": logistic(X[plus], y[plus], weight)}
    config = BASLConfig.empirical()

    def stop_prior(name):
        return priors[name].predict_proba(X[stop])[:, 1]

    models = {
        "A": fit_scorecard(X[accepted], y[accepted], seed=seed),
        "B": fit_basl(X[accepted], y[accepted], X[rejected], X[stop], labels[stop], stop_prior("logistic"),
                      seed=seed, config=config).model,
        "A+": fit_scorecard(X[plus], y[plus], seed=seed),
        "B+": fit_basl(X[plus], y[plus], X[unaudited], X[stop], labels[stop],
                       stop_prior("audited"), seed=seed, config=config).model,
    }
    score = models["A"].predict_proba(X[val])[:, 1]
    tests = {name: m.predict_proba(X[test])[:, 1] for name, m in models.items()}
    mask = a[val]
    prior_val = {name: m.predict_proba(X[val])[:, 1] for name, m in priors.items()}
    truth = integrated_bad_rate(y[test], tests["A"])
    same = integrated_bad_rate(y[val], score)
    estimates = {"accepts": integrated_bad_rate(y[val][mask], score[mask])}
    for name, p in prior_val.items():
        estimates["bayes_" + name] = integrated_bad_rate(np.where(mask, y[val], p), score)
    row = dict(accepted_share=a.mean(), bad_rate_accepted=y[a].mean(), bad_rate_rejected=y[~a].mean(),
               audited=len(audit))
    for name, est in estimates.items():
        row[f"{name}_error"] = est - truth
        row[f"{name}_same_cohort_error"] = est - same
    for name, s in tests.items():
        row[f"{name}_test_abr"] = integrated_bad_rate(y[test], s)
    rejects = ~mask
    for name, p in prior_val.items():
        row[f"{name}_reject_mean"] = p[rejects].mean()
        row[f"{name}_reject_auc"] = roc_auc_score(y[val][rejects], p[rejects])
    row["reject_bad_rate_validation"] = y[val][rejects].mean()
    inputs = dict(val=val, test=test, mask=mask, score=score, priors=prior_val, tests=tests)
    return row, inputs


def bootstrap(pop, inputs, n_boot=499, seed=4242):
    """Shared Poisson borrower weights across splits, with every fitted model held fixed."""
    rng = np.random.default_rng(seed)
    y = pop.y
    draws = []
    for b in range(n_boot + 1):
        w = np.ones(len(y)) if b == 0 else rng.poisson(1, len(y)).astype(float)
        errors = {k: [] for k in ESTIMATORS}
        gaps = {"B_minus_A": [], "Bplus_minus_Aplus": [], "Aplus_minus_A": []}
        for part in inputs:
            val, test, mask, score = part["val"], part["test"], part["mask"], part["score"]
            wt, wv = w[test], w[val]
            truth = integrated_bad_rate(y[test], part["tests"]["A"], wt)
            errors["accepts"].append(integrated_bad_rate(y[val][mask], score[mask], wv[mask]) - truth)
            for name, p in part["priors"].items():
                errors["bayes_" + name].append(integrated_bad_rate(np.where(mask, y[val], p), score, wv) - truth)
            abr = {k: integrated_bad_rate(y[test], s, wt) for k, s in part["tests"].items()}
            gaps["B_minus_A"].append(abr["B"] - abr["A"])
            gaps["Bplus_minus_Aplus"].append(abr["B+"] - abr["A+"])
            gaps["Aplus_minus_A"].append(abr["A+"] - abr["A"])
        rmse = {k: np.sqrt(np.mean(np.square(v))) for k, v in errors.items()}
        mean_gap = {k: np.mean(v) for k, v in gaps.items()}
        draws.append({
            "bayes_logistic_minus_accepts_rmse": rmse["bayes_logistic"] - rmse["accepts"],
            "bayes_audited_minus_logistic_rmse": rmse["bayes_audited"] - rmse["bayes_logistic"],
            **mean_gap,
            "audit_change_in_basl_gap": mean_gap["Bplus_minus_Aplus"] - mean_gap["B_minus_A"],
        })
    frame = pd.DataFrame(draws)
    return {k: (frame[k].iloc[0], frame[k].iloc[1:].quantile(.025), frame[k].iloc[1:].quantile(.975))
            for k in frame.columns}


def summarize(dataset, strength, folds, intervals):
    rows = []

    def add(quantity, estimate, low=np.nan, high=np.nan, fold_min=np.nan, fold_max=np.nan):
        rows.append(dict(dataset=dataset, strength=strength, quantity=quantity, estimate=estimate,
                         ci_low=low, ci_high=high, fold_min=fold_min, fold_max=fold_max))

    for column in ("accepted_share", "bad_rate_accepted", "bad_rate_rejected", "reject_bad_rate_validation",
                   "logistic_reject_mean", "audited_reject_mean", "logistic_reject_auc", "audited_reject_auc"):
        add(column, folds[column].mean())
    for name in ESTIMATORS:
        add(f"{name}_rmse", np.sqrt(np.mean(folds[f"{name}_error"] ** 2)))
        add(f"{name}_same_cohort_rmse", np.sqrt(np.mean(folds[f"{name}_same_cohort_error"] ** 2)))
    for name in MODELS:
        add(f"{name}_test_abr", folds[f"{name}_test_abr"].mean())
    per_fold = {"B_minus_A": folds.B_test_abr - folds.A_test_abr,
                "Bplus_minus_Aplus": folds["B+_test_abr"] - folds["A+_test_abr"],
                "Aplus_minus_A": folds["A+_test_abr"] - folds.A_test_abr}
    per_fold["audit_change_in_basl_gap"] = per_fold["Bplus_minus_Aplus"] - per_fold["B_minus_A"]
    for name, (estimate, low, high) in intervals.items():
        values = per_fold.get(name)
        add(name, estimate, low, high, *(values.agg(["min", "max"]) if values is not None else (np.nan, np.nan)))
    return rows


def run(out, cache, strengths=STRENGTHS, n_boot=499):
    out.mkdir(parents=True, exist_ok=True)
    fold_rows, summary = [], []
    for dataset in ("taiwan", "prosper"):
        base = load_population(dataset, cache)
        for strength in strengths:
            pop = at_strength(base, strength)
            rows, inputs = [], []
            for fold, split in enumerate(pop.splits, 1):
                print(f"{dataset}: strength {strength}, split {fold}/{len(pop.splits)}", flush=True)
                row, part = run_split(pop, split, 701 + fold)
                rows.append(dict(dataset=dataset, strength=strength, fold=fold, **row))
                inputs.append(part)
            fold_rows.extend(rows)
            summary.extend(summarize(dataset, strength, pd.DataFrame(rows), bootstrap(pop, inputs, n_boot)))
    pd.DataFrame(fold_rows).to_csv(out / "selection_strength_folds.csv", index=False, float_format="%.10g")
    pd.DataFrame(summary).to_csv(out / "selection_strength.csv", index=False, float_format="%.10g")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    args = parser.parse_args()
    run(args.out, args.cache)
