"""Precommitted pilot choice and strict-recovery score using origination-date inputs."""
from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq
from scipy.special import expit, logit
from scipy.stats import betabinom


REPAY = .10
DEFAULT = -.45
SPREAD = REPAY - DEFAULT
STRENGTH = 20.
CAPACITY = 25
TOL = 1e-12


@dataclass(frozen=True)
class Forecast:
    eligible: bool
    baseline_selected: bool
    selected: bool
    direct_money: float
    expected_info_money: float
    net_money: float
    baseline_score: float
    strict_probability: float
    exposure_only_net: float
    risk_only_net: float


def public_risks(q, old_risks, updated_risks, old_dates):
    """Only pass historical pairs whose public update is already available."""
    old = np.asarray(old_risks, dtype=float)
    updated = np.asarray(updated_risks, dtype=float)
    dates = np.asarray(old_dates)
    if (old.shape != updated.shape or old.shape != dates.shape or old.ndim != 1
            or not ((old > 0) & (old < 1) & (updated > 0) & (updated < 1)).all()
            or not 0 < q < 1):
        raise ValueError("expected aligned, strictly interior public risk estimates")
    if len(np.unique(dates)) < 8:
        return np.array([q])
    changes = logit(updated) - logit(old)
    center = brentq(lambda offset: expit(offset + changes).mean() - q,
                    logit(q)-changes.max()-1, logit(q)-changes.min()+1)
    return expit(center + changes)


def value_per_unit(u):
    repaid = STRENGTH*u/(STRENGTH+1)
    failed = (STRENGTH*u+1)/(STRENGTH+1)
    informed = (1-u)*np.maximum(0, REPAY-SPREAD*repaid) + u*np.maximum(0, REPAY-SPREAD*failed)
    return np.maximum(0, informed - np.maximum(0, REPAY-SPREAD*u))


def predict(q, principal, counts, volumes, old_risks=(), updated_risks=(), old_dates=()):
    counts = np.asarray(counts, dtype=float)
    volumes = np.asarray(volumes, dtype=float)
    if (counts.shape != (12,) or volumes.shape != (12,) or not np.isfinite(principal)
            or principal <= 0 or not np.isfinite(volumes).all() or not np.isfinite(counts).all()
            or np.any(counts != counts.astype(int)) or np.any((counts < 0) | (counts > CAPACITY))
            or np.any(volumes < 0) or np.any((counts == 0) != (volumes == 0))):
        raise ValueError("need a positive pilot and twelve valid historical portfolios")
    risks = public_risks(q, old_risks, updated_risks, old_dates)
    direct = REPAY-SPREAD*q
    fixed_value = float(value_per_unit(q))
    average_value = float(value_per_unit(risks).mean())
    exposure = float(volumes.mean())
    net = principal*direct + exposure*average_value
    fixed_net = direct + CAPACITY*fixed_value

    # A realized loss on a binary pilot requires default. A decline helps only
    # when the no-signal portfolio would have lent and made a sufficiently large loss.
    before = REPAY-SPREAD*risks > TOL
    after_default = REPAY-SPREAD*(STRENGTH*risks+1)/(STRENGTH+1) > TOL
    switches = risks[before & ~after_default]
    probability = 0.
    if switches.size:
        for n, volume in zip(counts.astype(int), volumes):
            if n == 0:
                continue
            # Equal principal within this historical batch. Test strict profit
            # directly on each count, avoiding rounding at integer break-even.
            k = np.arange(n+1)
            covered = (-DEFAULT*principal + volume*(REPAY-SPREAD*k/n)) < -TOL*principal
            if covered.any():
                tail = betabinom.pmf(k[covered,None], n, STRENGTH*switches+1,
                                     STRENGTH*(1-switches)).sum(axis=0)
                probability += float(switches @ tail)
    probability /= 12*len(risks)
    eligible = direct < -TOL
    return Forecast(eligible, bool(eligible and fixed_net > TOL), bool(eligible and net/principal > TOL),
                    direct*principal, exposure*average_value, net, fixed_net, probability,
                    principal*direct+exposure*fixed_value,
                    principal*(direct+CAPACITY*average_value))
