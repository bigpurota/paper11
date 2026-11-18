"""Dated Dutch repayment signals on the original eight future Bondora books."""
import argparse
from pathlib import Path

import pandas as pd

from .early_warning import curve_forecast, payment_forecast
from .lender_pilot import LATER_SNAPSHOT, fetch_bondora_followup
from .pilot_holdout import fetch_holdout, read_positions

WORKBOOK_FIELDS = ["country", "loan_issued_at", "early_repaid_at", "has_default_within_12_months",
                   "issued_amount"]
LEGACY_FIELDS = ["Country", "ReportAsOfEOD", "LoanNumber", "LoanDate", "DefaultDate", "Amount",
                 "FirstPaymentDate",
                 "PrincipalPaymentsMade", "InterestAndPenaltyPaymentsMade",
                 "PrincipalOverdueBySchedule", "CurrentDebtDaysPrimary"]


def read_legacy(path):
    data = pd.read_csv(path, usecols=LEGACY_FIELDS, low_memory=False)
    if not data.LoanNumber.is_unique or not pd.to_datetime(data.ReportAsOfEOD).eq(LATER_SNAPSHOT).all():
        raise ValueError("expected unique loans on the 24 May 2024 Bondora tape")
    orig = pd.to_datetime(data.LoanDate, format="mixed")
    default = pd.to_datetime(data.DefaultDate, format="mixed")
    if orig.isna().any() or (default < orig).any() or (default > LATER_SNAPSHOT).any():
        raise ValueError("unusable origination or recorded default date")
    return data.assign(day=orig, origin=orig.dt.to_period("M"),
                       d90=default.le(orig + pd.Timedelta(days=90)),
                       e6=default.le(orig + pd.DateOffset(months=6)),
                       y12=default.le(orig + pd.DateOffset(months=12)))


def payoff_records(raw):
    loans = raw.loc[raw.country.eq("Netherlands")].copy()
    # Convert Excel calendar dates first. A date-only payoff can be recorded earlier
    # in the day than origination even though both refer to the same calendar day.
    def day(field):
        serial = pd.to_numeric(loans[field], errors="raise")
        days = serial.dropna().astype("int64")
        return pd.to_datetime(days, unit="D", origin="1899-12-30").reindex(serial.index)
    issue, paid = day("loan_issued_at"), day("early_repaid_at")
    if issue.isna().any() or (paid < issue).any():
        raise ValueError("invalid dated early payoff")
    y = pd.to_numeric(loans.has_default_within_12_months, errors="raise")
    if not y.dropna().isin([0, 1]).all():
        raise ValueError("invalid first-year Dutch event flag")
    return loans.assign(day=issue, origin=issue.dt.to_period("M"), a90=paid.le(issue + pd.Timedelta(days=90)), y=y)


def snapshot(legacy, workbook):
    """Summarize a genuine servicing snapshot and reconcile the dated vintage across both tapes."""
    def at_age(day):
        return (LATER_SNAPSHOT - day).dt.days.between(60, 89)

    young = legacy.loc[legacy.Country.eq("NL") & at_age(legacy.day)].copy()
    later = workbook.loc[at_age(workbook.day)]
    due = pd.to_datetime(young.FirstPaymentDate)
    cash = young[["PrincipalPaymentsMade", "InterestAndPenaltyPaymentsMade"]]
    if due.isna().any() or (due > LATER_SNAPSHOT).any() or cash.isna().any().any():
        raise ValueError("first scheduled instalment or snapshot cash is unobserved")
    dpd = young.CurrentDebtDaysPrimary
    arrears = young.PrincipalOverdueBySchedule
    if arrears.isna().any() or (dpd.isna() & arrears.ne(0)).any():
        raise ValueError("missing arrears duration on positive principal due")
    received, late = cash.sum(axis=1).gt(0), dpd.ge(30)
    return pd.DataFrame([dict(
        snapshot_date=str(LATER_SNAPSHOT.date()), age_min_days=60, age_max_days=89,
        issue_from=str(young.day.min().date()), issue_to=str(young.day.max().date()),
        first_due_from=str(due.min().date()), first_due_to=str(due.max().date()),
        issued=len(young), principal=young.Amount.sum(), first_payment_scheduled=len(due),
        positive_receipts=int(received.sum()), zero_receipts=int((~received).sum()),
        at_least_30dpd=int(late.sum()), zero_cash_and_30dpd=int((~received & late).sum()),
        positive_cash_and_30dpd=int((received & late).sum()),
        no_dpd_but_zero_due=int(dpd.isna().sum()), overdue_amount_positive=int(arrears.gt(0).sum()),
        revised_issued=len(later), revised_principal=pd.to_numeric(later.issued_amount).sum(),
        revised_year_known=int(later.y.count()), revised_year_events=int(later.y.sum()),
    )])


def score(legacy, workbook, forecasts):
    monthly = legacy.groupby(["Country", "origin"]).agg(n=("day", "size"), e6=("e6", "sum"),
                                                       y12=("y12", "sum"), d90=("d90", "sum"))
    dutch = monthly.xs("NL").sort_index()
    # This retrospective like-for-like timing audit never enters a forecast.
    mature_at_snapshot = legacy.day + pd.DateOffset(months=12) <= LATER_SNAPSHOT
    auditable = legacy.loc[mature_at_snapshot & legacy.Country.eq("NL")].groupby("origin").agg(
        n=("day", "size"), early=("e6", "sum"), annual=("y12", "sum"))
    bank = monthly.groupby(level="origin").sum().sort_index()
    cols = workbook.assign(ya=workbook.y * workbook.a90).groupby("origin").agg(
        n=("day", "size"), labels=("y", "count"), y=("y", "sum"), a=("a90", "sum"), ya=("ya", "sum"))
    rows = []
    for f in forecasts.itertuples(index=False):
        t = pd.Period(f.origin_month, freq="M")
        if t.start_time > LATER_SNAPSHOT:
            raise ValueError("six-month archive does not reach the forecast date")
        old = dutch.loc[t-24:t-13].sum()
        old_bank = bank.loc[t-24:t-13].sum()
        young = dutch.loc[t-12:t-7].sum()
        paid_old, paid_recent = cols.loc[t-24:t-13].sum(), cols.loc[t-9:t-4].sum()
        retrospective_young = cols.loc[t-12:t-7].sum()
        mature_young = auditable.loc[t-12:t-7].sum()
        if paid_old.n != paid_old.labels or paid_old.n != f.historical_labels or paid_old.y != f.historical_defaults:
            raise ValueError("mature workbook cohorts disagree with the earlier Dutch analysis")
        local, broad = f.local_forecast, f.other_countries_forecast
        curve = curve_forecast(local, old.e6, old.y12, old_bank.e6, old_bank.y12, young.e6, young.n)
        legacy_local = (old.y12 + .5) / (old.n + 1)
        legacy_broader = (old_bank.y12 - old.y12 + .5) / (old_bank.n - old.n + 1)
        legacy_curve = curve_forecast(legacy_local, old.e6, old.y12, old_bank.e6, old_bank.y12,
                                      young.e6, young.n)
        payment = payment_forecast(local, paid_old.n, paid_old.y, paid_old.a, paid_old.ya,
                                   paid_recent.a, paid_recent.n)
        record = dict(origin_month=str(t), disclosure_month=f.disclosure_month,
                      mature_from=str(t-24), mature_to=str(t-13),
                      six_month_from=str(t-12), six_month_to=str(t-7),
                      payoff_from=str(t-9), payoff_to=str(t-4),
                      local=local, broader=broad, target=f.first25_principal_rate,
                      future_loans=f.first25_issued, future_principal=f.first25_principal,
                      future_default_principal=f.first25_default_principal,
                      future_defaults=f.first25_defaults, future_full_rate=f.future_all_count_rate,
                      old_n=int(old.n), old_y=int(old.y12), old_e=int(old.e6),
                      old_d90=int(old.d90), bank_n=int(old_bank.n), bank_y=int(old_bank.y12),
                      bank_e=int(old_bank.e6), young_n=int(young.n), young_e=int(young.e6),
                      young_d90=int(young.d90), revised_young_n=int(retrospective_young.n),
                      revised_young_labels=int(retrospective_young.labels),
                      revised_young_year_defaults=int(retrospective_young.y),
                      revised_young_year_rate=retrospective_young.y / retrospective_young.labels,
                      young_mature_at_snapshot=int(mature_young.n),
                      young_mature_at_snapshot_e=int(mature_young.early),
                      young_mature_at_snapshot_y=int(mature_young.annual),
                      capture=curve.capture, capture_source=curve.source,
                      six_month=curve.risk, legacy_local=legacy_local, legacy_broader=legacy_broader,
                      legacy_six_month=legacy_curve.risk,
                      legacy_six_month_below_both=legacy_curve.risk < min(legacy_local, legacy_broader) - 1e-12,
                      old_payoff_n=int(paid_old.n), old_payoff_y=int(paid_old.y),
                      old_payoff_a=int(paid_old.a), old_payoff_ya=int(paid_old.ya),
                      young_payoff_n=int(paid_recent.n), young_payoff_a=int(paid_recent.a),
                      three_month=payment)
        for label, value in [("six_month", curve.risk), ("three_month", payment),
                             ("realized", f.first25_principal_rate)]:
            record[label+"_below_both"] = value < min(local, broad) - 1e-12
        rows.append(record)
    return pd.DataFrame(rows)


def policy(books):
    results = []
    for good, bad in [(0.10, -.45), (.03, -.50)]:
        threshold = good / (good - bad)
        margin = good * books.future_principal + (bad - good) * books.future_default_principal
        for method in ("six_month", "three_month"):
            action = books[method].lt(threshold)
            for base in ("local", "broader"):
                ref = books[base].lt(threshold)
                change = action.astype(int) - ref.astype(int)
                results.append(dict(good=good, bad=bad, cutoff=threshold, method=method, baseline=base,
                                    books=len(books), lent=int(action.sum()), baseline_lent=int(ref.sum()),
                                    new_lending=int(change.gt(0).sum()), new_declines=int(change.lt(0).sum()),
                                    changed_loans=int((change.abs()*books.future_loans).sum()),
                                    changed_principal=float((change.abs()*books.future_principal).sum()),
                                    scenario_difference=float((change*margin).sum())))
    return pd.DataFrame(results)


def run(out, cache):
    out = Path(out)
    forecasts = pd.read_csv(out / "dutch_frequency_episodes.csv")
    legacy = read_legacy(fetch_bondora_followup(cache))
    workbook = payoff_records(read_positions(fetch_holdout(cache), fields=WORKBOOK_FIELDS))
    books = score(legacy, workbook, forecasts)
    for kind, table in [("episodes", books), ("snapshot", snapshot(legacy, workbook)), ("policy", policy(books))]:
        table.to_csv(out / f"early_dutch_{kind}.csv", index=False, float_format="%.12g")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--cache", type=Path, default=Path("data/cache"))
    args = parser.parse_args()
    run(args.out, args.cache)
