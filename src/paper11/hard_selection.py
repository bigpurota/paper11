"""Sensitivity: the same public experiment under a hard historical acceptance cutoff.

The main design accepts each applicant with probability 0.05 + 0.90 expit(index), so every
applicant can be observed. Here the same index and the same acceptance share are kept, but
acceptance becomes deterministic: no historical reject resembles an accepted case on the
index, as with a scorecard cutoff. Folds, seeds, models, priors and metrics are unchanged.
"""
import argparse
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import logit
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .data import load_population
from .empirical import evaluation_uncertainty, paired_uncertainty, run_fold

FLOOR, SPAN = .05, .90


def harden(pop):
    """Accept the same share of applicants with the highest index, without randomness."""
    index = logit((pop.propensity - FLOOR) / SPAN)
    share = pop.accepted.mean()
    cutoff = np.quantile(index, 1 - share, method="inverted_cdf")
    # The index has ties. Keep each tied group on one side, choosing the side whose
    # acceptance share is closer to the soft rule's realized share.
    accepted = min((index >= cutoff, index > cutoff), key=lambda rule: abs(rule.mean() - share))
    # Known acceptance probabilities are now exactly 0 or 1.
    return replace(pop, accepted=accepted, propensity=accepted.astype(float))


def selection_profile(pop):
    a = pop.accepted
    return dict(accepted_share=a.mean(), bad_rate_accepted=pop.y[a].mean(),
                bad_rate_rejected=pop.y[~a].mean())


def prior_diagnostics(pop):
    """How the accepts-trained logistic prior describes validation rejects: level and ranking.

    The model matches the main experiment's prior; BASL's pseudo-labeler is a logistic
    model of the same kind. Results are averaged over splits.
    """
    level, actual, ranking = [], [], []
    for fit, _, val, _ in pop.splits:
        imputer = SimpleImputer(strategy="median", keep_empty_features=True).fit(pop.X[fit])
        X = imputer.transform(pop.X)
        accepted = fit[pop.accepted[fit]]
        rejected = ~pop.accepted[val]
        model = make_pipeline(StandardScaler(), LogisticRegression(C=1., max_iter=1500))
        # Score the same whole validation batch as the primary evaluation, then
        # select rejects. Changing the BLAS batch shape can break numerical ties.
        prior = model.fit(X[accepted], pop.y[accepted]).predict_proba(X[val])[:, 1][rejected]
        outcomes = pop.y[val][rejected]
        level.append(prior.mean())
        actual.append(outcomes.mean())
        ranking.append(roc_auc_score(outcomes, prior))
    return dict(reject_prior_mean=np.mean(level), reject_bad_rate_validation=np.mean(actual),
                reject_prior_auc=np.mean(ranking))


def run(out, cache):
    out.mkdir(parents=True, exist_ok=True)
    rows, training = [], []
    for dataset in ("taiwan", "prosper"):
        soft = load_population(dataset, cache)
        pop = harden(soft)
        for design, frame in (("soft", soft), ("hard", pop)):
            profile = {**selection_profile(frame), **prior_diagnostics(frame)}
            rows.extend(dict(dataset=dataset, design=design, quantity=k, estimate=v) for k, v in profile.items())
        paired, inputs, evaluation = [], [], []
        for fold, split in enumerate(pop.splits, 1):
            print(f"{dataset}: hard cutoff, split {fold}/{len(pop.splits)}", flush=True)
            tables, heldout, estimate_inputs = run_fold(pop, split, 701 + fold)
            paired.append(heldout)
            inputs.append(estimate_inputs)
            training.extend(dict(dataset=dataset, fold=fold, **r) for r in tables["training"])
            evaluation.extend(r for r in tables["evaluation"] if r["metric"] == "abr")
        ev = pd.DataFrame(evaluation)
        for method in ("accepts", "bayes"):
            part = ev[ev.method == method]
            rows.append(dict(dataset=dataset, design="hard", quantity=f"{method}_eval_rmse_abr",
                             estimate=np.sqrt(np.mean(part.error ** 2))))
            rows.append(dict(dataset=dataset, design="hard", quantity=f"{method}_same_cohort_rmse_abr",
                             estimate=np.sqrt(np.mean(part.within_cohort_error ** 2))))
        trained = pd.DataFrame([r for r in training if r["dataset"] == dataset]).groupby("method").abr.mean()
        for method in ("accepts", "basl", "basl_guarded", "hard_cutoff", "logit"):
            rows.append(dict(dataset=dataset, design="hard", quantity=f"{method}_test_abr", estimate=trained[method]))
        contrasts = list(paired_uncertainty(paired)) + [evaluation_uncertainty(inputs, len(pop.y))]
        for c in contrasts:
            if c["contrast"] in ("basl_minus_accepts_abr", "bayes_minus_accepts_rmse_abr"):
                rows.append(dict(dataset=dataset, design="hard", quantity=c["contrast"], estimate=c["estimate"],
                                 ci_low=c["ci_low"], ci_high=c["ci_high"]))
    pd.DataFrame(rows).to_csv(out / "hard_selection.csv", index=False, float_format="%.10g")
    pd.DataFrame(training).to_csv(out / "hard_selection_training.csv", index=False, float_format="%.10g")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    args = parser.parse_args()
    run(args.out, args.cache)
