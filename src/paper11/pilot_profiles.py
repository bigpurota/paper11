"""Origination profiles and historical peer comparisons for the Bondora discovery cases."""
import argparse
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

from .lender_pilot import fetch_bondora, fetch_bondora_followup


KEYS = ["country", "customer", "pilot_month"]
CONTRACT = ["LoanNumber", "LoanDate", "Country", "NewCreditCustomer", "Amount", "AppliedAmount",
            "MaturityDate_Original", "Interest", "NoOfPreviousLoansBeforeLoan",
            "AmountOfPreviousLoansBeforeLoan"]
FEATURES = ["principal", "application_amount", "original_term_calendar_months", "quoted_interest_pct",
            "previous_loans", "previous_loan_amount", "prior_n", "matured_pd", "pd_trend",
            "recent_count_3m", "recent_median_principal", "principal_to_recent_median", "original_net"]


def read_book(path, member, columns):
    with ZipFile(path) as archive, archive.open(member) as raw:
        return pd.read_csv(raw, usecols=columns)


def at_origination(raw, scheduled):
    """Select the same candidate as the original replay; use only pre-pilot history."""
    book = raw.sort_values(["LoanDate", "LoanNumber"], kind="stable").copy()
    dates = pd.to_datetime(book.LoanDate)
    book["country"] = book.Country
    book["customer"] = np.where(book.NewCreditCustomer, "new", "returning")
    book["month"] = dates.dt.to_period("M")
    # A 12-month default label may first enter an origin profile once its entire month is mature.
    book["historical_event"] = pd.to_datetime(book.DefaultDate).le(dates + pd.DateOffset(years=1))
    book["original_months"] = ((pd.to_datetime(book.MaturityDate_Original).dt.year - dates.dt.year)*12
                               + pd.to_datetime(book.MaturityDate_Original).dt.month - dates.dt.month)
    series = dict(tuple(book.groupby(["country", "customer"], sort=False)))
    records = []
    for case in scheduled.itertuples(index=False):
        group = series[(case.country, case.customer)]
        month = pd.Period(case.pilot_month, "M")
        pilot = group.loc[group.month.eq(month)].iloc[0]
        early = group.loc[group.month.between(month-24, month-19), "historical_event"]
        late = group.loc[group.month.between(month-18, month-13), "historical_event"]
        n = len(early)+len(late)
        pd_est = (early.sum()+late.sum()+.5)/(n+1)
        if n != case.prior_n or not np.isclose(pd_est, case.q_initial, atol=1e-11, rtol=0):
            raise ValueError("mature origin window disagrees with the frozen replay")
        trend = np.nan
        if len(late) and len(early):
            trend = (late.sum()+.5)/(len(late)+1) - (early.sum()+.5)/(len(early)+1)
        recent = group.loc[group.month.between(month-3, month-1), "Amount"]
        recent_median = recent.median()
        records.append(dict(country=case.country, customer=case.customer, pilot_month=case.pilot_month,
                            loan_key=pilot.LoanNumber, principal=pilot.Amount,
                            application_amount=pilot.AppliedAmount, original_term_calendar_months=pilot.original_months,
                            quoted_interest_pct=pilot.Interest, previous_loans=pilot.NoOfPreviousLoansBeforeLoan,
                            previous_loan_amount=pilot.AmountOfPreviousLoansBeforeLoan, prior_n=n, matured_pd=pd_est,
                            pd_trend=trend, recent_count_3m=len(recent), recent_median_principal=recent_median,
                            principal_to_recent_median=pilot.Amount/recent_median if recent_median > 0 else np.nan,
                            original_net=case.predicted_net, eligible=case.eligible, selected=case.selected))
    return pd.DataFrame(records)


def check_origin_fields(early_book, late_book, keys):
    """Describe agreement between archives; a later release is only a diagnostic."""
    first = early_book.set_index("LoanNumber").loc[keys, CONTRACT[1:]]
    second = late_book.set_index("LoanNumber").loc[keys, CONTRACT[1:]]
    rows = []
    for name in first:
        both = first[name].notna() & second[name].notna()
        rows.append(dict(field=name, loans=len(keys), compared=int(both.sum()),
                         discordant=int((first.loc[both,name] != second.loc[both,name]).sum()),
                         missing_in_one=int((first[name].isna() ^ second[name].isna()).sum())))
    return pd.DataFrame(rows)


def peer_summary(cases):
    """The zero-success neighbors are retained in every applicable comparator."""
    eligible = cases.loc[cases.eligible]
    successes = eligible.loc[eligible.selected & eligible.euro_covered]
    other = eligible.loc[~eligible.index.isin(successes.index)]
    segment = other.country.eq("EE") & other.customer.eq("returning")
    peers = {
        "two_named_successes": successes,
        "other_eligible": other,
        "other_selected": other.loc[other.selected],
        "other_eligible_same_segment": other.loc[segment],
        "other_eligible_same_months": other.loc[other.pilot_month.isin(successes.pilot_month)],
    }
    rows = []
    for name, data in peers.items():
        for field in FEATURES:
            obs = data[field].dropna()
            rows.append(dict(comparator=name, episodes=len(data), selected=int(data.selected.sum()),
                             field=field, observed=len(obs), median=obs.median(),
                             q25=obs.quantile(.25), q75=obs.quantile(.75),
                             minimum=obs.min(), maximum=obs.max()))
    return pd.DataFrame(rows)


def run(out, cache):
    out = Path(out)
    scheduled = pd.read_csv(out/"lender_pilot_episodes.csv")
    late_outcomes = pd.read_csv(out/"lender_pilot_followup.csv",
                                usecols=KEYS+["euro_covered", "euro_net", "action_changed"])
    early = read_book(fetch_bondora(cache), "LoanData_Bondora.csv", CONTRACT+["DefaultDate"])
    origins = at_origination(early, scheduled)
    late = read_book(fetch_bondora_followup(cache), "LoanData.csv", CONTRACT)
    agreement = check_origin_fields(early, late, origins.pop("loan_key").tolist())
    joined = origins.merge(late_outcomes, on=KEYS, validate="one_to_one")
    if len(joined) != len(scheduled):
        raise ValueError("cash scoring records do not cover all scheduled origins")
    selected = joined[joined.selected].sort_values(KEYS)
    for name, df in [("selected", selected), ("comparators", peer_summary(joined)),
                     ("field_agreement", agreement)]:
        df.to_csv(out/f"pilot_profiles_{name}.csv", index=False, float_format="%.12g")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    options = parser.parse_args()
    run(options.out,options.cache)
