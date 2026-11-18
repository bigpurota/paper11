"""Estimate credibility of a local default rate using only dated cohort counts."""
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class LocalTrust:
    local: float
    pooled: float
    tau2: float
    effective_n: float
    weight: float
    hybrid: float
    support_weight: float
    support_hybrid: float
    hard: float


def trust_forecast(defaults, n, recent_n, other_defaults, other_n):
    """Donor dispersion discounts binomial noise. Rapid expansion discounts local support."""
    d, counts = np.broadcast_arrays(np.asarray(other_defaults, float), np.asarray(other_n, float))
    if (d.ndim != 1 or not np.isfinite([defaults, n, recent_n]).all()
            or not np.isfinite(d).all() or not np.isfinite(counts).all()
            or np.any(d < 0) or np.any(d > counts) or defaults < 0 or defaults > n or recent_n < 0):
        raise ValueError("invalid local or donor cohort counts")
    if counts.sum() == 0:
        raise ValueError("a pooled forecast requires at least one mature donor loan")
    pooled = (d.sum() + .5) / (counts.sum() + 1.)
    usable = counts >= 20
    tau2 = 0.
    if np.count_nonzero(usable) >= 3:
        k = counts[usable]
        q = (d[usable] + .5) / (k + 1.)
        tau2 = max(0., np.var(q, ddof=1) - np.mean(q * (1. - q) / (k + 1.)))
    if n == 0:
        return LocalTrust(pooled, pooled, tau2, 0., 0., pooled, 0., pooled, pooled)
    local = (defaults + .5) / (n + 1.)
    effective_n = n * min(1., n / max(1., recent_n))
    variance = local * (1. - local)
    weight = tau2 / (tau2 + variance / (effective_n + 1.))
    support = tau2 / (tau2 + variance / (n + 1.))
    return LocalTrust(local, pooled, tau2, effective_n, weight, pooled + weight * (local - pooled),
                      support, pooled + support * (local - pooled), local if weight > .5 else pooled)
