import pandas as pd
import pytest

from paper11.frequency_panel import assemble_panels
from paper11.pilot_holdout import CASH, order_positions


def example():
    s = pd.Period("2024-06", "M")
    rows = []

    def month(offset, n, events):
        for i in range(n):
            flag = events.get(i, 0)
            rows.append(dict(country="FI", customer_risk_rating="A",
                             loan_issued_at=str((s + offset).start_time + pd.Timedelta(minutes=i)),
                             issued_amount=100+i, initial_interest_rate=0.2, initial_loan_duration=36,
                             has_default_within_12_months=None if flag is None else str(flag),
                             principal_balance=23, **dict(zip(CASH, [80, 4, 2, 1]))))

    month(-50, 65, {1: 1})
    month(-26, 35, {1: 1})
    month(-24, 60, {1: 1})
    month(-13, 60, {10: 1})
    month(-1, 5, {})
    month(0, 27, {0: 1, 2: 1, 3: None})
    month(1, 5, {})
    month(13, 27, {1: 1, 2: None, 25: 1})
    loans = order_positions(pd.DataFrame(rows))
    previous = pd.DataFrame([dict(country="FI", origin_month=str(s-13), disclosure_month=str(s),
                                  future_count=25)])
    windows = {"train": (s-26, s-26), "test": (s, s+1)}
    return loans, previous, windows


def test_identity_disjoint_candidate_keeps_future_fixed_and_only_hides_own_outcome():
    loans, prev, windows = example()
    panel, support = assemble_panels(loans, prev.assign(grade="A"), prev, windows)
    test = panel.loc[panel["sample"].eq("test") & panel.origin_month.eq("2024-06")].set_index("pilot_rank")
    assert test.index.to_list() == [1, 26]
    assert test.pilot_in_previous_continuation.tolist() == [True, False]
    assert test.pilot_in_country_book.tolist() == test.pilot_in_grade_book.tolist() == [True, False]
    assert test.peer_in_previous_scored_count.tolist() == [24, 25]
    assert test.peer_total.tolist() == [26, 26]
    assert test.peer_n.tolist() == [25, 25]
    assert test.peer_defaults.tolist() == [1, 2]
    assert test.pilot_principal.tolist() == [100, 125]
    assert test.pilot_default.tolist() == [1, 0]
    assert test.future_in_previous_continuation_count.tolist() == [0, 0]
    assert test.future_count.tolist() == [25, 25] and test.future_event_n.tolist() == [24, 24]
    assert test.future_default_principal.isna().all() and test.future_scenario.isna().all()
    assert test.future_known_default_principal.tolist() == [101, 101]
    assert test.future_unknown_principal.tolist() == [102, 102]
    assert test.q_initial.nunique() == test.q_fresh.nunique() == test.mean_prior_exposure.nunique() == 1


def test_rank_coverage_training_cutoff_and_zero_volume():
    loans, prev, windows = example()
    panel, coverage = assemble_panels(loans, pd.DataFrame(), prev, windows)
    july = coverage.loc[coverage.origin_month.eq("2024-07")].set_index("pilot_rank")
    assert july.rank_available.tolist() == july.supported.tolist() == [True, False]
    row = panel.loc[panel.origin_month.eq("2024-07")].squeeze()
    assert row.future_count == 0 and row.future_principal == row.future_unknown_principal == 0.
    assert row.future_known_default_principal == row.future_in_country_book_count == 0
    train = panel.loc[panel["sample"].eq("train")]
    assert len(train) == 1 and train.pilot_rank.tolist() == [1]
    assert train.target_ready_month.tolist() == ["2024-06"]
    assert train[["pilot_cash", "future_cash", "pilot_balance", "future_balance"]].isna().all().all()
    with pytest.raises(ValueError, match="continuation count"):
        assemble_panels(loans, pd.DataFrame(), prev.assign(future_count=26), windows)
