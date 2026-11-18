import numpy as np
import pandas as pd
import pytest

from paper11.dutch_frequency import contract_mix, diagnose, monthly_books


def make_loans(month, amounts, flags, term=60):
    return pd.DataFrame({"origin": pd.Period(month, "M"), "principal": amounts, "event": flags,
                         "initial_loan_duration": term, "grade": "(unrated)"})


def test_different_denominators_and_rounding_reconcile_at_source():
    schedule = pd.DataFrame({"origin_month": ["2023-10"]})
    loans = pd.concat([
        make_loans("2022-09", [2000]*3, [0, 0, 1]),
        make_loans("2023-09", [2000]*8, [0]*8),
        make_loans("2024-11", [2000]+[1000]*24+[3000], [1]+[0]*24+[1]),
    ], ignore_index=True)
    m = monthly_books(loans)
    peers = pd.DataFrame({"labels": [10], "defaults": [1]}, index=pd.PeriodIndex(["2022-09"], freq="M"))
    r = diagnose(m, peers, schedule).iloc[0]
    assert r.local_forecast == .375 and r.historical_labels == 3 and r.volume_ratio == 8/3
    assert r.other_countries_forecast == 1.5/11
    assert r.future_all_count_rate == 2/26 and r.first25_count_rate == 1/25
    assert r.first25_principal_rate == pytest.approx(2000/26000)
    pieces = r.smoothing_effect + r.change_across_vintages + r.first25_selection_effect + r.principal_weight_effect
    assert pieces == pytest.approx(r.local_forecast - r.first25_principal_rate)
    loans.loc[loans.index[-2], "event"] = np.nan
    missing = diagnose(monthly_books(loans), peers, schedule).iloc[0]
    assert missing.local_forecast == r.local_forecast
    assert missing.first25_labels == 24 and pd.isna(missing.first25_principal_rate)


def test_contract_standardization_counts_distinct_history_once_and_retains_missing_support():
    schedule = pd.DataFrame({"origin_month": ["2023-10", "2023-11"]})
    loans = pd.concat([
        make_loans("2022-09", [1500, 1500, 2500], [1, 0, 1]),
        make_loans("2024-11", [1500]*4+[2500], [1, 0, 0, 0, 0]),
        make_loans("2024-12", [2500], [1]),
        make_loans("2024-12", [900], [1], term=84),
    ], ignore_index=True)
    c = contract_mix(loans, schedule)
    assert c.early_labels.sum() == 3
    assert c.later_rate_at_early_weights.sum(skipna=False) == pytest.approx((2/3)*.25+(1/3)*.5)
    c = contract_mix(loans.loc[~(loans.principal.eq(2500) & loans.origin.ge("2024-01"))], schedule)
    assert pd.isna(c.later_rate_at_early_weights.sum(skipna=False))
