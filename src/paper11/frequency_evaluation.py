"""Compare dated frequency forecasts and the bank actions implied by their updates."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .pilot_rule import REPAY, SPREAD, TOL
from .pilot_signal_evaluation import brier

PREDICTORS = {
    "frequency": "q_initial", "refresh_frequency": "q_fresh", "peer_frequency": "pi_disclosure",
    "public": "m_public", "common": "m_blind", "revealed": "m_seen",
    "hgb_issue": "hgb_origin", "hgb_public": "hgb_public", "hgb_common": "hgb_common",
    "hgb_blind": "hgb_blind", "hgb_seen": "hgb_seen",
    "hgb_2022_issue": "hgb_2022_origin", "hgb_2022_common": "hgb_2022_common",
    "hgb_2022_seen": "hgb_2022_seen",
}
COMPARISONS = {
    "frequency_to_public": ("frequency", "public"), "public_to_common": ("public", "common"),
    "frequency_to_common": ("frequency", "common"), "common_to_revealed": ("common", "revealed"),
    "frequency_to_revealed": ("frequency", "revealed"), "raw_peers_to_common": ("peer_frequency", "common"),
    "hgb_common_to_common": ("hgb_common", "common"), "hgb_seen_to_revealed": ("hgb_seen", "revealed"),
    "hgb_2022_seen_to_revealed": ("hgb_2022_seen", "revealed"),
}
ACTION_PAIRS = ("frequency_to_public", "public_to_common", "frequency_to_common", "common_to_revealed",
                "frequency_to_revealed", "raw_peers_to_common", "hgb_common_to_common", "hgb_seen_to_revealed")
KEYS = ["pilot_rank", "feed", "country", "origin_month"]


def endpoint_rates(row):
    low = row.future_known_default_principal / row.future_principal
    high = (row.future_known_default_principal + row.future_unknown_principal) / row.future_principal
    return low, high


def branch_values(row, name):
    if name == "revealed" and pd.isna(row.pilot_default):
        return [row.m_repay, row.m_default]
    return [getattr(row, PREDICTORS[name])]


def brier_bounds(row, left, right):
    """Both forecasts face the same unknown future defaults and the same pilot flag."""
    if not row.future_count:
        return np.nan, np.nan
    outcomes = endpoint_rates(row)
    baseline = branch_values(row, left)
    updated = branch_values(row, right)
    # Only the anchored reveal is branched; all bounded comparators are common forecasts.
    scores = [brier(z, p) - brier(z, q) for p in baseline for q in updated for z in outcomes]
    if not np.isfinite(scores).all():
        return np.nan, np.nan
    return min(scores), max(scores)


def sum_known(values):
    return values.sum() if values.notna().all() else np.nan


def summaries(data):
    yield "all", "all", data
    for column in ("country", "origin_month"):
        for key, group in data.groupby(column, sort=True):
            yield column, key, group
    for month in sorted(data.origin_month.unique()):
        yield "omit_month", month, data.loc[data.origin_month.ne(month)]


def forecast_summary(data):
    books = data.loc[data.future_count.gt(0)]
    complete = books.loc[books.future_unknown_principal.eq(0) & books.pilot_default.notna()]
    rate = complete.future_known_default_principal / complete.future_principal
    losses = {key: brier(rate, complete[col]) for key, col in PREDICTORS.items()}
    for name, loss in losses.items():
        yield dict(metric="brier_"+name, books=len(books), observed=loss.count(), mean=loss.mean(),
                   full_lower=np.nan, full_upper=np.nan)
    for name, (left, right) in COMPARISONS.items():
        difference = losses[left] - losses[right]
        bounds = np.array([brier_bounds(row, left, right) for row in books.itertuples()], dtype=float).reshape(-1, 2)
        lo, hi = bounds.mean(axis=0) if len(bounds) else (np.nan, np.nan)
        yield dict(metric="gain_"+name, books=len(books), observed=difference.count(), mean=difference.mean(),
                   full_lower=lo, full_upper=hi)


def action(p):
    return np.nan if pd.isna(p) else int(REPAY - SPREAD*p > TOL)


def action_rows(data):
    for row in data.itertuples():
        keys = {key: getattr(row, key) for key in KEYS}
        for name in ACTION_PAIRS:
            left, right = COMPARISONS[name]
            a = [action(p) for p in branch_values(row, left)]
            b = [action(p) for p in branch_values(row, right)]
            possible = [v-u for u in a for v in b] if row.future_count else [0]
            direction = possible[0] if all(x == possible[0] for x in possible) else np.nan
            if row.future_count:
                zlo, zhi = endpoint_rates(row)
                payoffs = [row.future_principal * (REPAY - SPREAD*z) for z in (zlo, zhi)]
            else:
                payoffs = [0.]
            scenario = [d*f if d != 0 else 0. for d in possible for f in payoffs]
            cash = [d*row.future_cash if d != 0 else 0. for d in possible]
            yield {**keys, "comparison": name, "future_count": row.future_count, "direction": direction,
                   "cash": cash[0] if all(x == cash[0] for x in cash) else np.nan,
                   "scenario_lower": np.min(scenario), "scenario_upper": np.max(scenario)}


def action_summary(ledger):
    for name, rows in ledger.groupby("comparison", sort=False):
        yield dict(comparison=name, scheduled=len(rows), nonempty=rows.future_count.gt(0).sum(),
                   known_actions=rows.direction.count(), lend_to_skip=rows.direction.lt(0).sum(),
                   skip_to_lend=rows.direction.gt(0).sum(), cash_known=rows.cash.count(),
                   total_cash=sum_known(rows.cash), scenario_lower=sum_known(rows.scenario_lower),
                   scenario_upper=sum_known(rows.scenario_upper))


def policy_summary(data, private):
    """Compare the two issue selectors under common downstream anchored actions."""
    eligible = data.loc[data.structural_eligible].set_index(KEYS)
    downstream = private.set_index(KEYS).loc[eligible.index]
    for policy, weight in (("skip", pd.Series(0, index=eligible.index)),
                           ("force", pd.Series(1, index=eligible.index)),
                           ("anchor", eligible.ml_selected.astype("Int64")),
                           ("legacy", eligible.structural_selected.astype("Int64")),
                           ("anchor_minus_legacy", eligible.ml_selected.astype("Int64")
                            - eligible.structural_selected.astype("Int64"))):
        def weighted(series):
            return (weight * series).where(weight.ne(0), 0.)
        pilot = weighted(eligible.pilot_cash)
        book = weighted(downstream.cash)
        total = pilot + book
        # For an unmeasured pilot and an issued loan, evaluate the same flag in
        # its own payoff and the continuation action before taking either endpoint.
        lower, upper = [], []
        for idx, row in eligible.iterrows():
            w = weight.loc[idx]
            if pd.isna(w):
                lower.append(np.nan)
                upper.append(np.nan)
                continue
            if w == 0:
                lower.append(0.)
                upper.append(0.)
                continue
            possible = []
            for y in ([0, 1] if pd.isna(row.pilot_default) else [row.pilot_default]):
                seen = row.m_default if y else row.m_repay
                delta = action(seen) - action(row.m_blind) if row.future_count else 0
                book_margins = ([row.future_principal*(REPAY - SPREAD*z) for z in endpoint_rates(row)]
                                if row.future_count else [0.])
                direct = row.pilot_principal*(REPAY - SPREAD*y)
                possible.extend(w*(direct + delta*v) for v in book_margins)
            lower.append(min(possible))
            upper.append(max(possible))
        yield dict(policy=policy, eligible=len(eligible), issue_more=weight.gt(0).sum(),
                   issue_fewer=weight.lt(0).sum(), known_cash=total.count(), direct_cash=sum_known(pilot),
                   future_cash=sum_known(book), net_cash=sum_known(total),
                   recovered=int(((weight.eq(1)) & eligible.pilot_cash.lt(0) & total.gt(0)
                                  & downstream.direction.ne(0)).sum()) if policy != "anchor_minus_legacy" else np.nan,
                   scenario_lower=np.sum(lower), scenario_upper=np.sum(upper))


def run(out):
    data = pd.read_csv(out / "frequency_model_episodes.csv")
    if data.duplicated(KEYS).any() or not data.origin_month.between("2024-06", "2024-09").all():
        raise ValueError("unexpected test date or repeated candidate and information set")
    ledger = pd.DataFrame(action_rows(data))
    forecasts, actions, policies = [], [], []
    for (rank, feed), part in data.groupby(["pilot_rank", "feed"], sort=True):
        local = ledger.loc[ledger.pilot_rank.eq(rank) & ledger.feed.eq(feed)]
        for scope, group, rows in summaries(part):
            key = dict(pilot_rank=rank, feed=feed, scope=scope, group=group)
            selected = local.merge(rows[KEYS], on=KEYS, validate="many_to_one")
            forecasts.extend({**key, **r} for r in forecast_summary(rows))
            actions.extend({**key, **r} for r in action_summary(selected))
            private = selected.loc[selected.comparison.eq("common_to_revealed")]
            policies.extend({**key, **r} for r in policy_summary(rows, private))
    for name, frame in [("evaluation", forecasts), ("actions", ledger), ("action_summary", actions),
                        ("policy", policies)]:
        pd.DataFrame(frame).to_csv(out / f"frequency_{name}.csv", index=False, float_format="%.12g")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    run(parser.parse_args().out)
