"""Value of one binary pilot signal for a separately chosen follow-up loan.

The arguments describe the same information date and fixed loan terms.
No latent regime or exchangeability assumption is required.
"""
import math


def joint_default_limits(pilot_pd, next_pd):
    """Sharp range of the probability that both borrowers default."""
    if not all(math.isfinite(p) and 0 <= p <= 1 for p in (pilot_pd, next_pd)):
        raise ValueError("Default probabilities must be in [0, 1].")
    return max(0., pilot_pd + next_pd - 1.), min(pilot_pd, next_pd)


def signal_value(pilot_pd, next_pd, both_default, repay_margin, default_margin):
    """Incremental follow-up value versus its best uninformed lend/decline rule.

    Uses joint (unconditional) branch payoffs to handle even zero-probability
    outcomes. Margins include all expected costs of the follow-up, at the
    follow-up decision date.
    """
    lo, hi = joint_default_limits(pilot_pd, next_pd)
    if not math.isfinite(both_default) or not lo - 1e-14 <= both_default <= hi + 1e-14:
        raise ValueError("Joint default probability is inconsistent with the two marginals.")
    if not all(math.isfinite(x) for x in (repay_margin, default_margin)):
        raise ValueError("Loan margins must be finite.")
    spread = repay_margin - default_margin
    after_default = pilot_pd * repay_margin - spread * both_default
    after_repay = (1 - pilot_pd) * repay_margin - spread * (next_pd - both_default)
    no_signal = max(0., repay_margin - spread * next_pd)
    return max(0., max(0., after_default) + max(0., after_repay) - no_signal)


def maximum_signal_value(pilot_pd, next_pd, repay_margin, default_margin):
    """Highest attainable information value over all compatible binary joint laws."""
    return max(signal_value(pilot_pd, next_pd, t, repay_margin, default_margin)
               for t in joint_default_limits(pilot_pd, next_pd))
