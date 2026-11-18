"""Value and break-even horizon of one funded pilot, with delayed and decaying information."""
import argparse
from dataclasses import dataclass
from itertools import product
from math import expm1, floor, inf, isfinite, log
from pathlib import Path

import numpy as np
import pandas as pd

from .exploration import Model, solve


TOL = 1e-12
RESETS = (0., .10, .25, .50, 1.)
DISCOUNTS = (1., .97, .90)
DELAYS = (1, 2, 4)
FEES = (0., .01, .03)
FOLLOWUPS = (0, 1, 2, 3, 5, 10, 20, 50)


def terminal_evsi(prior, likelihood, payoff):
    """Exact gross value of a finite signal before a choice among arbitrary actions.

    likelihood[z, s] is P(signal z | state s). payoff[a, s] is utility at
    the terminal decision date. Zero-probability signal branches contribute 0.
    """
    prior = np.asarray(prior, dtype=float)
    likelihood = np.asarray(likelihood, dtype=float)
    payoff = np.asarray(payoff, dtype=float)
    if (prior.ndim != 1 or not prior.size or likelihood.ndim != 2 or payoff.ndim != 2
            or not len(payoff) or not len(likelihood)
            or likelihood.shape[1] != len(prior) or payoff.shape[1] != len(prior)
            or not np.isfinite(prior).all() or not np.isfinite(likelihood).all()
            or not np.isfinite(payoff).all() or np.any(prior < 0) or np.any(likelihood < 0)
            or not np.isclose(prior.sum(), 1., atol=1e-12, rtol=0)
            or not np.allclose(likelihood.sum(axis=0), 1., atol=1e-12, rtol=0)):
        raise ValueError("aligned prior probabilities, signal likelihoods and finite payoffs required")
    joint = likelihood * prior
    with_signal = (joint @ payoff.T).max(axis=1).sum()
    no_signal = (payoff @ prior).max()
    return float(max(0., with_signal - no_signal))


def conditional_terminal_evsi(prior, joint_likelihood, payoff):
    """Incremental value of a private pilot outcome given a common public report.

    joint_likelihood[w, y, s] is P(W=w, Y=y | state s). No conditional
    independence between W and Y is required.
    """
    joint = np.asarray(joint_likelihood, dtype=float)
    if joint.ndim != 3 or 0 in joint.shape:
        raise ValueError("expected a public-report by pilot-outcome by state likelihood array")
    both = terminal_evsi(prior, joint.reshape(-1, joint.shape[-1]), payoff)
    public = terminal_evsi(prior, joint.sum(axis=1), payoff)
    return max(0., both - public)


@dataclass(frozen=True)
class Pilot:
    """First two moments of the latent PD; margins are present values at origination."""
    mean_pd: float
    pd_variance: float
    repaid_margin: float = .10
    default_margin: float = -.45

    def __post_init__(self):
        if not 0 <= self.mean_pd <= 1:
            raise ValueError("mean probability must be in [0,1]")
        if not 0 <= self.pd_variance <= self.mean_pd * (1 - self.mean_pd) + 1e-15:
            raise ValueError("variance is infeasible for a latent probability")
        if (not isfinite(self.repaid_margin) or not isfinite(self.default_margin)
                or self.repaid_margin < self.default_margin):
            raise ValueError("repayment and default margins must be finite and ordered")

    @property
    def prior_margin(self):
        return self.repaid_margin - (self.repaid_margin - self.default_margin) * self.mean_pd

    @property
    def signal_scale(self):
        return (self.repaid_margin - self.default_margin) * self.pd_variance

    @property
    def no_switch_gap(self):
        mu, p = self.prior_margin, self.mean_pd
        return (1 - p) * max(0., -mu) + p * max(0., mu)

    @classmethod
    def from_model(cls, model):
        b = model.prior_good
        pd_mean = b*model.default_good + (1-b)*model.default_bad
        variance = b*(1-b)*(model.default_bad-model.default_good)**2
        return cls(pd_mean, variance, model.repaid_margin, model.default_margin)


def geometric_sum(ratio, first, last):
    """Sum ratio**j for first <= j <= last. None denotes an infinite last date."""
    if (last is not None and last < first) or ratio == 0.:
        return 0.
    if ratio == 1.:
        return inf if last is None else float(last - first + 1)
    factor = 1. if last is None else -expm1((last - first + 1) * log(ratio))
    return ratio**first * factor / (1. - ratio)


def pilot_value(pilot, followups, *, reset=0., discount=1., delay=1, fixed_rule=False):
    """Discounted follow-up EVSI in the one-pilot protocol, excluding today's margin.

    followups counts arrivals after the pilot, including any before its signal
    matures. None requests the infinite-horizon EVSI under a date-specific plan.
    """
    if followups is not None and (not isinstance(followups, (int, np.integer)) or followups < 0):
        raise ValueError("followups must be nonnegative or None")
    if (not 0 <= reset <= 1 or not 0 <= discount <= 1
            or not isinstance(delay, (int, np.integer)) or delay < 1):
        raise ValueError("invalid reset, discount or first usable signal date")
    if fixed_rule and followups is None:
        raise ValueError("specify a finite contractual horizon for a single all-or-none rule")
    c, k, survival = pilot.signal_scale, pilot.no_switch_gap, 1. - reset
    if c <= k or discount == 0 or survival == 0 or (followups is not None and followups < delay):
        return 0.
    if survival == 1.:
        return (c-k) * geometric_sum(discount, delay, followups)
    last = followups
    if k > 0. and not fixed_rule:
        # Including a boundary date with c*s**j == k adds exactly zero.
        final_active = floor((log(k) - log(c)) / log(survival))
        last = final_active if last is None else min(last, final_active)
    discounted_signal = c * geometric_sum(discount * survival, delay, last)
    discounted_gap = k * geometric_sum(discount, delay, last) if k else 0.
    return max(0., discounted_signal - discounted_gap)


def break_even(pilot, *, fee=0., reset=0., discount=1., delay=1):
    """First number of follow-up arrivals at which a pilot strictly beats waiting."""
    if not isfinite(fee) or fee < 0:
        raise ValueError("pilot fee must be finite and nonnegative")
    args = dict(reset=reset, discount=discount, delay=delay)
    limit = pilot_value(pilot, None, **args)
    loss = fee - pilot.prior_margin
    if loss < -TOL:
        return 0
    if limit <= loss + TOL:
        return None
    low, high = 0, delay
    while pilot_value(pilot, high, **args) <= loss + TOL:
        high *= 2
    while high - low > 1:
        mid = (low + high) // 2
        if pilot_value(pilot, mid, **args) > loss + TOL:
            high = mid
        else:
            low = mid
    return high


def frontier():
    pilot = Pilot.from_model(Model())
    for reset, discount, delay, fee in product(RESETS, DISCOUNTS, DELAYS, FEES):
        args = dict(reset=reset, discount=discount, delay=delay)
        first = break_even(pilot, fee=fee, **args)
        evsi = pilot_value(pilot, 10, **args)
        yield dict(**args, fee=fee, prior_margin=pilot.prior_margin, signal_scale=pilot.signal_scale,
                   no_switch_gap=pilot.no_switch_gap, first_followups=first, ever_pays=first is not None,
                   evsi_limit=pilot_value(pilot, None, **args), net_at_ten=pilot.prior_margin-fee+evsi,
                   evsi_at_ten=evsi, fixed_rule_evsi_at_ten=pilot_value(pilot, 10, fixed_rule=True, **args))


def stress_grid():
    grid = product((.02,.05,.10), (.20,.40,.60), (.10,.25,.40,.55,.70,.85,.95),
                   (.05,.10,.20), (.25,.50,.75,1.))
    good, bad, prior, interest, lgd = np.asarray(list(grid)).T
    p = prior*good + (1-prior)*bad
    difference = (1+interest)*lgd
    margin_good, margin_bad = interest-difference*good, interest-difference*bad
    mu = prior*margin_good + (1-prior)*margin_bad
    scale = difference*prior*(1-prior)*(bad-good)**2
    gap = (1-p)*np.maximum(-mu,0.) + p*np.maximum(mu,0.)
    # Independent posterior check evaluates both explicit state mixtures.
    good_if_repay = prior*(1-good)/(1-p)
    good_if_default = prior*good/p
    loss_making = mu < -TOL
    j = np.arange(max(FOLLOWUPS) + 1)[:, None]
    for reset, discount, delay in product(RESETS, DISCOUNTS, DELAYS):
        survival = (1-reset)**j
        weight = discount**j * (j >= delay)
        raw_signal = scale * survival - gap
        evsi = np.cumsum(weight * np.maximum(raw_signal,0.), axis=0)
        all_or_none = np.maximum(np.cumsum(weight * raw_signal, axis=0),0.)
        after_repay = prior + survival * (good_if_repay - prior)
        after_default = prior + survival * (good_if_default - prior)
        payoff_repay = after_repay*margin_good + (1-after_repay)*margin_bad
        payoff_default = after_default*margin_good + (1-after_default)*margin_bad
        direct = np.cumsum(weight*((1-p)*np.maximum(payoff_repay,0.) + p*np.maximum(payoff_default,0.)
                                   - np.maximum(mu,0.)), axis=0)
        for fee, m in product(FEES, FOLLOWUPS):
            discrepancy = float(np.max(np.abs(evsi[m]-direct[m])))
            if discrepancy > 1e-11 or np.any(all_or_none[m] > evsi[m] + TOL):
                raise AssertionError("moment formula disagrees with direct posterior decisions")
            profitable = mu-fee+evsi[m] > TOL
            yield dict(reset=reset, discount=discount, delay=delay, fee=fee, followups=m,
                       scenarios=len(mu), loss_making=int(loss_making.sum()),
                       strictly_worthwhile_loss_making=int((loss_making & profitable).sum()),
                       no_signal_value=int((evsi[m] <= TOL).sum()),
                       mean_evsi=evsi[m].mean(), mean_committed_evsi=all_or_none[m].mean(),
                       max_abs_posterior_error=discrepancy)


def bellman_comparison():
    # Same payoffs, priors, transitions, no fee, first disclosure next period, no discount.
    for good, bad, prior, reset in product((.02,.05,.10), (.20,.40,.60), (.25,.55,.85), (0.,.25,1.)):
        model = Model(prior_good=prior, default_good=good, default_bad=bad, reset=reset)
        pilot = Pilot.from_model(model)
        values = solve(model, 10)
        mu = pilot.prior_margin
        oracle_per_period = prior*max(0.,model.margin[0]) + (1-prior)*max(0., model.margin[1])
        for horizon in (1,2,3,4,6,10):
            m = horizon - 1
            # A declined pilot leaves m decisions using no extra information.
            restricted = m*max(0.,mu) + max(0., mu + pilot_value(pilot,m,reset=reset))
            adaptive = float(values[horizon].value(prior))
            gap = adaptive-restricted
            equality_error = abs(gap) if horizon == 2 else np.nan
            if gap < -TOL or horizon * oracle_per_period < adaptive - TOL or equality_error > TOL:
                raise AssertionError("adaptive policy nesting or two-date Bellman equality failed")
            yield dict(prior_good=prior, default_good=good, default_bad=bad, reset=reset, horizon=horizon,
                       pilot_only=restricted, always_decline=0., current_regime_oracle=horizon*oracle_per_period,
                       fully_adaptive=adaptive, adaptive_minus_pilot_only=gap, one_followup_error=equality_error)


def plot(front, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    model = Pilot.from_model(Model())
    fig, (left,right) = plt.subplots(1,2, figsize=(10.5,3.8), layout="constrained")
    m = np.arange(16)
    for reset, color in [(0.,"#215b80"),(.10,"#a54931"),(.25,"#267963")]:
        ev = [pilot_value(model,int(n),reset=reset) for n in m]
        left.plot(m, 100*(model.prior_margin+np.array(ev)), color=color, label=f"{reset:.0%} redraw", lw=2)
    left.axhline(0., color="#686e73", lw=.9)
    left.set(title="One pilot, future decisions without more labels", xlabel="Follow-up applicants after pilot",
             ylabel="Net gain of issuing pilot (100 principal)")
    left.legend(frameon=False)
    for delay, color in [(1,"#215b80"),(2,"#a54931"),(4,"#267963")]:
        rows = front[(front.reset==0.) & (front.discount==.90) & (front.delay==delay)]
        right.plot(100*rows.fee, rows.first_followups, "-o", color=color, label=f"Signal at date {delay}")
        never = rows[~rows.ever_pays]
        right.scatter(100*never.fee, np.full(len(never), 60.), color=color, marker="x", s=65)
    right.axhline(55, color="#777b7d", lw=.7, linestyle=":")
    right.set_yticks([0,10,20,30,40,50,60], labels=["0","10","20","30","40","50","Never"])
    right.set(title="How many future applicants pay for the pilot?", xlabel="One-off fee (100 principal)",
              ylabel="First profitable number of follow-ups")
    right.legend(frameon=False)
    for ax in (left,right):
        ax.spines[["top","right"]].set_visible(False)
        ax.grid(axis="y", alpha=.2)
    fig.savefig(path, dpi=150, metadata={"Software":"Matplotlib"})
    plt.close(fig)


def run(out):
    out.mkdir(parents=True, exist_ok=True)
    front = pd.DataFrame(frontier())
    front["first_followups"] = front["first_followups"].astype("Int64")
    for name, frame in [("frontier",front), ("stress",pd.DataFrame(stress_grid())),
                        ("bellman",pd.DataFrame(bellman_comparison()))]:
        frame.to_csv(out / f"information_value_{name}.csv", index=False, float_format="%.12g")
    plot(front,out / "information_value_frontier.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",type=Path,default=Path("results"))
    args = parser.parse_args()
    run(args.out)
