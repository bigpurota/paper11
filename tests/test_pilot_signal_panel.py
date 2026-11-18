import numpy as np
import pandas as pd
import pytest

from paper11.pilot_holdout import CASH, order_positions
from paper11.pilot_signal_panel import make_signal_panel


def positions():
    s = pd.Period("2022-10", "M")
    rows = []

    def add(month, n, defaults, principal, mark=None):
        for i in range(n):
            a = principal if np.isscalar(principal) else principal[i]
            flag = (None if mark == i else str(int(i < defaults)))
            rows.append(dict(loan_issued_at=str((s+month).start_time + pd.Timedelta(minutes=i)),
                             country="Finland", customer_risk_rating=None,
                             issued_amount=a, initial_loan_duration=36, initial_interest_rate=.2,
                             has_default_within_12_months=flag, principal_balance=5,
                             **dict(zip(CASH, [a*.8, 3., 2., 1.]))))

    add(-25, 12, 12, 100)
    add(-24, 60, 14, 100)
    add(-12, 50, 4, 100)
    add(-1, 7, 1, 75)
    add(0, 5, 3, 70, mark=3)
    add(13, 26, 1, [500] + 25*[100])
    return pd.DataFrame(rows), s


def one(frame, s, sample="test", previous=None):
    return make_signal_panel(order_positions(frame), previous=previous, windows={sample: (s, s)})[0].iloc[0]


def test_exact_history_pairs_and_weighted_target():
    frame, s = positions()
    row = one(frame, s)
    assert row.prior_n == 60 and row.q_initial == pytest.approx(14.5 / 61)
    assert row.refresh_n == 57 and row.q_fresh == pytest.approx(5.5 / 58)
    assert row.peer_total == 4 and row.peer_n == 3 and row.peer_defaults == 2
    assert row.mean_prior_count == pytest.approx((25+7)/12)
    assert row.mean_prior_exposure == pytest.approx((2500+525)/12)
    assert row.future_count == 25 and row.future_default_principal == 500 and row.future_principal == 2900
    assert row.pilot_cash == -8 and row.future_cash == pytest.approx(-430)
    assert row.target_ready_month == str(s + 26)
    assert row.disclosure_month == str(s + 13)


def test_private_label_excluded_from_peer_feed_and_no_outcome_in_issue_features():
    frame, s = positions()
    a = one(frame, s)
    frame.loc[frame.loan_issued_at == str(s.start_time), "has_default_within_12_months"] = "0"
    frame.loc[frame.loan_issued_at >= str((s+13).start_time), "has_default_within_12_months"] = "1"
    frame.loc[:, "interest_paid_total"] = 1000
    b = one(frame, s)
    assert a.pilot_default != b.pilot_default and a.future_default_principal != b.future_default_principal
    assert a.pilot_cash != b.pilot_cash and a.future_cash != b.future_cash
    for col in ("peer_n", "peer_defaults", "q_initial", "q_fresh", "mean_prior_exposure",
                "structural_probability", "structural_net", "structural_selected"):
        assert a[col] == b[col]


def test_training_cash_mask_and_empty_missing_distinction():
    frame, s = positions()
    train = one(frame, s, "train")
    assert train[["pilot_cash", "future_cash", "pilot_balance", "future_balance"]].isna().all()
    future = frame.loan_issued_at >= str((s+13).start_time)
    frame.loc[future, "has_default_within_12_months"] = None
    row = one(frame, s)
    assert row.future_count == 25 and row.future_event_n == 0 and np.isnan(row.future_default_principal)
    row = one(frame[~future], s)
    assert row.future_count == 0 and row.future_default_principal == 0 and row.future_cash == 0


def test_overlap_uses_archived_country_grade_source_positions():
    frame, s = positions()
    earlier = frame.iloc[[0]].copy()
    earlier["loan_issued_at"] = str((s-13).start_time)
    frame = pd.concat([frame, earlier], ignore_index=True)
    previous = pd.DataFrame([dict(country="Finland", grade="(unrated)", origin_month=str(s-13),
                                  disclosure_month=str(s), future_count=5)])
    row = one(frame, s, previous=previous)
    assert row.pilot_in_previous_continuation
    assert row.future_in_previous_pilot_count == row.future_in_previous_continuation_count == 0
