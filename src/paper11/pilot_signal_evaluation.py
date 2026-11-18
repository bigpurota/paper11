"""Paired evaluation of an unseen repayment signal on the locked Bondora period."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd


WINDOWS = {"full": ("2022-10", "2024-05"), "later": ("2023-11", "2024-05")}


def brier(rate, prediction):
    """Mean individual Brier loss for a portfolio with default exposure share rate."""
    return rate * (1 - prediction)**2 + (1 - rate) * prediction**2


def log_loss_bits(rate, prediction):
    p = prediction.clip(1e-12, 1 - 1e-12)
    return -rate * np.log2(p) - (1 - rate) * np.log2(1 - p)


def forecast_contrasts(data):
    actual = data.future_default_principal / data.future_principal
    actual = actual.where(data.future_count.gt(0) & data.pilot_default.notna())
    scores = {name: brier(actual, data[column]) for name, column in {
        "initial": "q_initial", "origin": "m_origin", "public": "m_public",
        "peers": "m_peers", "common_fit": "m_independent_common",
        "blind": "m_blind", "seen": "m_seen"}.items()}
    randomized = ((1 - data.pi_disclosure) * brier(actual, data.m_repay)
                  + data.pi_disclosure * brier(actual, data.m_default))
    result = {f"brier_{name}": value for name, value in scores.items()}
    result.update(brier_contract_and_model=scores["initial"] - scores["origin"],
                  brier_public_refresh=scores["origin"] - scores["public"],
                  brier_peer_feed=scores["public"] - scores["peers"],
                  brier_private=scores["blind"] - scores["seen"],
                  brier_private_refit=scores["common_fit"] - scores["seen"],
                  brier_randomized=randomized, brier_real_vs_random=randomized - scores["seen"],
                  private_log_gain_bits=log_loss_bits(actual, data.m_blind) - log_loss_bits(actual, data.m_seen))
    return pd.DataFrame(result, index=data.index).loc[data.future_count.gt(0)]


def policy_contrasts(data):
    data = data.loc[data.structural_eligible].copy()
    blind = data.blind_lend.astype(float)
    seen = data.seen_lend.astype(float).where(data.pilot_default.notna())
    delta = (seen - blind).mask(data.future_count.eq(0), 0.)
    switched = delta.ne(0).astype("boolean").mask(delta.isna())
    result = pd.DataFrame(index=data.index)
    new = data.ml_selected.astype("boolean")
    old = data.structural_selected.astype("boolean")

    def if_selected(value, selected):
        return value.where(selected.fillna(False), 0.).where(selected.notna())
    for basis in ["cash", "scenario"]:
        pilot = data["pilot_" + basis]
        followup = (delta * data["future_" + basis]).mask(delta.eq(0), 0.)
        total = pilot + followup
        result["forced_" + basis] = total
        result["new_direct_" + basis] = if_selected(pilot, new)
        result["new_followup_" + basis] = if_selected(followup, new)
        result["new_" + basis] = if_selected(total, new)
        result["old_" + basis] = if_selected(total, old)
        choice_delta = new.astype("Int64") - old.astype("Int64")
        result["new_minus_old_" + basis] = if_selected(total * choice_delta, choice_delta.ne(0))
        covered = switched & pilot.astype("Float64").lt(-1e-12) & total.astype("Float64").gt(1e-12)
        result["strict_forced_" + basis] = covered.astype("Float64")
        result["strict_new_" + basis] = if_selected(covered.astype("Float64"), new)
    result["switch_forced"] = switched.astype("Float64")
    result["switch_new"] = if_selected(switched.astype("Float64"), new)
    return result


def block_counts(start, stop):
    """Sample contiguous calendar quarters, including those with no eligible row."""
    grid = pd.period_range(pd.Period(start, "M").asfreq("Q"), pd.Period(stop, "M").asfreq("Q"), freq="Q")
    n = len(grid)
    if n <= 4:
        return grid, None
    rng = np.random.default_rng(26011)
    starts = rng.integers(n, size=(2500, (n + 3) // 4))
    drawn = ((starts[:, :, None] + np.arange(4)) % n).reshape(2500, -1)[:, :n]
    counts = np.zeros((len(drawn), n), dtype=int)
    np.add.at(counts, (np.arange(len(drawn))[:, None], drawn), 1)
    return grid, counts


def estimates(frame, origin, window, with_intervals):
    grid, counts = block_counts(*window)
    quarter = pd.PeriodIndex(origin.loc[frame.index], freq="M").asfreq("Q")
    for name, column in frame.items():
        values = column.to_numpy(dtype=float, na_value=np.nan)
        observed = np.isfinite(values)
        n = int(observed.sum())
        lo = hi = np.nan
        draws = 0
        if with_intervals and n and counts is not None:
            offsets = quarter[observed].asi8 - grid[0].ordinal
            mass = counts @ np.bincount(offsets, minlength=len(grid))
            sums = counts @ np.bincount(offsets, weights=values[observed], minlength=len(grid))
            ok = mass > 0
            lo, hi = np.quantile(sums[ok] / mass[ok], [.025, .975])
            draws = int(ok.sum())
        yield dict(metric=name, population=len(frame), observed=n,
                   mean=values[observed].mean() if n else np.nan,
                   low=lo, high=hi, estimable_draws=draws)


def summarize(rows):
    estimates_rows, coverage = [], []
    for feed, panel in rows.groupby("feed", sort=True):
        for subset, window in WINDOWS.items():
            sample = panel.loc[panel.origin_month.between(*window)]
            groups = [("ALL", sample)]
            if subset == "full":
                groups.extend(sample.groupby("country", sort=True))
            for country, data in groups:
                key = dict(feed=feed, subset=subset, country=country)
                forecast = forecast_contrasts(data)
                policy = policy_contrasts(data)
                for frame in (forecast, policy):
                    for metric in estimates(frame, data.origin_month, window, country == "ALL"):
                        estimates_rows.append({**key, **metric})
                # No eligible cases is a known zero; unobserved decisions stay missing.
                min_known = int(not policy.empty)
                coverage.append({**key, "scheduled": len(data), "months": data.origin_month.nunique(),
                                 "nonempty": len(forecast), "scored": forecast.brier_private.count(),
                                 "eligible": len(policy), "new_selected": data.loc[data.structural_eligible, "ml_selected"].sum(min_count=min_known),
                                 "old_selected": data.structural_selected.sum(),
                                 "new_switches": policy.switch_new.sum(min_count=min_known),
                                 "forced_switches": policy.switch_forced.sum(min_count=min_known),
                                 "strict_available": policy.strict_forced_cash.sum(min_count=min_known),
                                 "strict_caught": policy.strict_new_cash.sum(min_count=min_known),
                                 "cash_policy_known": policy.new_cash.count()})
    return pd.DataFrame(estimates_rows), pd.DataFrame(coverage)


def run(out):
    rows = pd.read_csv(out / "pilot_signal_ml_episodes.csv")
    keys = ["feed", "country", "origin_month"]
    if rows.duplicated(keys).any() or set(rows.feed) != {"peers", "no_peers"}:
        raise ValueError("expected one record per feed and test country-month")
    cells = rows.groupby(["country", "origin_month"]).feed.nunique()
    if not cells.eq(2).all() or not rows.origin_month.between(*WINDOWS["full"]).all():
        raise ValueError("unpaired information sets or records outside the locked test period")
    metrics, coverage = summarize(rows)
    metrics.to_csv(out / "pilot_signal_ml_metrics.csv", index=False, float_format="%.12g")
    coverage.to_csv(out / "pilot_signal_ml_coverage.csv", index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    run(parser.parse_args().out)
