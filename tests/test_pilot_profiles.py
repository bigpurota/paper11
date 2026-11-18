import numpy as np
import pandas as pd
import pytest

from paper11.pilot_profiles import CONTRACT, at_origination, check_origin_fields


def test_profile_uses_only_mature_labels_and_past_origination_amounts():
    origin = pd.Period("2018-04", "M")
    months = pd.period_range(origin-24, origin+2, freq="M")
    dates = months.to_timestamp()
    loans = pd.DataFrame(dict(LoanNumber=np.arange(len(months)), LoanDate=dates, Country="EE",
                              NewCreditCustomer=False, Amount=100., AppliedAmount=100.,
                              Interest=16., NoOfPreviousLoansBeforeLoan=2, AmountOfPreviousLoansBeforeLoan=300.,
                              MaturityDate_Original=dates+pd.DateOffset(years=3), DefaultDate=pd.NaT))
    loans.loc[months == origin, ["Amount", "AppliedAmount"]] = 50.
    loans.loc[months == origin-13, "DefaultDate"] = (origin-1).start_time
    ep = pd.DataFrame([dict(country="EE", customer="returning", pilot_month=str(origin),
                            prior_n=12, q_initial=1.5/13, predicted_net=.1, eligible=True, selected=True)])
    result = at_origination(loans, ep)
    case = result.iloc[0]
    assert case.original_term_calendar_months == 36
    assert case.recent_count_3m == 3 and case.principal_to_recent_median == .5
    assert case.pd_trend == pytest.approx(1/7)
    assert case.previous_loans == 2 and case.principal == 50
    loans.loc[months >= origin-12, "DefaultDate"] = dates[months >= origin-12]+pd.Timedelta(days=1)
    loans.loc[months > origin, ["Amount", "AppliedAmount"]] = 40_000
    pd.testing.assert_frame_equal(result, at_origination(loans, ep))


def test_release_check_reports_changes_and_missingness_without_imputing_contracts():
    row = {col: 1 for col in CONTRACT}
    first = pd.DataFrame([row])
    second = first.copy()
    second["Interest"] = 2
    second["AppliedAmount"] = np.nan
    agreement = check_origin_fields(first, second, [1]).set_index("field")
    assert agreement.loc["Interest", "discordant"] == 1
    assert agreement.loc["AppliedAmount", "missing_in_one"] == 1
    assert agreement.loc["NoOfPreviousLoansBeforeLoan", "compared"] == 1
