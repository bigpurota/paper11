"""Explain the three named Finnish decisions from the earlier, seasoned Bondora test."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .lender_pilot import after_signal, margin
from .pilot_holdout import fetch_holdout, order_positions, read_positions, risk_pairs
from .pilot_rule import CAPACITY, STRENGTH, TOL, public_risks

CASE_MONTHS = ("2021-03", "2021-11", "2022-02")
COUNTRY = "Finland"
GRADE = "(unrated)"


def historical_inputs(loans, last_origin):
    """Build the public risk history and recent arrival counts, restricted by date."""
    before_issue = loans.loc[loans.origin < last_origin]
    series = before_issue.groupby(["country", "grade", "origin"], sort=True)
    # The original risk-update pairs are released after 13 months. Later cohorts
    # can contribute arrival counts, but their eventual defaults are unnecessary.
    last_pair_origin = last_origin - 13
    mature = before_issue.loc[before_issue.origin <= last_pair_origin]
    labels = mature.groupby(["country", "grade", "origin"]).event.agg(n="count", d="sum")
    _, releases = risk_pairs(labels, labels.index)
    counts = series.size().clip(upper=CAPACITY)
    return releases, counts


def information_at_issue(q, principal, exposure, nonempty_share, risks):
    """Separate the two mutually exclusive ways in which one signal changes a decision."""
    lend = margin(risks) > TOL
    repay_pd = after_signal(risks, 0)
    default_pd = after_signal(risks, 1)
    avoid = lend & (margin(default_pd) <= TOL)
    enable = ~lend & (margin(repay_pd) > TOL)
    # Conditional expected savings relative to the optimal no-signal action.
    # In the first case this is the loss avoided following default; in the
    # second it is positive lending margin earned following repayment.
    avoid_per_euro = np.mean(np.where(avoid, risks * -margin(default_pd), 0.))
    enable_per_euro = np.mean(np.where(enable, (1 - risks) * margin(repay_pd), 0.))
    per_euro = avoid_per_euro + enable_per_euro
    information = exposure * per_euro
    direct = principal * margin(q)
    default_flip = np.mean(risks * avoid)
    repayment_flip = np.mean((1 - risks) * enable)
    return dict(
        expected_direct=direct, expected_info_after_default=exposure * avoid_per_euro,
        expected_info_after_repayment=exposure * enable_per_euro,
        expected_information=information, expected_total=direct + information,
        expected_information_per_1000=1000 * per_euro,
        break_even_followup_principal=-direct/per_euro if per_euro > 0 else np.nan,
        break_even_pilot_principal=information/-margin(q) if margin(q) < 0 else np.nan,
        share_public_risk_in_default_pivot_band=np.mean(avoid),
        share_public_risk_in_repayment_pivot_band=np.mean(enable),
        probability_default_and_flip_given_nonempty=default_flip,
        probability_repayment_and_flip_given_nonempty=repayment_flip,
        probability_any_flip_with_nonempty=nonempty_share * (default_flip + repayment_flip),
    )


def peer_feed_at_disclosure(q, peer_flags, pilot_flag, followup_cash):
    """Both portfolios see measured same-vintage peers. Only one sees this pilot."""
    known = peer_flags.dropna()
    weight = STRENGTH + len(known)
    event_mass = STRENGTH*q + known.sum()
    without = event_mass/weight
    with_pilot = (event_mass + pilot_flag)/(weight + 1)
    direction = int(margin(with_pilot) > TOL) - int(margin(without) > TOL)
    return dict(peer_flags_known=len(known), peer_flags_unknown=int(peer_flags.isna().sum()),
                peer_defaults=int(known.sum()), later_peer_pd_without_pilot=without,
                later_peer_pd_with_pilot=with_pilot, changed_with_shared_peers=bool(direction),
                incremental_future_cash_with_shared_peers=direction * followup_cash)


def case_table(episodes, releases, counts, candidate_flags):
    eligible = episodes.loc[episodes["sample"].eq("seasoned") & episodes.eligible].copy()
    eligible["money_rank"] = eligible.score.rank(ascending=False, method="min").astype(int)
    eligible["recovery_rank"] = eligible.strict_probability.rank(ascending=False, method="min").astype(int)
    chosen = eligible.loc[eligible.country.eq(COUNTRY) & eligible.grade.eq(GRADE) &
                          eligible.origin_month.isin(CASE_MONTHS)].sort_values("origin_month")
    if tuple(chosen.origin_month) != CASE_MONTHS:
        raise ValueError("three named Finnish cases are required")
    segment_counts = counts.loc[COUNTRY, GRADE]
    rows = []
    for case in chosen.itertuples(index=False):
        origin = pd.Period(case.origin_month, freq="M")
        disclosed = [pair for date in sorted(releases) if date <= origin for pair in releases[date]]
        if len(disclosed) != case.public_pairs:
            raise ValueError("historical public update count does not match the frozen test")
        initial, updated, months = zip(*disclosed)
        risks = public_risks(case.q_initial, initial, updated, months)
        arrivals = segment_counts.reindex(pd.period_range(origin-12, origin-1, freq="M"), fill_value=0)
        if not np.isclose(arrivals.mean(), case.mean_prior_count, rtol=0, atol=1e-9):
            raise ValueError("twelve-month follow-up count differs from the frozen test")
        info = information_at_issue(case.q_initial, case.pilot_principal, case.mean_prior_exposure,
                                    (arrivals > 0).mean(), risks)
        if not np.isclose(info["expected_total"], case.score, rtol=0, atol=1e-7):
            raise ValueError("the two information branches do not recover the frozen score")
        cohort = candidate_flags[origin]
        if cohort.iloc[0] != case.pilot_default:
            raise ValueError("first contract does not have the archived pilot signal")
        peer_feed = peer_feed_at_disclosure(case.q_fresh, cohort.iloc[1:], case.pilot_default,
                                            case.future_cash)
        rows.append(dict(
            origin_month=case.origin_month, disclosure_month=case.disclosure_month,
            pilot_principal=case.pilot_principal, prior_loans=case.prior_n,
            risk_at_issue=case.q_initial, months_with_arrivals=int((arrivals > 0).sum()),
            projected_count=case.mean_prior_count, projected_principal=case.mean_prior_exposure,
            public_update_pairs=len(disclosed), **info, funding_rank=case.money_rank,
            strict_recovery_probability=case.strict_probability, strict_recovery_rank=case.recovery_rank,
            eligible_opportunities=len(eligible), selected=case.selected,
            refresh_loans=case.refresh_n, later_public_risk=case.q_fresh,
            later_public_risk_forecast_cdf=np.mean(risks <= case.q_fresh),
            later_risk_if_repaid=after_signal(case.q_fresh, 0),
            later_risk_if_default=after_signal(case.q_fresh, 1), observed_default=case.pilot_default,
            lend_without_signal=case.baseline_lend, lend_with_signal=case.informed_lend,
            observed_future_count=case.future_count, observed_future_principal=case.future_principal,
            observed_future_defaults=case.future_defaults, observed_future_cash=case.future_cash,
            direct_cash=case.pilot_cash, incremental_future_cash=case.net_cash-case.pilot_cash,
            incremental_total_cash=case.net_cash, incremental_total_scenario=case.net_scenario,
            future_outstanding=case.future_balance, **peer_feed,
        ))
    return pd.DataFrame(rows)


def run(out, cache):
    last_origin = pd.Period(CASE_MONTHS[-1], freq="M")
    raw = read_positions(fetch_holdout(cache))
    # The three named same-vintage cohorts also supply the retrospective peer feed.
    last_day = ((last_origin + 1).start_time - pd.Timestamp("1899-12-30")).days
    before = pd.to_numeric(raw.loan_issued_at, errors="raise") < last_day
    loans = order_positions(raw.loc[before])
    releases, counts = historical_inputs(loans, last_origin)
    episodes = pd.read_csv(out / "pilot_holdout_episodes.csv")
    focus = loans.loc[loans.country.eq(COUNTRY) & loans.grade.eq(GRADE) &
                      loans.origin.isin(pd.PeriodIndex(CASE_MONTHS, freq="M"))]
    candidate_flags = {month: group.event for month, group in focus.groupby("origin")}
    cases = case_table(episodes, releases, counts, candidate_flags)
    cases.to_csv(out / "finnish_pilot_cases.csv", index=False, float_format="%.12g")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    args = parser.parse_args()
    run(args.out, args.cache)
