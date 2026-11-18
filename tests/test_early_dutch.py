import numpy as np
import pandas as pd

from paper11.early_dutch import LEGACY_FIELDS, payoff_records, policy, read_legacy, score, snapshot


def test_dated_default_calendar_anniversaries(tmp_path):
    issue = pd.Timestamp("2022-08-31")
    dates = [issue + pd.Timedelta(days=90), issue + pd.Timedelta(days=91),
             pd.Timestamp("2023-02-28"), pd.Timestamp("2023-03-01"),
             pd.Timestamp("2023-08-31"), pd.Timestamp("2023-09-01"), pd.NaT]
    source = pd.DataFrame(0, index=range(len(dates)), columns=LEGACY_FIELDS)
    source["LoanDate"] = str(issue.date())
    source["DefaultDate"] = dates
    source["ReportAsOfEOD"] = "2024-05-24"
    source["LoanNumber"] = range(len(dates))
    path = tmp_path / "loan.csv"
    source.to_csv(path, index=False)
    book = read_legacy(path)
    assert book.d90.tolist() == [1, 0, 0, 0, 0, 0, 0]
    assert book.e6.tolist() == [1, 1, 1, 0, 0, 0, 0]
    assert book.y12.tolist() == [1, 1, 1, 1, 1, 0, 0]


def test_three_month_marker_uses_only_dated_payoff():
    raw = pd.DataFrame(dict(country=["Netherlands"] * 5 + ["Finland"], loan_issued_at=[45000.8]*6,
                            early_repaid_at=[45000, 45090, 45091, None, 45600, 44900],
                            has_default_within_12_months=["0", "0", "0", None, "1", "1"]))
    loans = payoff_records(raw)
    assert loans.a90.tolist() == [True, True, False, False, False]
    assert loans.y.dropna().tolist() == [0, 0, 0, 1]


def test_young_annual_outcomes_and_future_books_cannot_affect_forecast():
    months = ["2022-10"] * 8 + ["2023-08"] * 12 + ["2024-04"] * 6
    month = pd.PeriodIndex(months, freq="M")
    legacy = pd.DataFrame(dict(origin=month, day=month.to_timestamp(), Country="NL",
                               d90=False, e6=[True]*2+[False]*6+[True]+[False]*17,
                               y12=[True]*5+[False]*3+[True]*18))
    wb = pd.DataFrame(dict(origin=month, day=month.to_timestamp(),
                           a90=[True]*2+[False]*6+[True]+[False]*17,
                           y=[0]*2+[1]*5+[0]+[1]*18))
    inputs = pd.DataFrame([dict(origin_month="2024-05", disclosure_month="2025-06", local_forecast=.6,
                                other_countries_forecast=.3, first25_principal_rate=.12, first25_issued=5,
                                first25_principal=500, first25_default_principal=60, first25_defaults=1,
                                future_all_count_rate=.1, historical_labels=8, historical_defaults=5)])
    old = score(legacy, wb, inputs).iloc[0]
    legacy.loc[month >= "2023-08", "y12"] = False
    wb.loc[month >= "2023-08", "y"] = 0
    # Last month is too recent for either signal.
    legacy.loc[month == "2024-04", "e6"] = True
    wb.loc[month == "2024-04", "a90"] = True
    inputs.loc[0, "first25_principal_rate"] = .9
    new = score(legacy, wb, inputs).iloc[0]
    assert old.revised_young_year_rate != new.revised_young_year_rate
    assert old.target != new.target
    for name in ("capture", "six_month", "three_month", "young_n", "young_e", "young_payoff_a"):
        assert old[name] == new[name]
    assert (new.young_n, new.young_e) == (12, 1)
    assert (new.young_payoff_n, new.young_payoff_a) == (12, 1)


def test_snapshot_includes_no_receipts_and_zero_dpd_with_zero_arrears():
    cutoff = pd.Timestamp("2024-05-24")
    ages = [59, 60, 61, 89, 90]
    days = cutoff - pd.to_timedelta(ages, unit="D")
    source = pd.DataFrame(dict(Country="NL", day=days, FirstPaymentDate=days+pd.Timedelta(days=30),
                               Amount=100, PrincipalPaymentsMade=[1, 1, 0, 0, 0],
                               InterestAndPenaltyPaymentsMade=[0, 0, 10, 0, 0],
                               CurrentDebtDaysPrimary=[np.nan, np.nan, 29, 30, 60],
                               PrincipalOverdueBySchedule=[0, 0, 1, 5, 20]))
    workbook = pd.DataFrame(dict(day=days, issued_amount=100, y=[1, 0, 0, 1, 1]))
    row = snapshot(source, workbook).iloc[0]
    assert (row.issued, row.positive_receipts, row.at_least_30dpd, row.zero_cash_and_30dpd) == (3, 2, 1, 1)
    assert (row.revised_issued, row.revised_year_events) == (3, 1)


def test_hypothetical_margin_uses_exposure_and_direction():
    loans = pd.DataFrame(dict(local=[.3,.25], broader=[.12,.14], six_month=[.10,.2],
                              three_month=[.3,.25], future_principal=[100,200],
                              future_default_principal=[5,0], future_loans=[2,3]))
    table = policy(loans).query("good == .1 and method == 'six_month'").set_index("baseline")
    assert (table.loc["local", "new_lending"], table.loc["broader", "new_declines"]) == (1, 1)
    np.testing.assert_allclose(table.loc[["local", "broader"], "scenario_difference"], [7.25,-20])
