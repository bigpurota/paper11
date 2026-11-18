"""Validate worst-case policy gains on the public credit cohorts."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .bounds import policy_bounds, select_expansion, tipping_gamma
from .data import load_population
from .empirical import cashflow
from .methods import fit_scorecard


TARGETS = np.array([.30, .35, .40, .45, .50])
GAMMAS = (1., 1.25, 1.5, 2., 3., 5., 10., np.inf)
BUDGETS = (0., .0025)
LGD = .5


def design(score, observed, prior):
    """Read validation inputs only. Freeze cutoffs, candidate choices and bounds."""
    cutoffs = np.quantile(score, TARGETS, method="inverted_cdf")
    decisions = score[None, :] <= cutoffs[:, None]
    baseline = decisions[0]
    prior_deltas = [policy_bounds(observed, prior, 1., a, baseline)[2].lower for a in decisions]
    frontier, tipping, choices = [], [], []
    for rate, cutoff, candidate in zip(TARGETS, cutoffs, decisions):
        for budget in BUDGETS:
            radius = tipping_gamma(observed, prior, candidate, baseline, budget=budget)
            tipping.append(dict(target=rate, budget=budget, cutoff=cutoff, tipping_gamma=radius,
                                already_fails_at_prior=bool(np.isnan(radius)),
                                valid_without_prior=bool(np.isposinf(radius))))
    for gamma in GAMMAS:
        lower = []
        for rank, candidate in enumerate(decisions):
            abr, margin, delta = policy_bounds(observed, prior, gamma, candidate, baseline)
            lower.append(delta.lower)
            switched = candidate != baseline
            frontier.append(dict(gamma=gamma, target=TARGETS[rank], cutoff=cutoffs[rank],
                                 n_validation=len(score), n_approved=int(candidate.sum()),
                                 n_changed=int(switched.sum()),
                                 n_changed_unlabeled=int((switched & np.isnan(observed)).sum()),
                                 abr_lower=abr.lower, abr_upper=abr.upper, margin_lower=margin.lower,
                                 margin_upper=margin.upper, delta_lower=delta.lower,
                                 delta_upper=delta.upper, prior_mean_gain=prior_deltas[rank]))
        for budget in BUDGETS:
            idx = select_expansion(TARGETS, prior_deltas, lower, budget)
            choices.append(dict(gamma=gamma, budget=budget, target=TARGETS[idx], cutoff=cutoffs[idx],
                                baseline_cutoff=cutoffs[0], validation_worst_gain=lower[idx],
                                validation_prior_mean_gain=prior_deltas[idx]))
    return frontier, tipping, choices


def score_inputs(pop, split, seed):
    fit, _, val, test = split
    imp = SimpleImputer(strategy="median", keep_empty_features=True).fit(pop.X[fit])
    accept = fit[pop.accepted[fit]]
    x, y = imp.transform(pop.X[accept]), pop.y[accept]
    model = fit_scorecard(x, y, seed=seed)
    prior = make_pipeline(StandardScaler(), LogisticRegression(C=1., max_iter=1500)).fit(x, y)

    def predict(rows):
        xx = imp.transform(pop.X[rows])
        pd = prior.predict_proba(xx)[:, 1]
        # A finite log-odds box requires an interior reference probability.
        return model.predict_proba(xx)[:, 1], np.clip(pd, 1e-8, 1 - 1e-8)

    return predict(val), predict(test)


def evaluate_choices(choices, score, prior, observed, truth):
    audit = []
    for rule in choices:
        a, b = score <= rule["cutoff"], score <= rule["baseline_cutoff"]
        abr, _, delta = policy_bounds(observed, prior, rule["gamma"], a, b)
        abr_free, _, delta_free = policy_bounds(observed, None, np.inf, a, b)
        real_abr = truth[a].mean() if a.any() else np.nan
        real_delta = (cashflow(truth, a, LGD) - cashflow(truth, b, LGD)).mean()
        if a.any() and not abr_free.lower - 1e-12 <= real_abr <= abr_free.upper + 1e-12:
            raise AssertionError("realized test ABR outside sharp binary bounds")
        if not delta_free.lower - 1e-12 <= real_delta <= delta_free.upper + 1e-12:
            raise AssertionError("realized paired test gain outside sharp binary bounds")
        audit.append(dict(**rule, n_test=len(truth), test_approval=a.mean(),
                          test_baseline_approval=b.mean(), test_n_changed=int((a != b).sum()),
                          realized_test_abr=real_abr, realized_test_gain=real_delta,
                          test_abr_lower=abr.lower, test_abr_upper=abr.upper,
                          test_delta_lower=delta.lower, test_delta_upper=delta.upper,
                          test_binary_abr_lower=abr_free.lower, test_binary_abr_upper=abr_free.upper,
                          test_binary_gain_lower=delta_free.lower, test_binary_gain_upper=delta_free.upper))
    return audit


def plot_bounds(frontier, policies, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    colors = {"taiwan": "#215b80", "prosper": "#9c452d"}
    labels = ["1", "1.25", "1.5", "2", "3", "5", "10", "Free"]
    x = np.arange(len(GAMMAS))
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 4.5), layout="constrained")
    for ds, color in colors.items():
        f = frontier[(frontier.dataset == ds) & (frontier.target == .5)].groupby("gamma")
        low = f.delta_lower.mean().reindex(GAMMAS).to_numpy()
        high = f.delta_upper.mean().reindex(GAMMAS).to_numpy()
        a = axes[0]
        a.fill_between(x, low, high, color=color, alpha=.11)
        a.plot(x, low, color=color, marker="o", label=ds.title())
        a.plot(x, high, color=color, linestyle=":", linewidth=1.1)
        z = policies[(policies.dataset == ds) & (policies.budget == 0.)].groupby("gamma")
        axes[1].plot(x, z.target.mean().reindex(GAMMAS), color=color,
                     marker="o" if ds == "taiwan" else "x", label=ds.title())
    axes[0].set_title("Gain from expanding 30% to 50%")
    axes[0].axhline(0., color="#313b44", linewidth=.8)
    axes[0].set_ylabel("Validation margin gain per applicant")
    axes[0].legend(frameon=False)
    axes[1].set_title("Validation choice with zero downside")
    axes[1].set_ylabel("Mean selected target approval rate")
    axes[1].set_yticks(TARGETS)
    axes[1].legend(frameon=False)
    for a in axes:
        a.yaxis.set_major_formatter(PercentFormatter(1, decimals=1))
        a.set_xticks(x, labels)
        a.set_xlabel("Reject-prior odds multiplier Γ (Free = unrestricted)")
        a.grid(axis="y", alpha=.22)
        a.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Policy sensitivity to missing repayments", fontsize=15, fontweight="bold")
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def run(out, cache):
    out.mkdir(parents=True, exist_ok=True)
    frontier, tipping, policies = [], [], []
    for ds in ("taiwan", "prosper"):
        pop = load_population(ds, cache)
        for fold, split in enumerate(pop.splits, 1):
            (_, _, val, test) = split
            (s_val, p_val), (s_test, p_test) = score_inputs(pop, split, 701 + fold)
            y_val = np.where(pop.accepted[val], pop.y[val], np.nan)
            f, t, choices = design(s_val, y_val, p_val)
            y_test = np.where(pop.accepted[test], pop.y[test], np.nan)
            test_rows = evaluate_choices(choices, s_test, p_test, y_test, pop.y[test])
            for dest, rows in [(frontier, f), (tipping, t), (policies, test_rows)]:
                dest.extend(dict(dataset=ds, fold=fold, **row) for row in rows)
    f, t, p = map(pd.DataFrame, [frontier, tipping, policies])
    summary = p.groupby(["dataset", "gamma", "budget"], as_index=False).agg(
        folds=("fold", "count"), mean_target=("target", "mean"),
        mean_validation_floor=("validation_worst_gain", "mean"),
        mean_test_approval=("test_approval", "mean"), mean_realized_test_gain=("realized_test_gain", "mean"),
        mean_test_binary_gain_lower=("test_binary_gain_lower", "mean"),
        mean_test_binary_gain_upper=("test_binary_gain_upper", "mean"))
    for name, frame in [("frontier", f), ("tipping", t), ("policy", p), ("summary", summary)]:
        frame.to_csv(out / f"bounds_{name}.csv", index=False, float_format="%.10g")
    plot_bounds(f, p, out / "bounds_frontier.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    args = parser.parse_args()
    run(args.out, args.cache)
