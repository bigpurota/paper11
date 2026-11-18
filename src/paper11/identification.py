"""Observationally equivalent credit histories and exact minimax cutoff regret."""
import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linprog

from .bounds_experiment import LGD, TARGETS, score_inputs
from .data import load_population
from .empirical import INTEREST, cashflow


@dataclass(frozen=True)
class RegretGame:
    # Row k is a single admissible world maximizing the regret against oracle k
    # simultaneously for all choices. Its diagonal need not be the row maximum.
    worlds: np.ndarray
    margins: np.ndarray
    regret: np.ndarray


@dataclass(frozen=True)
class Minimax:
    weights: np.ndarray
    mixed_regret: float
    pure_action: int
    pure_regret: float


def rounded_prior_counts(observed, prior, bins=10):
    """Hypothetical oracle discloses reject-default counts by fitted prior rank."""
    observed = np.asarray(observed, dtype=float)
    p = np.asarray(prior, dtype=float)
    if observed.ndim != 1 or p.shape != observed.shape or not isinstance(bins, int) or bins < 1:
        raise ValueError("prior and observed must be aligned vectors, with a positive bin count")
    hidden = np.flatnonzero(np.isnan(observed))
    if np.any(~np.isfinite(p[hidden])) or np.any((p[hidden] < 0) | (p[hidden] > 1)):
        raise ValueError("hidden applicants require finite probabilities")
    # Use original cohort order only to break ties at an equal-frequency boundary.
    ordered = hidden[np.argsort(p[hidden], kind="stable")]
    groups = np.full(len(p), -1, dtype=int)
    counts = []
    for g, ids in enumerate(np.array_split(ordered, bins)):
        groups[ids] = g
        counts.append(int(np.floor(p[ids].sum() + .5)))
    return groups, np.asarray(counts, dtype=int)


def adverse_worlds(observed, decisions, quotas=None):
    """Construct sharp oracle witnesses. Quota-constrained policies must be nested."""
    y = np.asarray(observed, dtype=float)
    d = np.asarray(decisions)
    if (y.ndim != 1 or not y.size or not np.isin(y[~np.isnan(y)], [0, 1]).all()
            or d.ndim != 2 or not len(d) or d.shape[1] != len(y)
            or not np.isin(d, [0, 1]).all()):
        raise ValueError("aligned binary decisions and observed 0/1/NaN outcomes required")
    d = d.astype(int)
    missing = np.isnan(y)
    groups = counts = None
    if quotas is not None:
        if np.any(d[:-1] > d[1:]):
            raise ValueError("the common quota-constrained adverse ordering requires nested policies")
        groups, counts = (np.asarray(x) for x in quotas)
        if (groups.shape != y.shape or groups.dtype.kind not in "iu" or counts.ndim != 1
                or counts.dtype.kind not in "iu" or np.any(counts < 0)
                or np.any(groups[missing] < 0) or np.any(groups[missing] >= len(counts))
                or (np.bincount(groups[missing], minlength=len(counts)) < counts).any()):
            raise ValueError("infeasible hidden-default quotas or misaligned integer strata")
    # A strictly interior uniform mixture breaks score-band ties consistently for
    # every pure opponent. See docs/identification.md for the common sort order.
    mean_decision = d.mean(axis=0)
    worlds = []
    for oracle in d:
        priority = mean_decision - oracle
        state = np.where(missing, 0, y).astype(int)
        if quotas is None:
            state[missing & (priority > 0.)] = 1
        else:
            for g, k in enumerate(counts):
                ids = np.flatnonzero(missing & (groups == g))
                order = ids[np.argsort(-priority[ids], kind="stable")]
                state[order[:k]] = 1
        worlds.append(state)
    worlds = np.asarray(worlds)
    # Compute all policy payoffs in the same completed world before differencing.
    margins = cashflow(worlds, 1, LGD) @ d.T / len(y)
    regret = margins.diagonal()[:, None] - margins
    return RegretGame(worlds, margins, regret)


def minimax(regret):
    """Minimize the maximum oracle row, both for a pure cutoff and a lottery."""
    g = np.asarray(regret, dtype=float)
    if g.ndim != 2 or not all(g.shape) or not np.isfinite(g).all():
        raise ValueError("a nonempty finite oracle-by-action regret matrix is required")
    m, n = g.shape
    # Last variable is the upper bound on every oracle's regret.
    lp = linprog(np.r_[np.zeros(n), 1.], A_ub=np.column_stack((g, -np.ones(m))),
                 b_ub=np.zeros(m), A_eq=[np.r_[np.ones(n), 0.]], b_eq=[1.],
                 bounds=[(0., 1.)] * n + [(None, None)], method="highs")
    if not lp.success:
        raise RuntimeError(f"minimax LP failed: {lp.message}")
    w = np.clip(lp.x[:n], 0., 1.)
    w /= w.sum()
    ceiling = g.max(axis=0)
    pure = int(np.flatnonzero(ceiling <= ceiling.min() + 1e-12)[0])
    return Minimax(w, max(0., float((g @ w).max())), pure, max(0., float(ceiling[pure])))


def binary_solution(lower, upper):
    """Expansion lottery for two actions, closed form in the sharp gain bounds."""
    if not np.isfinite([lower, upper]).all() or lower > upper:
        raise ValueError("gain endpoints must be finite and ordered")
    if upper <= 0.:
        return 0., 0.
    if lower >= 0.:
        return 1., 0.
    p = upper / (upper - lower)
    return p, -p * lower


def information_value(observed, decisions, before):
    """Exact ex-ante worst regret after revealing a single adjacent band's total.

    Unrestricted outcomes only. Conditional on the count, all other bands are
    independent feasible binary completions. Equal principal makes identities
    within that band irrelevant to every available cutoff.
    """
    d = np.asarray(decisions, dtype=int)
    n = len(observed)
    changed = np.diff(d, axis=0).astype(bool)
    mid = np.nan_to_num(observed)
    m = changed @ np.isnan(observed).astype(int)
    upper = cashflow(mid, 1, LGD) @ changed.T / n
    c = (1 + INTEREST) * LGD / n
    lower = upper - c * m
    rows = []
    for j, size in enumerate(m):
        worst_after = 0.
        for count in range(size + 1):
            # Under adversary k, make the first k increments good and the rest bad.
            increments = np.where(np.arange(len(m))[None, :] < np.arange(len(d))[:, None],
                                  upper, lower)
            increments[:, j] = upper[j] - c * count
            values = np.column_stack((np.zeros(len(d)), increments.cumsum(axis=1)))
            g = values.diagonal()[:, None] - values
            worst_after = max(worst_after, minimax(g).mixed_regret)
        rows.append(dict(band=j, hidden_in_band=int(size), possible_totals=int(size)+1,
                         before=before, worst_after=worst_after,
                         guaranteed_regret_reduction=max(0., before - worst_after)))
    return rows


def analyze_grid(cutoffs, masks, observed, groups, counts, grid, idx, constraint):
    decisions = masks[idx]
    targets = TARGETS[idx]
    quotas = None if constraint == "unrestricted" else (groups, counts)
    game = adverse_worlds(observed, decisions, quotas)
    solution = minimax(game.regret)
    lower = game.margins[0, -1] - game.margins[0, 0]
    upper = game.margins[-1, -1] - game.margins[-1, 0]
    if grid == "two":
        _, closed_form = binary_solution(lower, upper)
        if not np.isclose(closed_form, solution.mixed_regret, atol=1e-10):
            raise AssertionError("minimax LP disagrees with binary closed form")

    design = dict(grid=grid, constraint=constraint, oracle_audit_only=constraint == "oracle_decile_totals")
    hidden = np.isnan(observed)
    band = decisions[-1] & ~decisions[0]
    worlds = []
    for k, state in enumerate(game.worlds):
        hist = np.bincount(groups[hidden], weights=state[hidden], minlength=len(counts)).astype(int)
        if not np.array_equal(state[~hidden], observed[~hidden]):
            raise AssertionError("constructed witness changed observed repayments")
        if quotas is not None and not np.array_equal(hist, counts):
            raise AssertionError("constructed witness changed a known stratum total")
        worlds.append(dict(
            **design, witness_for=targets[k], n=len(state), n_observed=int((~hidden).sum()),
            observed_defaults=int(state[~hidden].sum()), hidden_defaults=int(state[hidden].sum()),
            hidden_defaults_by_prior_decile=" ".join(map(str, hist)),
            changed_cases=int(band.sum()), changed_hidden=int((band & hidden).sum()),
            changed_defaults=int(state[band].sum()),
            change_30_to_50=game.margins[k, -1] - game.margins[k, 0],
            world_best_target=targets[np.argmax(game.margins[k])],
        ))
    policies = []
    for j, target in enumerate(targets):
        policies.append(dict(
            **design, target=target, cutoff=cutoffs[idx[j]], lottery_weight=solution.weights[j],
            pure_choice=(j == solution.pure_action), worst_for_this_cutoff=game.regret[:, j].max(),
            worst_deterministic=solution.pure_regret, worst_lottery=solution.mixed_regret,
            gain_30_to_50_lower=lower, gain_30_to_50_upper=upper,
        ))
    choice = dict(**design, indices=idx, weights=solution.weights, pure_action=solution.pure_action)
    return choice, worlds, policies


def validation_game(score, observed, prior):
    cutoffs = np.quantile(score, TARGETS, method="inverted_cdf")
    masks = score[None, :] <= cutoffs[:, None]
    groups, counts = rounded_prior_counts(observed, prior)
    worlds, policies, information, choices = [], [], [], []
    for grid, idx in [("two", np.array([0, 4])), ("five", np.arange(len(TARGETS)))]:
        for constraint in ("unrestricted", "prior_decile_totals"):
            choice, witness, rows = analyze_grid(cutoffs, masks, observed, groups, counts,
                                                  grid, idx, constraint)
            choices.append(choice)
            worlds.extend(witness)
            policies.extend(rows)
            if grid == "five" and constraint == "unrestricted":
                information = information_value(observed, masks, rows[0]["worst_lottery"])
    return cutoffs, choices, worlds, policies, information


def retrospective_counts(observed, truth, prior):
    """Disclose only true aggregate hidden counts in the pre-existing prior strata."""
    observed = np.asarray(observed, dtype=float)
    truth = np.asarray(truth)
    hidden = np.isnan(observed)
    if (truth.shape != observed.shape or not np.isin(truth, [0, 1]).all()
            or not np.array_equal(truth[~hidden], observed[~hidden])):
        raise ValueError("oracle outcomes must be binary and agree with the observed record")
    groups, design_counts = rounded_prior_counts(observed, prior)
    true_counts = np.bincount(groups[hidden], weights=truth[hidden], minlength=len(design_counts))
    return groups, true_counts.astype(int)


def decile_certificate(observed, switchers, groups, counts):
    """Sharp switcher-default bounds from each stratum's capacity and known total."""
    hidden = np.isnan(observed)
    known_defaults = int(np.sum(observed[switchers & ~hidden]))
    rows = []
    for group, count in enumerate(counts):
        members = hidden & (groups == group)
        size = int(members.sum())
        switched = int((members & switchers).sum())
        rows.append(dict(prior_decile=group + 1, hidden_cases=size, hidden_switchers=switched,
                         oracle_hidden_defaults=int(count),
                         min_hidden_switcher_defaults=max(0, int(count) - (size - switched)),
                         max_hidden_switcher_defaults=min(switched, int(count)),
                         known_switcher_defaults_fold=known_defaults,
                         total_switchers_fold=int(switchers.sum()), validation_rows_fold=len(observed)))
    return rows


def test_audit(scores, outcomes, cutoffs, choices):
    masks = np.asarray(scores)[None, :] <= cutoffs[:, None]
    value = (cashflow(np.asarray(outcomes), masks, LGD)).mean(axis=1)
    rows = []
    for choice in choices:
        v, w = value[choice["indices"]], choice["weights"]
        rows.append(dict(grid=choice["grid"], constraint=choice["constraint"],
                         test_pure_gain=v[choice["pure_action"]] - v[0],
                         test_mixed_gain=float(w @ v - v[0]),
                         test_mixed_regret=float(v.max() - w @ v),
                         test_pure_regret=v.max()-v[choice["pure_action"]]))
    return rows


def plot(summary, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), layout="constrained")
    for x, name, color in [(0, "taiwan", "#215b80"), (1, "prosper", "#a64f34")]:
        part = summary[(summary.dataset == name) & (summary.grid == "five")]
        free = part[part.constraint == "unrestricted"].iloc[0]
        bins = part[part.constraint == "prior_decile_totals"].iloc[0]
        oracle = summary[(summary.dataset == name) & (summary.constraint == "oracle_decile_totals")].iloc[0]
        for offset, row, marker in [(-.16, free, "o"), (0., bins, "s"), (.16, oracle, "D")]:
            y = x + offset
            axes[0].plot([100*row.gain_30_to_50_lower, 100*row.gain_30_to_50_upper], [y, y],
                         color=color, lw=2.5, marker=marker, ms=5)
        axes[1].plot([0, 1], 100*np.array([free.worst_deterministic, free.worst_lottery]),
                     color=color, marker="o", label=name.title())
        axes[1].plot([0, 1], 100*np.array([bins.worst_deterministic, bins.worst_lottery]),
                     color=color, linestyle=":", marker="s")
    axes[0].axvline(0, color="#55606a", ls="--", lw=1)
    axes[0].set(yticks=[0,1], yticklabels=["Taiwan","Prosper"], ylim=(-.4,1.4),
                xlabel="Margin change from 30% to 50%, pp", title="Two admissible worlds")
    axes[1].set(xticks=[0,1], xticklabels=["One cutoff","Lottery over cutoffs"], xlim=(-.2,1.2),
                ylabel="Worst regret, pp per applicant", title="Five available approval targets")
    axes[1].legend(frameon=False)
    for a in axes:
        a.spines[["top","right"]].set_visible(False)
        a.grid(alpha=.18)
    fig.supxlabel("Circles = unrestricted. Squares = prior-implied decile totals. Diamonds = actual decile totals (retrospective).",
                  fontsize=9)
    fig.savefig(path, dpi=160, metadata={"Software":"Matplotlib"})
    plt.close(fig)


def run(out, cache):
    out.mkdir(parents=True, exist_ok=True)
    all_worlds, all_policies, all_info, audits = [], [], [], []
    deciles = []
    for name in ("taiwan", "prosper"):
        pop = load_population(name, cache)
        for fold, split in enumerate(pop.splits, 1):
            _, _, val, test = split
            (s, p), (s_test, _) = score_inputs(pop, split, 701 + fold)
            observed = np.where(pop.accepted[val], pop.y[val], np.nan)
            cut, choices, worlds, policies, info = validation_game(s, observed, p)
            # The prospective decisions above are already frozen. An external
            # oracle now discloses ten historical totals to a separate two-cutoff game.
            group, counts = retrospective_counts(observed, pop.y[val], p)
            masks = s[None, :] <= cut[:, None]
            choice, oracle_worlds, oracle_policies = analyze_grid(
                cut, masks, observed, group, counts, "two", np.array([0, 4]), "oracle_decile_totals"
            )
            certificate = decile_certificate(observed, masks[-1] & ~masks[0], group, counts)
            known = certificate[0]["known_switcher_defaults_fold"]
            endpoints = [known + sum(row[key] for row in certificate)
                         for key in ("min_hidden_switcher_defaults", "max_hidden_switcher_defaults")]
            if endpoints != sorted(row["changed_defaults"] for row in oracle_worlds):
                raise AssertionError("stratum capacity sums disagree with complete witness worlds")
            deciles.extend(dict(dataset=name, fold=fold, **r) for r in certificate)
            realized_gain = (cashflow(pop.y[val], masks[-1], LGD) - cashflow(pop.y[val], masks[0], LGD)).mean()
            if not (oracle_policies[0]["gain_30_to_50_lower"] - 1e-12 <= realized_gain
                    <= oracle_policies[0]["gain_30_to_50_upper"] + 1e-12):
                raise AssertionError("actual validation outcome outside own exact aggregate bounds")
            choices.append(choice)
            policies.extend(oracle_policies)
            worlds.extend(oracle_worlds)
            held = test_audit(s_test, pop.y[test], cut, choices)
            for row in info:
                j = row.pop("band")
                row.update(from_target=TARGETS[j], to_target=TARGETS[j+1])
            for total, rows in [(all_worlds, worlds), (all_policies, policies),
                                (all_info, info), (audits, held)]:
                total.extend(dict(dataset=name, fold=fold, **r) for r in rows)
    w, p, i, a = map(pd.DataFrame, [all_worlds, all_policies, all_info, audits])
    keys = ["dataset", "fold", "grid", "constraint"]
    once = p.loc[p.pure_choice, keys + ["target","worst_deterministic","worst_lottery",
                "gain_30_to_50_lower","gain_30_to_50_upper"]].rename(columns={"target":"pure_target"})
    by_fold = once.merge(a, on=keys, validate="one_to_one")
    summary = by_fold.drop(columns="fold").groupby(["dataset","grid","constraint"], as_index=False).mean()
    summary["folds"] = by_fold.groupby(["dataset","grid","constraint"]).size().to_numpy()
    summary["oracle_audit_only"] = summary["constraint"] == "oracle_decile_totals"
    for label, df in [("worlds",w),("policies",p.merge(a,on=keys,validate="many_to_one")),
                      ("information",i),("summary",summary),("deciles",pd.DataFrame(deciles))]:
        df.to_csv(out / f"identification_{label}.csv", index=False, float_format="%.10g")
    plot(summary, out / "identification_regret.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    args = parser.parse_args()
    run(args.out, args.cache)
