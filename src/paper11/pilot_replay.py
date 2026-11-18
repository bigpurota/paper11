"""Two-stage repayment-information replay on US SBA 504 disbursement vintages."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .data import fetch

REGIONS = {
    "Northeast": "CT ME MA NH RI VT NJ NY PA",
    "Midwest": "IL IN MI OH WI IA KS MN MO NE ND SD",
    "South": "DE DC FL GA MD NC SC VA WV AL KY MS TN AR LA OK TX",
    "West": "AZ CO ID MT NV NM UT WY AK CA HI OR WA",
}
STATE_REGION = {state: region for region, states in REGIONS.items() for state in states.split()}
SOURCE = "sba504_1991_2009"
AS_OF = pd.Timestamp("2026-09-30")
HORIZON = 25
STRENGTH = 20.
PAYOFF_LOSS = .50
WINDOW = 12
MATURITY = 13   # a full quarter of three-year outcomes is available 13 quarters later
FIRST = 1999 * 4
LAST = 2006 * 4 + 1   # last continuation is 2009 Q3, prior to end of approval extract


def period(q):
    return f"{q // 4}Q{q % 4 + 1}"


def cohort(path):
    cols = ["AsOfDate", "ProjectState", "ApprovalDate", "FirstDisbursementDate", "ChargeOffDate"]
    a = pd.read_csv(path, usecols=cols, parse_dates=cols[2:] + ["AsOfDate"])
    if not a.AsOfDate.eq(AS_OF).all():
        raise ValueError("unexpected date of SBA release")
    disb = a.FirstDisbursementDate
    region = a.ProjectState.map(STATE_REGION)
    dated = disb.notna()
    consistent = dated & (disb >= a.ApprovalDate)
    if (a.ChargeOffDate[consistent] < disb[consistent]).any():
        raise ValueError("a dated charge-off precedes disbursement")
    maturity = disb + pd.DateOffset(years=3)
    eligible = consistent & region.notna() & (maturity <= AS_OF)
    df = pd.DataFrame({
        "quarter": disb.dt.year * 4 + disb.dt.quarter - 1, "region": region, "day": disb,
        "event": a.ChargeOffDate.notna() & a.ChargeOffDate.le(maturity),
    }).loc[eligible]
    df["quarter"] = df.quarter.astype(int)
    cells = df.groupby(["quarter", "region", "day"]).event.agg(n="size", events="sum").reset_index()
    counts = dict(source_rows=len(a), missing_disbursement=int((~dated).sum()),
                  disbursement_precedes_approval=int((dated & ~consistent).sum()),
                  outside_census_regions=int((consistent & region.isna()).sum()),
                  immature=int((consistent & region.notna() & (maturity > AS_OF)).sum()),
                  retained=len(df), recorded_three_year_chargeoffs=int(df.event.sum()))
    return cells, counts


def mean_margin(probability, interest):
    return interest - (interest + PAYOFF_LOSS) * probability


def posterior(q, outcome):
    return (STRENGTH * q + outcome) / (STRENGTH + 1.)


def pilot_plan(q, interest):
    """One marginal loan now; the same known H opportunities in both branches."""
    immediate = mean_margin(q, interest)
    branch = [(1 - q, posterior(q, 0)), (q, posterior(q, 1))]
    continuation = sum(weight * max(0., mean_margin(risk, interest)) for weight, risk in branch)
    gross = HORIZON * (continuation - max(0., immediate))
    return immediate, gross, immediate + gross > 1e-12


def sample_rate(history):
    if len(history) != WINDOW or history.n.sum() == 0:
        raise ValueError("incomplete matured history in a regional decision")
    # Jeffreys' half-event and half-non-event keep both single-loan outcomes
    # possible, including in mature windows with no recorded charge-offs.
    return float((history.events.sum() + .5) / (history.n.sum() + 1))


def history(cells, region, last):
    return cells[(cells.region == region) & cells.quarter.between(last - WINDOW + 1, last)]


def episode(q_initial, q_fresh, pilot_rate, future_rate, interest, arrival=1.):
    """Score both outcome branches on the same continuation panel, after freezing actions."""
    immediate, expected_gross, select = pilot_plan(q_initial, interest)
    no_action = mean_margin(q_fresh, interest) > 1e-12
    repay_action = mean_margin(posterior(q_fresh, 0), interest) > 1e-12
    event_action = mean_margin(posterior(q_fresh, 1), interest) > 1e-12
    # Scoring only: integrate a single uniformly drawn loan, and H uniformly
    # drawn continuation borrowers without replacement. Portfolios are paired.
    pilot_cash = mean_margin(pilot_rate, interest)
    continuation_cash = HORIZON * mean_margin(future_rate, interest)
    baseline = int(no_action) * continuation_cash
    stale = int(immediate > 1e-12) * continuation_cash
    branch_lend = (1 - pilot_rate) * int(repay_action) + pilot_rate * int(event_action)
    gross = arrival * (branch_lend * continuation_cash - baseline)
    pilot_cash *= arrival
    eligible = immediate < -1e-12
    modeled = bool(eligible and select)
    forced = bool(eligible)
    row = dict(predicted_immediate=immediate, predicted_gross=expected_gross, eligible=eligible,
               model_pilots=modeled, fresh_lend=no_action, lend_after_no_event=repay_action,
               lend_after_event=event_action, forced_signal_changes_policy=repay_action != event_action,
               no_pilot_fresh=baseline, no_pilot_stale=stale, no_pilot_decline=0.)
    for name, ask in [("model", modeled), ("forced", forced)]:
        row.update({name + "_pilot_margin": int(ask) * pilot_cash,
                    name + "_gross": int(ask) * gross,
                    name + "_net": int(ask) * (gross + pilot_cash),
                    name + "_total": baseline + int(ask) * (gross + pilot_cash)})
    return row


def chronological_panels(pilot_days, target_days):
    """Random start month, first available daily SBA batch; first H future arrivals."""
    pilot_days = pilot_days.sort_values("day")
    first_month = (pilot_days.day.iloc[0].month - 1) // 3 * 3 + 1
    rates = []
    for month in range(first_month, first_month + 3):
        available = pilot_days[pilot_days.day.dt.month >= month]
        if not available.empty:
            batch = available.iloc[0]
            rates.append(batch.events / batch.n)
    target_days = target_days.sort_values("day")
    remaining = (HORIZON - (target_days.n.cumsum() - target_days.n)).clip(lower=0)
    draws = np.minimum(remaining, target_days.n)
    if draws.sum() != HORIZON:
        raise ValueError("the historical panel cannot evaluate the fixed portfolio")
    future_rate = (draws * target_days.events / target_days.n).sum() / HORIZON
    return len(rates) / 3, float(np.mean(rates)), float(future_rate)


def replay(daily):
    cells = daily.groupby(["quarter", "region"], as_index=False)[["n", "events"]].sum()
    batches = dict(tuple(daily.groupby(["quarter", "region"])))
    calibration = cells[cells.quarter.between(1992 * 4, 1995 * 4 + 3)]
    q_break = calibration.events.sum() / calibration.n.sum()
    # Common 50% loss and performing interest yield an ex-ante zero-margin
    # anchor at the earlier national event frequency, fixed before 1999 Q1.
    interest = PAYOFF_LOSS * q_break / (1 - q_break)
    terms = [("early_national", interest), ("fixed_10pct_interest", .10)]
    records = []
    for q in range(FIRST, LAST + 1):
        future_q = q + MATURITY
        for region in REGIONS:
            old = history(cells, region, q - MATURITY)
            # At follow-up the pilot cohort is just mature. Its labels can enter
            # only through the one funded pilot. Both policies share older data.
            updated = history(cells, region, q - 1)
            initial, fresh = sample_rate(old), sample_rate(updated)
            pilot = cells[(cells.region == region) & (cells.quarter == q)].iloc[0]
            target = cells[(cells.region == region) & (cells.quarter == future_q)].iloc[0]
            if pilot.n < 1 or target.n < HORIZON:
                raise ValueError("the historical panel cannot evaluate the fixed portfolio")
            temporal = chronological_panels(batches[q, region], batches[future_q, region])
            for sampling, (arrival, pilot_rate, future_rate) in [
                ("chronological", temporal),
                ("uniform_quarter", (1., pilot.events / pilot.n, target.events / target.n)),
            ]:
                for name, r in terms:
                    result = episode(initial, fresh, pilot_rate, future_rate, r, arrival)
                    records.append(dict(
                        sampling=sampling, pilot_arrival_probability=arrival, sampling_pilot_rate=pilot_rate,
                        sampling_future_rate=future_rate,
                        terms=name, pilot_quarter=period(q), future_quarter=period(future_q), region=region,
                        maturity_quarters=MATURITY, future_capacity=HORIZON, prior_strength=STRENGTH,
                        interest=r, default_loss=PAYOFF_LOSS, break_even=r / (r + PAYOFF_LOSS),
                        last_mature_at_pilot=period(q - MATURITY), last_common_at_followup=period(q - 1),
                        prior_n=int(old.n.sum()), q_initial=initial, fresh_n=int(updated.n.sum()), q_fresh=fresh,
                        pilot_pool=int(pilot.n), pilot_pool_events=int(pilot.events),
                        future_pool=int(target.n), future_pool_events=int(target.events), **result,
                    ))
    return pd.DataFrame(records), dict(calibration_loans=int(calibration.n.sum()),
                                      calibration_events=int(calibration.events.sum()))


def clustered_interval(values, weights, block, draws=4000, seed=1109):
    """Circular moving-block bootstrap of calendar-quarter sums and counts."""
    n = len(values)
    rng = np.random.default_rng(seed)
    start = rng.integers(n, size=(draws, (n + block - 1) // block))
    ix = ((start[:, :, None] + np.arange(block)) % n).reshape(draws, -1)[:, :n]
    count = weights[ix].sum(axis=1)
    keep = count > 0
    if not keep.any():
        return np.nan, np.nan
    ratios = values[ix].sum(axis=1)[keep] / count[keep]
    return tuple(np.quantile(ratios, [.025, .975]))


def summary(panel):
    rows = []
    for (sampling, terms), all_cells in panel.groupby(["sampling", "terms"], sort=False):
        quarter_grid = all_cells.pilot_quarter.drop_duplicates()
        cases = all_cells[all_cells.eligible]
        for strategy in ["model", "forced"]:
            for label in ["gross", "pilot_margin", "net", "total", "no_pilot_fresh", "no_pilot_stale",
                          "no_pilot_decline"]:
                col = strategy + "_" + label if not label.startswith("no_pilot") else label
                quarter = cases.groupby("pilot_quarter")[col].agg(["sum", "size"]).reindex(quarter_grid, fill_value=0)
                v, w = quarter["sum"].to_numpy(), quarter["size"].to_numpy()
                intervals = {b: clustered_interval(v, w, b) for b in (4, 8)}
                rows.append(dict(sampling=sampling, terms=terms, strategy=strategy, measure=label,
                                 scheduled_cells=len(all_cells), eligible_cells=len(cases),
                                 quarters_total=len(quarter_grid), quarters_with_eligible=int((w > 0).sum()),
                                 pilot_cells=int(cases.model_pilots.sum()) if strategy == "model" else len(cases),
                                 signal_sensitive_cells=int(cases.loc[
                                     cases.model_pilots if strategy == "model" else cases.eligible,
                                     "forced_signal_changes_policy"].sum()),
                                 mean_per_eligible_episode=v.sum()/w.sum() if w.sum() else np.nan,
                                 ci_4q_low=intervals[4][0], ci_4q_high=intervals[4][1],
                                 ci_8q_low=intervals[8][0], ci_8q_high=intervals[8][1]))
    return pd.DataFrame(rows)


def run(out, cache):
    cells, counts = cohort(fetch(SOURCE, cache))
    panel, calibration = replay(cells)
    counts.update(calibration)
    selected_quarters = panel[(panel.terms == "early_national") & (panel.sampling == "chronological")]
    counts.update(pilot_pool_loans=int(selected_quarters.pilot_pool.sum()),
                  continuation_pool_loans=int(selected_quarters.future_pool.sum()))
    out.mkdir(parents=True, exist_ok=True)
    for tag, df in [("cohort", pd.DataFrame([counts])), ("episodes", panel), ("summary", summary(panel))]:
        df.to_csv(out / f"pilot_replay_{tag}.csv", index=False, float_format="%.12g")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    args = parser.parse_args()
    run(args.out, args.cache)
