"""Out-of-sample ranking and value of a pilot rule at its pre-specified threshold."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def weighted_auc(scores, positive, weights):
    """Probability a positive case outranks a negative, splitting ties equally."""
    _, ties = np.unique(scores, return_inverse=True)
    n_scores = int(ties.max()) + 1
    winners = np.bincount(ties, weights=weights * positive, minlength=n_scores)
    others = np.bincount(ties, weights=weights * ~positive, minlength=n_scores)
    pairs = winners.sum() * others.sum()
    if not pairs:
        return np.nan
    earlier = np.cumsum(others) - .5 * others
    return (winners @ earlier) / pairs


def score_panel(panel, draws=2500, seed=26011):
    """One row per scheduled opportunity; scores and choices must predate outcomes."""
    dates = pd.PeriodIndex(panel.quarter, freq="Q")
    n_quarters = dates.max().ordinal - dates.min().ordinal + 1
    keep = panel.eligible.to_numpy(dtype=bool)
    cells = panel.loc[keep]
    score = cells.score.to_numpy(dtype=float)
    net = cells.net.to_numpy(dtype=float)  # gain relative to refreshed no-pilot for this opportunity
    selected = cells.selected.to_numpy(dtype=bool)
    strict = cells.strict.to_numpy(dtype=bool)
    positive = net > 1e-10
    if not np.isfinite(score).all() or not np.isfinite(net).all():
        raise ValueError("nonfinite values in an eligible episode")
    if np.any(strict & ~positive) or not np.array_equal(selected, score > 1e-12):
        raise ValueError("inconsistent cost-recovery flag or prospective threshold")
    if np.any(panel.selected.to_numpy(dtype=bool) & ~keep):
        raise ValueError("a policy selected an ineligible opportunity")

    groups = (dates.asi8 - dates.min().ordinal)[keep]
    counts = dict(scheduled=len(panel), quarters=n_quarters, eligible=len(cells),
                  selected=int(selected.sum()), profitable=int(positive.sum()),
                  profitable_selected=int((positive & selected).sum()),
                  strict_recoveries=int(strict.sum()), strict_selected=int((strict & selected).sum()))

    def measures(weights):
        def avg(values, mask):
            denominator = weights[mask].sum()
            return np.dot(weights[mask], values[mask]) / denominator if denominator else np.nan
        all_cases = np.ones(len(weights), dtype=bool)
        chosen, skipped = avg(net, selected), avg(net, ~selected)
        return dict(auc_positive=weighted_auc(score, positive, weights) if len(net) else np.nan,
                    auc_strict=weighted_auc(score, strict, weights) if len(net) else np.nan,
                    selected_mean=chosen, skipped_mean=skipped, targeting_difference=chosen-skipped,
                    rule_gain=avg(selected*net, all_cases), pilot_all_gain=avg(net, all_cases),
                    rule_minus_pilot_all=avg(-(1-selected.astype(int))*net, all_cases),
                    predicted_rule_gain=avg(selected*score, all_cases))

    points = measures(np.ones(len(cells)))
    samples = {key: [] for key in points}
    rng = np.random.default_rng(seed)
    # Keep the full time axis, including quarters that contributed no eligible rows.
    if n_quarters >= 4:
        starts = rng.integers(n_quarters, size=(draws, (n_quarters+3)//4))
        indices = ((starts[:, :, None] + np.arange(4)) % n_quarters).reshape(draws, -1)[:, :n_quarters]
        for pick in indices:
            weights = np.bincount(pick, minlength=n_quarters)[groups]
            for key, value in measures(weights).items():
                if np.isfinite(value):
                    samples[key].append(value)
    rows = []
    for key, point in points.items():
        sample = samples[key]
        lower, upper = np.quantile(sample, [.025,.975]) if sample else (np.nan, np.nan)
        rows.append(dict(**counts, metric=key, estimate=point, block4_low=lower, block4_high=upper,
                         estimable_resamples=len(sample), requested_resamples=draws))
    return rows


def public_risk_forecast(panel):
    """Average decision value over earlier public risk updates available at origination.

    Source and update dates have the same frequency within a portfolio. Both
    endpoints of each historical update are model estimates, never pilot returns.
    """
    from scipy.optimize import brentq
    from scipy.special import expit, logit

    q0 = panel.initial.to_numpy(dtype=float)
    q1 = panel.fresh.to_numpy(dtype=float)
    if not ((q0 > 0) & (q0 < 1) & (q1 > 0) & (q1 < 1)).all():
        raise ValueError("smoothed public default estimates must lie strictly between zero and one")
    forecast = panel.score.to_numpy(dtype=float).copy()
    origins = panel.origin.to_numpy()
    disclosures = panel.disclosure.to_numpy()
    drifts = logit(q1) - logit(q0)
    history_dates = np.zeros(len(panel), dtype=int)
    for index, row in enumerate(panel.itertuples()):
        available = (disclosures <= row.origin) & (origins < row.origin)
        history_dates[index] = np.unique(origins[available]).size
        if history_dates[index] < 8:
            continue
        drift = drifts[available]
        # Restoring the martingale mean preserves the pilot's prior default probability.
        shift = brentq(lambda offset: expit(offset + drift).mean() - row.initial,
                       logit(row.initial)-drift.max()-1, logit(row.initial)-drift.min()+1)
        prior = expit(shift + drift)
        probability_if_repaid = row.strength * prior / (row.strength + 1)
        probability_if_default = probability_if_repaid + 1 / (row.strength + 1)
        spread = row.repay - row.default
        gross = ((1-prior)*np.maximum(0, row.repay-spread*probability_if_repaid)
                 + prior*np.maximum(0, row.repay-spread*probability_if_default)
                 - np.maximum(0, row.repay-spread*prior))
        forecast[index] = row.repay - spread*row.initial + row.capacity*np.maximum(0, gross).mean()
    return forecast, history_dates


def transfer_panels(out):
    sba = pd.read_csv(out / "pilot_transfer_episodes.csv")
    for terms, rows in sba.groupby("terms"):
        yield "sba_7a", terms, "scenario", pd.DataFrame(dict(
            quarter=rows.pilot_quarter, origin=pd.PeriodIndex(rows.pilot_quarter, freq="Q").asi8,
            disclosure=pd.PeriodIndex(rows.future_quarter, freq="Q").asi8,
            group=rows.region, eligible=rows.eligible, selected=rows.model_pilots,
            initial=rows.q_initial, fresh=rows.q_fresh, strength=rows.prior_strength,
            repay=rows.interest, default=-.50, capacity=rows.horizon,
            score=rows.predicted_net, net=rows.seed_net, strict=rows.seed_loss_recovered))

    lender = pd.read_csv(out / "lender_pilot_episodes.csv")
    keys = ["country", "customer", "pilot_month", "future_month"]
    late = pd.read_csv(out / "lender_pilot_followup.csv")
    ledger = lender.merge(late[keys + ["net", "cash_covered", "scorable"]], on=keys, how="left",
                          suffixes=("", "_late"), validate="one_to_one")
    if ledger.scorable.isna().any() or not ledger.scorable.all():
        raise ValueError("late receipts missing for a scheduled portfolio")
    for window, target in (("at_least_36m", ledger.loc[ledger.primary]), ("at_least_12m", ledger)):
        panel = pd.DataFrame(dict(
            quarter=target.pilot_quarter, origin=pd.PeriodIndex(target.pilot_month, freq="M").asi8,
            disclosure=pd.PeriodIndex(target.future_month, freq="M").asi8,
            group=target.country.astype(str) + "/" + target.customer.astype(str),
            eligible=target.eligible, selected=target.selected, initial=target.q_initial,
            fresh=target.q_fresh, strength=target.prior_strength, repay=target.repay_margin,
            default=target.default_margin, capacity=target.planned_followups, score=target.predicted_net,
            net=target.forced_net, strict=target.action_changed & (target.forced_pilot < 0) & (target.forced_net > 1e-10)))
        yield "bondora", window, "scenario", panel
        yield "bondora", window, "receipts", panel.assign(net=target.cash_net, strict=target.cash_covered)
        yield "bondora", window, "receipts_2024", panel.assign(net=target.net, strict=target.cash_covered_late)


def run(out):
    records, forecasts = [], []
    for archive, terms, outcome, panel in transfer_panels(out):
        alternative, dates = public_risk_forecast(panel)
        for model in ("fixed_risk", "public_updates"):
            scored = panel if model == "fixed_risk" else panel.assign(
                score=alternative, selected=panel.eligible & (alternative > 1e-12))
            labels = dict(archive=archive, terms=terms, outcome=outcome, forecast=model)
            for row in score_panel(scored):
                records.append({**labels, "warm_eligible": int((scored.eligible & (dates >= 8)).sum()), **row})
            evidence = scored[["origin", "quarter", "group", "score", "eligible", "selected", "net", "strict"]]
            forecasts.append(evidence.assign(**labels, matured_origin_dates=dates))
    pd.DataFrame(records).to_csv(out / "pilot_targeting_summary.csv", index=False, float_format="%.12g")
    pd.concat(forecasts, ignore_index=True).to_csv(out / "pilot_targeting_forecasts.csv", index=False,
                                                  float_format="%.12g")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    run(parser.parse_args().out)
