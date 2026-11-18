"""Sharp bounds for score cutoffs evaluated with partially observed binary labels."""
from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq
from scipy.special import expit, logit


@dataclass(frozen=True)
class Interval:
    lower: float
    upper: float


def outcome_limits(observed, prior, gamma):
    """Adversarial reject PDs at finite gamma; any binary completion at infinity.

    Finite gamma requires interior priors for missing cases so their odds exist.
    Observed repayment labels are held fixed in both regimes.
    """
    y = np.asarray(observed, dtype=float)
    if y.ndim != 1 or not y.size or not np.isin(y[~np.isnan(y)], [0., 1.]).all():
        raise ValueError("observed must be a nonempty vector of 0, 1 or NaN")
    if np.isnan(gamma) or gamma < 1:
        raise ValueError("gamma must be at least one")
    missing = np.isnan(y)
    low, high = y.copy(), y.copy()
    if not missing.any():
        return low, high
    if np.isposinf(gamma):
        low[missing], high[missing] = 0., 1.
    else:
        p = np.asarray(prior, dtype=float)
        if p.shape != y.shape:
            raise ValueError("finite gamma requires a prior vector aligned to outcomes")
        p = p[missing]
        if not np.all((p > 0) & (p < 1)):
            raise ValueError("finite gamma requires an interior prior PD for each missing outcome")
        logits = logit(p)
        low[missing] = expit(logits - np.log(gamma))
        high[missing] = expit(logits + np.log(gamma))
    return low, high


def _approved(mask, shape):
    mask = np.asarray(mask)
    if mask.shape != shape or not np.isin(mask, [0, 1]).all():
        raise ValueError("policy must contain an aligned binary approval decision per row")
    return mask.astype(bool)


def _linear_bounds(coef, low, high, constant=0.):
    # The extremizing assignment reverses for negative coefficients.
    return Interval(float(constant + np.sum(coef * np.where(coef >= 0., low, high))),
                    float(constant + np.sum(coef * np.where(coef >= 0., high, low))))


def policy_bounds(observed, prior, gamma, candidate, baseline, *, interest=.10, lgd=.50):
    """Bounds for ABR, margin per applicant and paired change in that margin.

    For gamma=infinity the endpoints are attained by binary completions of this
    finite cohort. For finite gamma the endpoints concern the mean over unseen
    outcomes, conditional on the observed labels, features and given PD box.
    """
    low, high = outcome_limits(observed, prior, gamma)
    a = _approved(candidate, low.shape)
    b = _approved(baseline, low.shape)
    if not np.isfinite(interest) or interest < 0 or not np.isfinite(lgd) or not 0 <= lgd <= 1:
        raise ValueError("unit-principal cash flow requires interest >= 0 and LGD within [0,1]")
    changed = a.astype(float) - b
    loss = (1. + interest) * lgd
    abr = (Interval(float(low[a].mean()), float(high[a].mean()))
           if a.any() else Interval(np.nan, np.nan))
    value = _linear_bounds(-loss * a / len(a), low, high, interest * a.mean())
    delta = _linear_bounds(-loss * changed / len(a), low, high, interest * changed.mean())
    return abr, value, delta


def tipping_gamma(observed, prior, candidate, baseline, *, budget=0., interest=.1, lgd=.5):
    """Largest odds ratio for which worst paired margin change is at least -budget.

    Returns NaN if the policy fails already at the prior; infinity if the
    assumption-free bound suffices (including identical decisions).
    """
    if not np.isfinite(budget) or budget < 0:
        raise ValueError("downside budget must be finite and nonnegative")

    def slack(gamma):
        (_, _, delta) = policy_bounds(observed, prior, gamma, candidate, baseline,
                                      interest=interest, lgd=lgd)
        return delta.lower + budget

    at_prior = slack(1.)
    if at_prior < -1e-12:
        return np.nan
    if slack(np.inf) >= -1e-12:
        return np.inf
    if at_prior <= 1e-12:
        return 1.
    def objective(log_gamma):
        return slack(np.exp(log_gamma))
    hi = 1.
    while objective(hi) > 0:
        hi = min(hi * 2, np.log(np.finfo(float).max))
        if hi == np.log(np.finfo(float).max) and objective(hi) > 0:
            return np.inf  # mathematical radius exceeds representable float
    return float(np.exp(brentq(objective, 0., hi)))


def select_expansion(targets, expected_gain, worst_gain, budget):
    """Choose on validation only; targets must include the unchanged baseline."""
    targets = np.asarray(targets, dtype=float)
    expected = np.asarray(expected_gain, dtype=float)
    worst = np.asarray(worst_gain, dtype=float)
    if (targets.ndim != 1 or not len(targets) or targets.shape != expected.shape
            or targets.shape != worst.shape or not np.isfinite([targets, expected, worst]).all()
            or not np.isfinite(budget) or budget < 0 or np.any(np.diff(targets) <= 0)):
        raise ValueError("invalid policy grid or downside budget")
    if abs(expected[0]) > 1e-12 or abs(worst[0]) > 1e-12:
        raise ValueError("first policy must be the zero-change baseline")
    feasible = np.flatnonzero(worst >= -budget - 1e-12)
    best = expected[feasible].max()
    return int(feasible[np.flatnonzero(expected[feasible] >= best - 1e-12)[0]])
