"""Convert dated six-month event counts and three-month payment markers to year-one risk."""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class EarlyForecast:
    risk: float
    capture: float
    source: str


def _check_counts(*counts):
    if any(not isfinite(x) or x < 0 or x != int(x) for x in counts):
        raise ValueError("event counts must be finite nonnegative integers")


def _check_probability(value):
    if not 0 <= value <= 1:
        raise ValueError("local risk must lie between zero and one")


def curve_forecast(local, old_e, old_y, bank_e, bank_y, young_e, young_n):
    """Annualize young six-month events with a mature capture fraction, anchoring ten loans to local."""
    _check_probability(local)
    _check_counts(old_e, old_y, bank_e, bank_y, young_e, young_n)
    if old_e > old_y or bank_e > bank_y or young_e > young_n:
        raise ValueError("six-month events must be a subset of exposed loans and annual events")
    if old_y >= 5 and old_e >= 1:
        source, early, annual = "local", old_e, old_y
    elif bank_y >= 5 and bank_e >= 1:
        source, early, annual = "bank", bank_e, bank_y
    else:
        return EarlyForecast(local, float("nan"), "none")
    capture = (early + .5) / (annual + 1)
    if young_n == 0:
        return EarlyForecast(local, capture, source)
    # Equivalent to shrinking the new early rate toward capture * local, then annualizing it.
    risk = (young_e / capture + 10 * local) / (young_n + 10)
    return EarlyForecast(min(1., risk), capture, source)


def payment_forecast(local, old_n, old_y, old_a, old_ya, young_a, young_n):
    """Apply mature risks conditional on the payment marker to its recent prevalence."""
    _check_probability(local)
    _check_counts(old_n, old_y, old_a, old_ya, young_a, young_n)
    if (old_y > old_n or old_a > old_n or old_ya > min(old_a, old_y)
            or old_y - old_ya > old_n - old_a or young_a > young_n):
        raise ValueError("inconsistent payment-marker counts")
    if old_a in (0, old_n) or young_n == 0:
        return local
    marker_prior = (old_a + .5) / (old_n + 1)
    share = (young_a + 10 * marker_prior) / (young_n + 10)
    risk_if_marked = (old_ya + .5) / (old_a + 1)
    risk_if_unmarked = (old_y - old_ya + .5) / (old_n - old_a + 1)
    return share * risk_if_marked + (1 - share) * risk_if_unmarked
