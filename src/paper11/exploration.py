"""Exact finite-horizon lending decisions with an unobserved, persistent risk regime."""
import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


RESET_PROBABILITIES = (0., .10, .25, .50, 1.)
MAX_HORIZON = 16


@dataclass(frozen=True)
class Model:
    prior_good: float = .55
    default_good: float = .05
    default_bad: float = .40
    repaid_margin: float = .10
    default_margin: float = -.45
    reset: float = 0.

    def __post_init__(self):
        if not 0 <= self.prior_good <= 1 or not 0 <= self.reset <= 1:
            raise ValueError("prior and reset probability must be in [0,1]")
        if not 0 <= self.default_good <= self.default_bad <= 1:
            raise ValueError("default probabilities must satisfy 0 <= good <= bad <= 1")
        if not np.isfinite([self.repaid_margin, self.default_margin]).all():
            raise ValueError("both loan margins must be finite")

    @property
    def default(self):
        return np.array([self.default_good, self.default_bad])

    @property
    def margin(self):
        return (1 - self.default) * self.repaid_margin + self.default * self.default_margin

    @property
    def transition(self):
        redraw = np.broadcast_to([self.prior_good, 1 - self.prior_good], (2, 2))
        return (1 - self.reset) * np.eye(2) + self.reset * redraw

    def predict(self, belief):
        return (1 - self.reset) * belief + self.reset * self.prior_good


@dataclass(frozen=True)
class Envelope:
    """At a given belief, pick the active linear reward of a feasible policy tree."""
    starts: np.ndarray
    payoffs: np.ndarray  # columns conditional on current regime G and B

    def plans(self, belief):
        index = np.searchsorted(self.starts[1:], belief, side="right")
        return self.payoffs[index]

    def value(self, belief):
        plans = self.plans(belief)
        return belief * plans[..., 0] + (1 - belief) * plans[..., 1]


def upper_envelope(payoffs):
    """Upper hull of lines b*good+(1-b)*bad on the continuous interval [0,1]."""
    lines = np.asarray(payoffs, dtype=float)
    slopes = lines[:, 0] - lines[:, 1]
    order = np.lexsort((-lines[:, 1], slopes))
    active, starts = [], []
    for j in order:
        # For an identical slope the larger intercept was visited first.
        if active and slopes[active[-1]] == slopes[j]:
            continue
        start = -np.inf
        while active:
            old = active[-1]
            start = (lines[old, 1] - lines[j, 1]) / (slopes[j] - slopes[old])
            if start > starts[-1]:
                break
            active.pop()
            starts.pop()
        active.append(j)
        starts.append(start if len(active) > 1 else -np.inf)
    first = np.searchsorted(starts, 0., side="right") - 1
    end = np.searchsorted(starts, 1., side="left")
    return Envelope(np.r_[0., starts[first + 1:end]], lines[active[first:end]])


def posterior(belief, likelihood):
    """Probability of an observation and the posterior before a possible reset."""
    p = belief * likelihood[0] + (1 - belief) * likelihood[1]
    good = np.divide(belief * likelihood[0], p, out=np.zeros_like(p, dtype=float), where=p > 0)
    return p, good  # the posterior for an impossible branch is never used


def inverse_breaks(starts, likelihood, model):
    """Current beliefs at which the post-observation next belief crosses a kink."""
    if model.reset == 1 or np.any(likelihood == 0):
        return []
    updated = (starts[1:] - model.reset * model.prior_good) / (1 - model.reset)
    updated = updated[(updated > 0) & (updated < 1)]
    return updated * likelihood[1] / ((1 - updated) * likelihood[0] + updated * likelihood[1])


def backup(previous, model):
    # A funded observation selects one continuation tree per possible repayment.
    # These choices change only at the inverse breakpoints. A midpoint picks each
    # active tree; its payoff line is valid across the whole interval.
    likelihoods = [model.default, 1 - model.default]
    boundaries = np.unique(np.concatenate(([0., 1.], *[
        inverse_breaks(previous.starts, likelihood, model) for likelihood in likelihoods
    ])))
    midpoints = (boundaries[:-1] + boundaries[1:]) / 2
    fund = np.tile(model.margin, (len(midpoints), 1))
    transposed = model.transition.T
    for likelihood in likelihoods:
        _, post = posterior(midpoints, likelihood)
        fund += likelihood * (previous.plans(model.predict(post)) @ transposed)
    # Waiting produces no repayment signal; stopping forever is always available.
    wait = previous.payoffs @ transposed
    return upper_envelope(np.vstack((fund, wait, [0., 0.])))


def solve(model, horizon):
    if not isinstance(horizon, (int, np.integer)) or horizon < 0:
        raise ValueError("horizon must be a nonnegative integer")
    values = [Envelope(np.array([0.]), np.array([[0., 0.]]))]
    for _ in range(horizon):
        values.append(backup(values[-1], model))
    return values


def choices(model, previous, belief):
    """Expected present margin and continuation values before observing this loan."""
    immediate = float(np.dot([belief, 1-belief], model.margin))
    wait = float(previous.value(model.predict(belief)))
    continuation = 0.
    for likelihood in (model.default, 1-model.default):
        probability, post = posterior(belief, likelihood)
        continuation += probability * previous.value(model.predict(post))
    fund = float(immediate + continuation)
    best = max(0., wait, fund)
    # If every policy has zero value we can stop permanently. Prefer waiting at
    # a positive tie, so an initial loan requires a strict improvement.
    action = "stop" if best <= 1e-12 else ("fund" if fund > wait + 1e-12 else "wait")
    return dict(first_action=action, immediate_margin=immediate, fund_value=fund,
                wait_value=wait, stop_value=0., adaptive_value=best,
                first_signal_value=float(continuation - wait))


def run(out):
    out.mkdir(parents=True, exist_ok=True)
    rows, branches = [], []
    for reset in RESET_PROBABILITIES:
        model = Model(reset=reset)
        values = solve(model, MAX_HORIZON)
        b = model.prior_good  # stationary under the reset law
        oracle_period = b * max(0., model.margin[0]) + (1 - b) * max(0., model.margin[1])
        for h in range(1, MAX_HORIZON + 1):
            prefix = dict(reset=reset, horizon=h)
            result = choices(model, values[h-1], b)
            if not np.isclose(result["adaptive_value"], values[h].value(b), atol=1e-11, rtol=0):
                raise AssertionError("envelope and observable action values disagree")
            fund_all = h * result["immediate_margin"]
            fixed = max(0., fund_all)
            rows.append(dict(**prefix, prior_good=b, default_good=model.default_good,
                default_bad=model.default_bad, repaid_margin=model.repaid_margin,
                default_margin=model.default_margin, **result, always_fund=fund_all,
                best_fixed=fixed, adaptive_minus_fixed=result["adaptive_value"]-fixed,
                current_regime_oracle=h*oracle_period, oracle_minus_adaptive=h*oracle_period-result["adaptive_value"]))
            for label, likelihood in [("default", model.default), ("repay", 1-model.default)]:
                probability, post = posterior(b, likelihood)
                next_b = model.predict(post)
                second = choices(model, values[h-2], next_b)["first_action"] if h > 1 else "end"
                branches.append(dict(**prefix, first_action_optimal=result["first_action"],
                    if_first_funded_outcome=label, outcome_probability=float(probability),
                    posterior_good_current=float(post), next_belief_good=float(next_b),
                    next_action=second, next_value=float(values[h-1].value(next_b))))
    results = pd.DataFrame(rows)
    results.to_csv(out / "exploration_values.csv", index=False, float_format="%.12g")
    pd.DataFrame(branches).to_csv(out / "exploration_branches.csv", index=False, float_format="%.12g")
    plot(results, out / "exploration_value.png")


def plot(rows, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (ax, loss) = plt.subplots(1, 2, figsize=(10.8, 4.2), layout="constrained")
    for amount, color in [(0., "#20567d"), (.10, "#a44931"), (.25, "#267963"), (1., "#6c7175")]:
        sub = rows[rows.reset == amount]
        ax.plot(sub.horizon, 100*sub.adaptive_minus_fixed, color=color, lw=2,
                label=f"{amount:.0%} redraw", ls="--" if amount == 1 else "-")
    ax.set(title="Learning across future applicants", xlabel="Number of applicants remaining",
           ylabel="Total extra margin (100 principal per loan)")
    ax.legend(frameon=False)
    sample = rows[(rows.reset == 0) & (rows.horizon <= 5)]
    loss.axhline(0, color="#738086", lw=.8)
    loss.plot(sample.horizon, 100*sample.immediate_margin, ls=":", color="#a44931", label="First loan alone")
    loss.plot(sample.horizon, 100*sample.first_signal_value, color="#267963", label="Information for later loans")
    loss.plot(sample.horizon, 100*(sample.fund_value-sample.wait_value), color="#20567d",
              marker="o", lw=2, label="Fund now minus wait")
    loss.set(title="Why the first loan changes at horizon 3", xlabel="Applicants remaining, persistent regime",
             ylabel="Expected value (100 principal per loan)", xticks=sample.horizon)
    loss.legend(frameon=False, fontsize=9)
    for a in (ax, loss):
        a.spines[["top", "right"]].set_visible(False)
        a.grid(axis="y", alpha=.2)
    fig.savefig(path, dpi=155, metadata={"Software":"Matplotlib"})
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    args = parser.parse_args()
    run(args.out)
