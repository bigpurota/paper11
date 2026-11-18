"""Selective-label feedback simulation for Kozodoi et al. (2024), Appendix C."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit, logit, logsumexp
from scipy.stats import multivariate_normal
from sklearn.linear_model import LogisticRegression

from .methods import BASLConfig, bayesian_metrics, fit_basl, fit_scorecard, integrated_bad_rate, metrics


@dataclass
class Mixture:
    means: np.ndarray
    covs: np.ndarray
    prevalence: float = .70

    @classmethod
    def create(cls, rng):
        means = np.array([[[0., 0.], [1., 1.]], [[2., 1.], [3., 2.]]])
        covs = np.empty((2, 2, 2, 2))
        for pair in np.ndindex(2, 2):
            # A covariance must be symmetric positive definite. Sample its three
            # distinct entries from U(0,1) and reject invalid matrices.
            while True:
                a, b, c = rng.uniform(size=3)
                if a * c > b * b + 1e-5:
                    covs[pair] = [[a, b], [b, c]]
                    break
        return cls(means, covs)

    def sample(self, n, rng):
        bad_count = round(self.prevalence * n)
        y = np.r_[np.zeros(n - bad_count, dtype=int), np.ones(bad_count, dtype=int)]
        rng.shuffle(y)
        component = rng.integers(2, size=n)
        x = rng.normal(size=(n, 4))
        for group, part in np.ndindex(2, 2):
            selected = (y == group) & (component == part)
            x[selected, :2] = rng.multivariate_normal(
                self.means[group, part], self.covs[group, part], selected.sum()
            )
        return x, y

    def exact_pd(self, x):
        # Identical noise-feature densities cancel in Bayes' rule.
        densities = np.stack([
            logsumexp([multivariate_normal.logpdf(x[:, :2], m, s)
                       for m, s in zip(means, covs)], axis=0) - np.log(2)
            for means, covs in zip(self.means, self.covs)
        ])
        return expit(logit(self.prevalence) + densities[1] - densities[0])


def approve(scores, rate, rng):
    """Exact quota, uniformly randomized ties; labels are outside the signature."""
    scores = np.asarray(scores)
    count = round(len(scores) * rate)
    shuffled = rng.permutation(len(scores))
    order = shuffled[np.argsort(scores[shuffled], kind="stable")]
    mask = np.zeros(len(scores), dtype=bool)
    mask[order[:count]] = True
    return mask


class Pool:
    def __init__(self):
        self.x, self.y, self.accepted = [], [], []

    def append(self, sample, model, rng):
        x, y = sample
        # Good and bad populations have first-component means 0 and 2.
        # Define bureau quality as -x1, so high quality means low default PD.
        scores = x[:, 0] if model is None else model.predict_proba(x)[:, 1]
        self.x.append(x)
        self.y.append(y)
        self.accepted.append(approve(scores, .15, rng))

    def arrays(self):
        return np.vstack(self.x), np.concatenate(self.y), np.concatenate(self.accepted)


class ConstantPD:
    def __init__(self, y):
        self.p = (np.sum(y) + 1.) / (len(y) + 2.)

    def predict_proba(self, x):
        return np.tile([1 - self.p, self.p], (len(x), 1))


def scorecard(x, y, seed):
    if len(np.unique(y)) < 2:
        return ConstantPD(y)
    return fit_scorecard(x, y, seed=seed)


def calibrated_prior(model, x, calibration_x, calibration_y):
    if len(np.unique(calibration_y)) < 2:
        return np.full(len(x), ConstantPD(calibration_y).p)

    def predictor(rows):
        pd_score = model.predict_proba(rows)[:, 1]
        return logit(np.clip(pd_score, 1e-6, 1 - 1e-6)).reshape(-1, 1)

    calibration = LogisticRegression(C=1., solver="lbfgs")
    calibration.fit(predictor(calibration_x), calibration_y)
    return calibration.predict_proba(predictor(x))[:, 1]


def one_trial(params):
    seed, last_batch, interval, batch_n, holdout_n, draws = params
    # Separate streams for training, calibration, stopping, evaluation, and
    # population truth. Each application stream follows the same policy history.
    streams = [np.random.default_rng(s) for s in np.random.SeedSequence(seed).spawn(9)]
    design, holdout_rng, *other = streams
    cohort_rngs, tie_rng, control_rng, fit_rng = other[:4], other[4], other[5], other[6]
    population = Mixture.create(design)
    x_hold, y_hold = population.sample(holdout_n, holdout_rng)
    pools = [Pool() for _ in range(4)]
    model = None
    out = []
    for step in range(1, last_batch + 1):
        for pool, rng in zip(pools, cohort_rngs):
            pool.append(population.sample(batch_n, rng), model, tie_rng)
        x, y, accepted = pools[0].arrays()
        fit_seed = int(fit_rng.integers(2**30))
        model = scorecard(x[accepted], y[accepted], fit_seed)
        if step % interval and step != last_batch:
            continue

        cx, cy, ca = pools[1].arrays()
        sx, sy, sa = pools[2].arrays()
        vx, vy, va = pools[3].arrays()
        stop_prior = calibrated_prior(model, sx, cx[ca], cy[ca])
        eval_prior = calibrated_prior(model, vx, cx[ca], cy[ca])
        if len(np.unique(y[accepted])) == 2 and sa.any() and (~sa).any():
            basl = fit_basl(x[accepted], y[accepted], x[~accepted],
                            sx, np.where(sa, sy, np.nan), stop_prior,
                            seed=fit_seed, config=BASLConfig())
            corrected, best_round = basl.model, basl.best_round
            # Both rules follow the same candidates if the first augmented
            # model improves. Otherwise the conservative rule returns round 0.
            history = basl.history
            first_improved = (len(history) > 1 and
                              history[1]["validation_abr"] < history[0]["validation_abr"] - 1e-12)
            cautious = corrected if first_improved else model
            cautious_round = best_round if first_improved else 0
        else:
            corrected, cautious, best_round, cautious_round = model, model, 0, 0

        oracle = scorecard(x, y, fit_seed)
        row = dict(seed=seed, batch=step, n_training=len(y), n_accepted=int(accepted.sum()),
                   population_bad=population.prevalence, accepted_bad=y[accepted].mean(),
                   chosen_basl_round=best_round, conservative_round=cautious_round)
        val_scores = model.predict_proba(vx)[:, 1]
        obs = np.where(va, vy, np.nan)
        hold_scores = model.predict_proba(x_hold)[:, 1]
        statistic_sets = {
            "truth": metrics(y_hold, hold_scores),
            "oracle_model": metrics(y_hold, oracle.predict_proba(x_hold)[:, 1]),
            "basl_model": metrics(y_hold, corrected.predict_proba(x_hold)[:, 1]),
            "conservative_model": metrics(y_hold, cautious.predict_proba(x_hold)[:, 1]),
            "accept_eval": metrics(vy[va], val_scores[va]),
            "bayes_eval": bayesian_metrics(obs, val_scores, eval_prior, seed=fit_seed,
                                           min_draws=draws, max_draws=draws),
        }
        # Diagnostic priors are never fed back into model fitting or stopping.
        # For ABR (a linear functional of labels), posterior expectation is exact.
        q = population.exact_pd(vx)
        random_observed = approve(np.zeros(len(vy)), .15, control_rng)
        shuffled = control_rng.permutation(eval_prior[~va])
        adversarial = eval_prior.copy()
        adversarial[~va] = shuffled
        row["known_prior_abr"] = integrated_bad_rate(np.where(va, vy, q), val_scores)
        row["shuffled_prior_abr"] = integrated_bad_rate(np.where(va, vy, adversarial), val_scores)
        row["random_accept_eval_abr"] = integrated_bad_rate(vy[random_observed], val_scores[random_observed])
        row["eval_population_abr"] = integrated_bad_rate(vy, val_scores)
        for prefix, values in statistic_sets.items():
            for metric in ("auc", "brier", "pauc", "abr"):
                row[prefix + "_" + metric] = values[metric]
        out.append(row)
    return out


# Only point values explicitly printed in §7.1.1 and Tables C.3–C.4 of the
# July 2024 course preprint. Percentage recoveries converted to fractions.
RMSE_PAPER = {"auc": (.2205, .1000), "brier": (.0828, .0566),
              "pauc": (.2803, .1187), "abr": (.2010, .0929)}
TRAIN_PAPER = {"auc": (.0591, .3572), "brier": (.0432, .2929),
               "pauc": (.0535, .2242), "abr": (.0598, .2482)}


def summarize(trials):
    """Interval resamples independent trial seeds and keeps whole trajectories."""
    trials = trials.sort_values(["seed", "batch"])
    if trials.groupby("seed").batch.apply(tuple).nunique() != 1:
        raise ValueError("simulation trials must have the same checkpoints")
    n = trials.seed.nunique()
    records = []

    def emit(panel, metric, statistic, paper, values, scale="mean", denom=None):
        # An accepted-only validation sample can have one class in a tiny run.
        # Keep only independent seeds with defined inputs at all checkpoints.
        by_seed = np.asarray(values).reshape(n, -1).mean(axis=1)
        valid = np.isfinite(by_seed)
        if denom is not None:
            denominator = np.asarray(denom).reshape(n, -1).mean(axis=1)
            valid &= np.isfinite(denominator)
        by_seed = by_seed[valid]
        size = len(by_seed)
        estimate = lo = hi = np.nan
        if size:
            indices = np.random.default_rng(8701).integers(size, size=(2000, size))
            estimate, replicas = by_seed.mean(), by_seed[indices].mean(axis=1)
            if scale == "rmse":
                estimate, replicas = np.sqrt(estimate), np.sqrt(replicas)
            elif denom is not None:
                d = denominator[valid]
                bd = d[indices].mean(axis=1)
                if scale == "ratio":
                    estimate = estimate / d.mean() if d.mean() else np.nan
                    replicas = np.divide(replicas, bd, out=np.full_like(replicas, np.nan), where=bd != 0)
                elif scale == "difference_rmse":
                    estimate = np.sqrt(estimate) - np.sqrt(d.mean())
                    replicas = np.sqrt(replicas) - np.sqrt(bd)
            if size > 1 and np.isfinite(replicas).any():
                lo, hi = np.nanquantile(replicas, [.025, .975])
        records.append(dict(panel=panel, metric=metric, statistic=statistic, paper_value=paper,
                            estimate=estimate, ci_low=lo, ci_high=hi, independent_seeds=size))

    for metric in RMSE_PAPER:
        truth = trials["truth_" + metric]
        for i, method in enumerate(["accept_eval", "bayes_eval"]):
            prediction = trials[method + "_" + metric]
            emit("2d/C.3", metric, method + "_rmse", RMSE_PAPER[metric][i],
                 (prediction - truth) ** 2, "rmse")
            emit("2d/C.3", metric, method + "_signed_bias", np.nan, prediction - truth)
        emit("2d/C.3", metric, "rmse_reduction", RMSE_PAPER[metric][0] - RMSE_PAPER[metric][1],
             (trials["accept_eval_" + metric] - truth)**2, "difference_rmse",
             (trials["bayes_eval_" + metric] - truth)**2)
        direction = 1 if metric in {"auc", "pauc"} else -1
        gap = direction * (trials["oracle_model_" + metric] - truth)
        improvement = direction * (trials["basl_model_" + metric] - truth)
        conservative = direction * (trials["conservative_model_" + metric] - truth)
        emit("sensitivity", metric, "basl_conservative_recovery_fraction", np.nan,
             conservative, "ratio", gap)
        emit("2e/C.4", metric, "oracle_gap", TRAIN_PAPER[metric][0], gap)
        emit("2e/C.4", metric, "basl_improvement", np.nan, improvement)
        emit("2e/C.4", metric, "basl_recovery_fraction", TRAIN_PAPER[metric][1],
             improvement, "ratio", gap)
    for col, reference in [("truth_abr", .2095), ("accept_eval_abr", .0140),
                           ("bayes_eval_abr", np.nan)]:
        emit("2d/text", "abr", col + "_mean", reference, trials[col])
    for col in ["eval_population_abr", "known_prior_abr", "shuffled_prior_abr",
                "random_accept_eval_abr"]:
        emit("control", "abr", col + "_rmse", np.nan, (trials[col] - trials.truth_abr) ** 2,
             "rmse")
    return pd.DataFrame(records)


# Four shared x-grid points read from vector paths in the assigned preprint's
# Figure 2 (page 12). See docs/simulation.md for the calibration and legend.
FIG2_POINTS = {
    "evaluation": {
        "accept_eval_abr": [.02000, .01529, .01616, .01520],
        "truth_abr": [.23555, .23146, .23070, .22708],
        "bayes_eval_abr": [.20645, .17512, .18074, .17428],
    },
    "training": {
        "truth_abr": [.23555, .23147, .23070, .22710],
        "oracle_model_abr": [.15754, .15495, .15353, .15262],
        "basl_model_abr": [.21927, .21431, .21305, .20732],
    },
}


def comparison_figure(trials, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    anchors = pd.DataFrame(
        [dict(panel=panel, method=method, batch=batch, paper_abr=abr)
         for panel, series in FIG2_POINTS.items()
         for method, values in series.items()
         for batch, abr in zip([16, 24, 32, 40], values)]
    )
    anchors.to_csv(out / "simulation_fig2_digitized.csv", index=False)
    ours = trials.groupby("batch").mean(numeric_only=True)
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.6), sharex=True, sharey=True)
    names = {"evaluation": ["Accepted labels", "Holdout truth", "Bayesian estimate"],
             "training": ["Accepts-trained", "Oracle-trained", "BASL"]}
    colors = ["#147753", "#2b56a0", "#c55712"]
    shapes = ["o", "s", "^"]
    for col, (panel, series) in enumerate(FIG2_POINTS.items()):
        for i, (method, values) in enumerate(series.items()):
            # Unconnected markers preserve discrete readings from the figure.
            axes[0, col].plot([16, 24, 32, 40], values, color=colors[i],
                              marker=shapes[i], linestyle="none", label=names[panel][i],
                              fillstyle="none" if i == 2 else "full", markersize=6)
            axes[1, col].plot(ours.index, ours[method], color=colors[i], marker=shapes[i],
                              linewidth=1.6, fillstyle="none" if i == 2 else "full",
                              linestyle="--" if i == 2 else "-", markersize=6)
        axes[0, col].set_title("Evaluation of one scorecard" if col == 0 else "Training different scorecards",
                               fontsize=13, fontweight="bold")
        axes[0, col].legend(loc="lower center" if col == 1 else "center left",
                            fontsize=8, frameon=False)
        axes[1, col].set_xlabel("Acceptance-loop batch")
    axes[0, 0].set_ylabel("Paper, Figure 2\nAverage bad rate")
    axes[1, 0].set_ylabel("Independent implementation\nAverage bad rate")
    max_y = max(.30, ours[list(set(k for vals in FIG2_POINTS.values() for k in vals))].max().max() * 1.07)
    for ax in axes.flat:
        ax.set_ylim(0, max_y)
        ax.set_xticks(sorted(set([16, 24, 32, 40]) | set(ours.index)))
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
        ax.grid(axis="y", alpha=.2)
        ax.spines[["right", "top"]].set_visible(False)
    fig.suptitle("Sampling bias in a dynamic lending policy", fontsize=16, fontweight="bold")
    fig.text(.5, .015, "Paper markers are digitized from the assigned July 2024 preprint. "
             "Each replication point averages independent seeds. ABR integrates approval rates of 20–40%.",
             ha="center", fontsize=8)
    fig.tight_layout(rect=(0, .045, 1, .96))
    fig.savefig(out / "simulation_fig2.png", dpi=170, bbox_inches="tight")
    plt.close(fig)


def run(args):
    if min(args.seeds, args.batches, args.interval, args.workers, args.draws) < 1:
        raise ValueError("counts and interval must be positive")
    if min(args.batch_size, args.holdout) < 100:
        raise ValueError("use at least 100 examples per batch and holdout")
    raw = [(args.first_seed + i, args.batches, args.interval, args.batch_size,
            args.holdout, args.draws) for i in range(args.seeds)]
    if args.workers == 1:
        all_trials = [one_trial(p) for p in raw]
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            all_trials = list(executor.map(one_trial, raw))
    trials = pd.DataFrame([row for trial in all_trials for row in trial])
    args.out.mkdir(exist_ok=True, parents=True)
    trials.to_csv(args.out / "simulation_trajectory.csv", index=False, float_format="%.12g")
    comparison_figure(trials, args.out)
    comparison = summarize(trials)
    comparison.to_csv(args.out / "simulation_comparison.csv", index=False, float_format="%.12g")
    print(comparison.loc[(comparison.metric == "abr") & (comparison.panel != "control"),
                         ["statistic", "paper_value", "estimate", "ci_low", "ci_high"]].to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--first-seed", type=int, default=15011)
    parser.add_argument("--batches", type=int, default=40)
    parser.add_argument("--interval", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--holdout", type=int, default=3000)
    parser.add_argument("--draws", type=int, default=100)
    parser.add_argument("--workers", type=int, default=3)
    run(parser.parse_args())
