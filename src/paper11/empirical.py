"""Experiments I/II and a locked lending policy on public borrower cohorts."""
import argparse
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .audit_design import randomized_audit
from .data import load_population
from .methods import (BASLConfig, bayesian_metrics, fit_basl, fit_hard_cutoff, fit_ipw,
                      fit_scorecard, integrated_bad_rate, metrics)

METRICS = ["auc", "brier", "pauc", "abr"]
RATES = np.arange(10, 51, 5) / 100
LGDS = (.25, .50, .75, 1.0)
INTEREST = .10


def odds_shift(p, factor):
    return factor * p / (1 - p + factor * p)


def cashflow(y, admitted, lgd):
    """Realized margin on unit principal, per person approached (Eq. 2)."""
    return admitted * (INTEREST - (1 + INTEREST) * lgd * y)


def select_policy(score, observed, prior, propensity, lgd):
    """Use a common cutoff grid; the accepted-only estimator also sees application scores."""
    visible = np.isfinite(observed)
    choices = []
    for strategy in ("accepts", "bayes", "ipw"):
        curve = []
        for rate in RATES:
            cutoff = np.quantile(score, rate, method="inverted_cdf")
            approved = score <= cutoff
            use = approved & visible
            if strategy == "bayes":
                default = np.where(visible, observed, prior)[approved].mean()
            elif strategy == "accepts" and use.any():
                default = observed[use].mean()
            elif strategy == "ipw" and use.any():
                default = np.average(observed[use], weights=1 / propensity[use])
            else:
                continue
            profit = approved.mean() * (INTEREST - (1 + INTEREST) * lgd * default)
            curve.append((profit, cutoff, rate))
        if not curve:
            raise ValueError("Empty validation policy grid")
        # Conservative tie break: first (lowest target rate) on the grid.
        _, cutoff, rate = max(curve, key=lambda row: row[0])
        choices.append((strategy, cutoff, rate))
    return choices


def risk_lift(y, score, fraction=.1):
    """Default lift in the riskiest fraction with fractional inclusion of score ties."""
    threshold = np.quantile(score, 1 - fraction, method="inverted_cdf")
    high, tied = score > threshold, score == threshold
    tie_share = np.clip((fraction * len(y) - high.sum()) / tied.sum(), 0, 1)
    return (y[high].sum() + tie_share * y[tied].sum()) / (fraction * y.sum())


def calibration_rows(y, score):
    # Equal-frequency groups of predictions, with group means and honest counts.
    bins = np.unique(np.quantile(score, np.linspace(0, 1, 11)))[1:-1]
    group = np.digitize(score, bins)
    for i in np.unique(group):
        members = group == i
        yield dict(bin=int(i + 1), n=int(members.sum()), predicted=score[members].mean(),
                   observed=y[members].mean())


def run_fold(pop, split, seed):
    fit, stop, val, test = split
    imp = SimpleImputer(strategy="median", keep_empty_features=True).fit(pop.X[fit])
    X = imp.transform(pop.X)
    a, prop = pop.accepted, pop.propensity
    labels = np.where(a, pop.y, np.nan)
    accepted, rejected = fit[a[fit]], fit[~a[fit]]
    xa, ya, xr = X[accepted], labels[accepted], X[rejected]
    logit = make_pipeline(StandardScaler(), LogisticRegression(C=1., max_iter=1500)).fit(xa, ya)

    def predict(model, rows):
        return model.predict_proba(X[rows])[:, 1]

    base = fit_scorecard(xa, ya, seed=seed)
    basl = fit_basl(xa, ya, xr, X[stop], labels[stop], predict(logit, stop), seed=seed,
                    config=BASLConfig.empirical())
    guard = fit_basl(xa, ya, xr, X[stop], labels[stop], predict(logit, stop), seed=seed,
                     config=replace(BASLConfig.empirical(), allow_round_zero=True))
    models = {"basl_guarded": guard.model, "logit": logit, "accepts": base, "basl": basl.model,
              "ipw": fit_ipw(xa, ya, prop[accepted], seed=seed),
              "hard_cutoff": fit_hard_cutoff(xa, ya, xr, seed=seed)}
    score, prior = predict(base, val), predict(logit, val)
    mask = a[val]
    estimates = {"accepts": metrics(labels[val][mask], score[mask]),
                 "ipw": metrics(labels[val][mask], score[mask], 1 / prop[val][mask])}
    for factor, name in ((.5, "bayes_odds_half"), (1, "bayes"), (2, "bayes_odds_double")):
        p = odds_shift(prior, factor)
        est = bayesian_metrics(labels[val], score, p, seed=seed, min_draws=200, max_draws=200)
        # Linear in the missing labels: use the exact expectation for the primary endpoint.
        est["abr"] = integrated_bad_rate(np.where(mask, labels[val], p), score)
        estimates[name] = est

    policies = [(lgd, *choice) for lgd in LGDS
                for choice in select_policy(score, labels[val], prior, prop[val], lgd)]
    # Holdout labels enter here, after every fitted model, prior and cutoff has been fixed.
    y = pop.y[test]
    scores = {method: predict(model, test) for method, model in models.items()}
    training, calibration, evaluation = [], [], []
    for name, s in scores.items():
        training.append(dict(method=name, **metrics(y, s), lift10=risk_lift(y, s)))
        calibration.extend(dict(method=name, **row) for row in calibration_rows(y, s))
    truth = metrics(y, scores["accepts"])
    validation_truth = metrics(pop.y[val], score)
    for name, est in estimates.items():
        for metric in METRICS:
            evaluation.append(dict(method=name, metric=metric, estimate=est[metric], truth=truth[metric],
                                   error=est[metric] - truth[metric],
                                   validation_oracle_audit=validation_truth[metric],
                                   within_cohort_error=est[metric] - validation_truth[metric]))
    business, base_cash = [], {}
    for lgd, name, cutoff, target in policies:
        taken = scores["accepts"] <= cutoff
        profit = cashflow(y, taken, lgd)
        business.append(dict(lgd=lgd, method=name, cutoff=cutoff, validation_target=target,
                             test_approval=taken.mean(), n_issued=int(taken.sum()),
                             test_abr=y[taken].mean(), profit_per_applicant=profit.mean(),
                             profit_per_issued=profit[taken].mean()))
        if lgd == .5:
            base_cash[name] = profit
    parts = []
    for role, rows in zip(["fit", "stop", "validation", "test"], split):
        weights = 1 / prop[rows][a[rows]]
        parts.append(dict(role=role, n=len(rows), accepted=int(a[rows].sum()),
                          visible_bad_rate=labels[rows][a[rows]].mean(),
                          population_bad_rate_audit=pop.y[rows].mean(), min_propensity=prop[rows].min(),
                          max_weight=weights.max(), weight_ess=weights.sum()**2 / (weights @ weights)))
    history = [dict(**r, selected_round=basl.best_round, stop_reason=basl.stop_reason) for r in basl.history]
    tables = dict(training=training, evaluation=evaluation, calibration=calibration, policy=business,
                  partitions=parts, basl=history)
    paired = (y, scores["accepts"], scores["basl"], base_cash["bayes"] - base_cash["accepts"])
    tables["audit_budget"] = list(randomized_audit(pop.y[val], labels[val], score, prior, seed=seed))
    inputs = (val, test, labels[val], score, prior, y, scores["accepts"])
    return tables, paired, inputs


def paired_uncertainty(folds, n_boot=499, seed=7711):
    """Resample paired borrowers within each holdout; preserve all fold sizes."""
    rng = np.random.default_rng(seed)
    estim = np.zeros((n_boot + 1, 3))
    for y, s0, s1, delta in folds:
        for b in range(n_boot + 1):
            w = np.ones(len(y)) if b == 0 else rng.multinomial(len(y), np.full(len(y), 1/len(y)))
            abr_delta = integrated_bad_rate(y, s1, w) - integrated_bad_rate(y, s0, w)
            estim[b] += (abr_delta, np.average(delta, weights=w),
                         np.average((y-s1)**2 - (y-s0)**2, weights=w))
    estim /= len(folds)
    for column, name in enumerate(["basl_minus_accepts_abr", "bayes_minus_accepts_profit_at_lgd50",
                                    "basl_minus_accepts_brier"]):
        bs = estim[1:, column]
        yield dict(contrast=name, estimate=estim[0, column], ci_low=np.quantile(bs, .025),
                   ci_high=np.quantile(bs, .975), bootstrap_se=bs.std(ddof=1),
                   mde_80pct_normal_approx=(1.96 + .842) * bs.std(ddof=1), n_boot=n_boot)


def evaluation_uncertainty(inputs, n, n_boot=499, seed=119):
    """Use shared borrower weights across folds whenever a row recurs as validation."""
    rng = np.random.default_rng(seed)
    delta = []
    for i in range(n_boot + 1):
        w = np.ones(n) if i == 0 else rng.poisson(1, n)
        errs = []
        for val, test, labels, score, prior, y, test_score in inputs:
            a = np.isfinite(labels)
            truth = integrated_bad_rate(y, test_score, w[test])
            accept = integrated_bad_rate(labels[a], score[a], w[val][a])
            bayes = integrated_bad_rate(np.where(a, labels, prior), score, w[val])
            errs.append([accept - truth, bayes - truth])
        rmse_a, rmse_b = np.sqrt(np.mean(np.square(errs), axis=0))
        delta.append(rmse_b - rmse_a)
    se = np.std(delta[1:], ddof=1)
    return dict(contrast="bayes_minus_accepts_rmse_abr", estimate=delta[0],
                ci_low=np.quantile(delta[1:], .025), ci_high=np.quantile(delta[1:], .975),
                bootstrap_se=se, mde_80pct_normal_approx=np.nan, n_boot=n_boot)


def run(out, cache):
    out.mkdir(parents=True, exist_ok=True)
    tables = {}
    for dataset in ("taiwan", "prosper"):
        pop = load_population(dataset, cache)
        tables.setdefault("cohort", []).append(dict(dataset=dataset, **pop.audit))
        paired, inputs = [], []
        for fold, split in enumerate(pop.splits, 1):
            print(f"{dataset}: fitting split {fold}/{len(pop.splits)}", flush=True)
            part, heldout, estimate_inputs = run_fold(pop, split, 701 + fold)
            paired.append(heldout)
            inputs.append(estimate_inputs)
            for key, rows in part.items():
                tables.setdefault(key, []).extend(dict(dataset=dataset, fold=fold, **r) for r in rows)
        tables.setdefault("uncertainty", []).extend(dict(dataset=dataset, **r) for r in paired_uncertainty(paired))
        tables["uncertainty"].append(dict(dataset=dataset, **evaluation_uncertainty(inputs, len(pop.y))))
    for name, rows in tables.items():
        pd.DataFrame(rows).to_csv(out / f"{name}.csv", index=False, float_format="%.10g")
    ev = pd.DataFrame(tables["evaluation"])
    ev["sq"] = ev.error**2
    summary = ev.groupby(["dataset", "method", "metric"]).agg(mse=("sq", "mean"), folds=("fold","count")).reset_index()
    summary["rmse"] = np.sqrt(summary.pop("mse"))
    summary.to_csv(out / "evaluation_rmse.csv", index=False, float_format="%.10g")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    args = parser.parse_args()
    run(args.out, args.cache)
