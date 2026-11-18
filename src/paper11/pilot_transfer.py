"""Transport the SBA 504 pilot rule to two independent SBA 7(a) loan files."""
import argparse
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import hypergeom
from sklearn.metrics import roc_auc_score

from .data import fetch
from . import pilot_replay as base


SOURCES = ("sba7a_1991_1999", "sba7a_2000_2009")
REGIONS = tuple(base.REGIONS)
SEED = 1109
REFERENCE_INTEREST = base.PAYOFF_LOSS * 27 / (9398 - 27)
TOL = 1e-12


def read_loans(paths):
    """Only dates, repayment indicator and region survive the row-level read."""
    cols = ["AsOfDate", "ProjectState", "ApprovalDate", "FirstDisbursementDate", "ChargeOffDate",
            "GrossApproval", "GrossChargeOffAmount"]
    pieces = []
    counts = Counter()
    for path in paths:
        for a in pd.read_csv(path, usecols=cols, dtype=str, chunksize=125000):
            if len(a.AsOfDate.unique()) != 1 or pd.Timestamp(a.AsOfDate.iloc[0]) != base.AS_OF:
                raise ValueError("unexpected date of SBA release")
            day = pd.to_datetime(a.FirstDisbursementDate, format="mixed")
            approval = pd.to_datetime(a.ApprovalDate, format="mixed")
            charge = pd.to_datetime(a.ChargeOffDate, format="mixed")
            maturity = day + pd.DateOffset(years=3)
            region = a.ProjectState.map(base.STATE_REGION)
            valid_dates = day.notna() & approval.notna() & day.ge(approval)
            valid_charge = valid_dates & (charge.isna() | charge.ge(day))
            keep = valid_charge & region.notna() & (maturity <= base.AS_OF)
            counts.update(source_rows=len(a), missing_disbursement=int(day.isna().sum()),
                          inconsistent_approval=int((day.notna() & ~valid_dates).sum()),
                          chargeoff_before_disbursement=int((valid_dates & ~valid_charge).sum()),
                          outside_regions=int((valid_charge & region.isna()).sum()),
                          immature=int((valid_charge & region.notna() & (maturity > base.AS_OF)).sum()),
                          retained=int(keep.sum()))
            event = charge[keep].le(maturity[keep])
            approved = pd.to_numeric(a.loc[keep, "GrossApproval"], errors="coerce")
            amount = pd.to_numeric(a.loc[keep, "GrossChargeOffAmount"], errors="coerce")
            severity = (amount / approved.where(approved > 0)).where(amount >= 0).where(event, 0.)
            counts["events_missing_chargeoff_fraction"] += int((event & severity.isna()).sum())
            pieces.append(pd.DataFrame({"day": day[keep], "region": region[keep], "event": event,
                                        "chargeoff_fraction": severity}))
    loans = pd.concat(pieces, ignore_index=True)
    loans["region"] = pd.Categorical(loans.region, categories=REGIONS)
    loans["quarter"] = loans.day.dt.year * 4 + loans.day.dt.quarter - 1
    counts["events"] = int(loans.event.sum())
    return loans, dict(counts)


def draw_panel(pilot, future, q, region_index):
    """Sample indices independently of their events; the order for ties is fixed by source."""
    p_rng, f_rng = [np.random.default_rng(s) for s in np.random.SeedSequence(
        [SEED, q, region_index]).spawn(2)]
    month = 1 + 3 * (q % 4) + p_rng.integers(3)
    available = pilot[pilot.day.dt.month >= month]
    selected_pilot = None
    if len(available):
        first_day = available[available.day == available.day.min()]
        selected_pilot = first_day.iloc[p_rng.integers(len(first_day))]
    future = future.sort_values("day", kind="stable")
    boundary = future.day.iloc[base.HORIZON - 1]
    first = future[future.day < boundary]
    tied = future[future.day == boundary]
    size = base.HORIZON - len(first)
    chosen = f_rng.choice(len(tied), size=size, replace=False)
    return selected_pilot, pd.concat([first, tied.iloc[chosen]])


def recorded_margin(interest, plan, pilot, future):
    """Realized gross charge-offs on an equal-principal portfolio; non-event payoffs are scenarios."""
    if pilot is None:
        return dict(seed_recorded_pilot_cash=0., seed_recorded_gross=0., seed_recorded_net=0.,
                    seed_recorded_loss_recovered=False)
    direct = -pilot.chargeoff_fraction if pilot.event else interest
    followup = np.where(future.event.to_numpy(), -future.chargeoff_fraction.to_numpy(), interest)
    decision = plan["lend_after_event"] if pilot.event else plan["lend_after_no_event"]
    delta = int(decision) - int(plan["fresh_lend"])
    gross = delta * followup.sum() if delta else 0.
    net = direct + gross
    success = (direct < -TOL and delta != 0 and net > TOL) if np.isfinite(net) else np.nan
    return dict(seed_recorded_pilot_cash=direct, seed_recorded_gross=gross,
                seed_recorded_net=net, seed_recorded_loss_recovered=success)


def chargeoff_witness(pilots, future, q, plan, interest):
    """Condition on the *original* fixed 25 follow-ups, then enumerate feasible failed pilots.

    This audits existence after the fact. It cannot replace the precommitted seed.
    """
    delta = int(plan["lend_after_event"]) - int(plan["fresh_lend"])
    future_cash = base.mean_margin(future.event.mean(), interest) * len(future)
    recorded_future = np.where(future.event, -future.chargeoff_fraction, interest).sum()
    gross, recorded_gross = delta * future_cash, delta * recorded_future if delta else 0.
    first = None
    default_probability = recorded_recovery_probability = 0.
    for m in range(1 + 3*(q % 4), 4 + 3*(q % 4)):
        available = pilots[pilots.day.dt.month >= m]
        if available.empty:
            continue
        batch = available[available.day == available.day.min()]
        failed = batch[batch.event]
        default_probability += len(failed) / (3*len(batch))
        covered = (failed.chargeoff_fraction > TOL) & (recorded_gross - failed.chargeoff_fraction > TOL)
        recorded_recovery_probability += covered.sum() / (3*len(batch))
        if first is None and len(failed):
            first = failed.iloc[0]
    scenario_probability = default_probability if gross > base.PAYOFF_LOSS + TOL else 0.
    return dict(fixed_future_prob_strict=scenario_probability,
                fixed_future_prob_recorded_strict=recorded_recovery_probability,
                fixed_future_first_failed_pilot_cash=(np.nan if first is None else -first.chargeoff_fraction),
                fixed_future_recorded_gross_on_failure=recorded_gross,
                fixed_future_scenario_gross_on_failure=gross)


def future_counts(days):
    """Exact event count distribution on the same chronological 25-slot portfolio."""
    days = days.sort_values("day")
    pos = days.n.cumsum().searchsorted(base.HORIZON)
    if pos >= len(days):
        raise ValueError("fewer loans than the fixed follow-up capacity")
    earlier, last = days.iloc[:pos], days.iloc[pos]
    draw = base.HORIZON - int(earlier.n.sum())
    indices = np.arange(max(0, draw + last.events - last.n), min(draw, last.events) + 1,
                        dtype=int)
    return (int(earlier.events.sum()) + indices,
            hypergeom.pmf(indices, int(last.n), int(last.events), draw))


def evaluate_paths(plan, interest, arrival, pilot_rate, future_dist, pilot_event, future_events):
    """Use true outcomes for scoring only. A loss recovered means a failed pilot paid for itself."""
    counts, masses = future_dist
    baseline = int(plan["fresh_lend"])
    positive = strict = change = 0.
    for y, p in ((0, 1 - pilot_rate), (1, pilot_rate)):
        action = int(plan["lend_after_event"] if y else plan["lend_after_no_event"])
        move = action - baseline
        cash = base.HORIZON * interest - (interest + base.PAYOFF_LOSS) * counts
        net = base.mean_margin(y, interest) + move * cash
        positive += arrival * p * masses[net > TOL].sum()
        if move != 0:
            change += arrival * p
            if y == 1:
                strict += arrival * p * masses[net > TOL].sum()
    if pilot_event is None:
        return dict(prob_positive_net=positive, prob_changed=change, prob_loss_recovered=strict,
                    seed_pilot_event=np.nan, seed_next_events=future_events, seed_flip=False,
                    seed_pilot_cash=0., seed_gross=0., seed_net=0., seed_loss_recovered=False)
    chosen = int(plan["lend_after_event"] if pilot_event else plan["lend_after_no_event"])
    direct = base.mean_margin(pilot_event, interest)
    gross = (chosen - baseline) * (base.HORIZON * interest - (interest + base.PAYOFF_LOSS) * future_events)
    return dict(prob_positive_net=positive, prob_changed=change, prob_loss_recovered=strict,
                seed_pilot_event=pilot_event, seed_next_events=future_events, seed_flip=chosen != baseline,
                seed_pilot_cash=direct, seed_gross=gross, seed_net=direct + gross,
                seed_loss_recovered=bool(direct < -TOL and chosen != baseline and direct + gross > TOL))


def replay(loans):
    keys = ["quarter", "region"]
    events = loans.groupby(keys + ["day"], observed=True).event.agg(n="size", events="sum").reset_index()
    cells = events.groupby(keys, as_index=False, observed=True)[["n", "events"]].sum()
    daily = dict(tuple(events.groupby(keys, observed=True)))
    borrowers = dict(tuple(loans.groupby(keys, observed=True)))
    train = cells[cells.quarter.between(1992 * 4, 1995 * 4 + 3)]
    train_events, train_n = int(train.events.sum()), int(train.n.sum())
    recalibrated = base.PAYOFF_LOSS * train_events / (train_n - train_events)
    rates = [("fixed_504", REFERENCE_INTEREST), ("early_7a", recalibrated)]
    rows = []
    for q in range(base.FIRST, base.LAST + 1):
        target = q + base.MATURITY
        for idx, region in enumerate(REGIONS):
            p_days, f_days = daily[q, region], daily[target, region]
            q0 = base.sample_rate(base.history(cells, region, q - base.MATURITY))
            q1 = base.sample_rate(base.history(cells, region, q - 1))
            arrival, p_rate, f_rate = base.chronological_panels(p_days, f_days)
            dist = future_counts(f_days)
            pilot, followup = draw_panel(borrowers[q, region], borrowers[target, region], q, idx)
            pe, fe = (None if pilot is None else int(pilot.event)), int(followup.event.sum())
            for name, interest in rates:
                policy = base.episode(q0, q1, p_rate, f_rate, interest, arrival)
                predicted = policy["predicted_immediate"] + policy["predicted_gross"]
                rows.append(dict(terms=name, pilot_quarter=base.period(q), future_quarter=base.period(target),
                                 region=region, pilot_pool=int(p_days.n.sum()), future_pool=int(f_days.n.sum()),
                                 horizon=base.HORIZON, interest=interest, q_initial=q0, q_fresh=q1,
                                 prior_strength=base.STRENGTH, arrival=arrival, expected_pilot_event=p_rate,
                                 expected_next_events=base.HORIZON * f_rate, predicted_net=predicted,
                                 **policy, **evaluate_paths(policy, interest, arrival, p_rate, dist, pe, fe),
                                 **recorded_margin(interest, policy, pilot, followup),
                                 **chargeoff_witness(borrowers[q, region], followup, q, policy, interest)))
    return pd.DataFrame(rows), dict(early_loans=train_n, early_events=train_events)


def summarize(panel):
    records = []
    for terms, all_rows in panel.groupby("terms", sort=False):
        quarters = all_rows.pilot_quarter.drop_duplicates()
        available = all_rows[all_rows.eligible]
        outcome = available.forced_net > TOL
        auc = roc_auc_score(outcome, available.predicted_net) if outcome.nunique() == 2 else np.nan
        for group, subset in [("all_eligible", available), ("selected", available[available.model_pilots]),
                              ("skipped", available[~available.model_pilots])]:
            quarters_data = subset.groupby("pilot_quarter").forced_net.agg(["sum", "size"]).reindex(quarters, fill_value=0)
            lo, hi = base.clustered_interval(quarters_data["sum"].to_numpy(), quarters_data["size"].to_numpy(), block=4)
            records.append(dict(terms=terms, group=group, scheduled=len(all_rows), episodes=len(subset),
                                predicted_avg=subset.predicted_net.mean(), forced_avg=subset.forced_net.mean(),
                                forced_ci4_lo=lo, forced_ci4_hi=hi, model_avg=subset.model_net.mean(),
                                avg_gross=subset.forced_gross.mean(), avg_direct=subset.forced_pilot_margin.mean(),
                                positive_avg_net=int((subset.forced_net > TOL).sum()),
                                possible_losses_recovered=int((subset.prob_loss_recovered > TOL).sum()),
                                mean_prob_loss_recovered=subset.prob_loss_recovered.mean(),
                                mean_prob_flip=subset.prob_changed.mean(), positive_seed_net=int((subset.seed_net > TOL).sum()),
                                seed_flips=int(subset.seed_flip.sum()), seed_losing_pilots=int((subset.seed_pilot_cash < -TOL).sum()),
                                seed_losses_recovered=int(subset.seed_loss_recovered.sum()),
                                seed_recorded_net_n=int(subset.seed_recorded_net.notna().sum()),
                                seed_recorded_losses_recovered=int(subset.seed_recorded_loss_recovered.sum()),
                                seed_recorded_avg=subset.seed_recorded_net.mean(), eligible_net_sign_auc=auc))
    return pd.DataFrame(records)


def run(out, cache):
    loans, counts = read_loans([fetch(s, cache) for s in SOURCES])
    panel, calibration = replay(loans)
    counts.update(calibration)
    main = panel[panel.terms == "fixed_504"]
    counts.update(pilot_pool=int(main.pilot_pool.sum()), future_pool=int(main.future_pool.sum()))
    out.mkdir(parents=True, exist_ok=True)
    for suffix, df in [("cohort", pd.DataFrame([counts])), ("episodes", panel),
                       ("summary", summarize(panel))]:
        df.to_csv(out / f"pilot_transfer_{suffix}.csv", index=False, float_format="%.12g")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    args = parser.parse_args()
    run(args.out, args.cache)
