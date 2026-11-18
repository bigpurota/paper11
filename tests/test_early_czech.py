import numpy as np
import pandas as pd

from paper11.early_czech import label_loans


def example_loans():
    return pd.DataFrame({"account_id": [1, 2, 3, 4], "origin": pd.to_datetime(["1996-01-15"] * 4),
                         "payments": [100.] * 4, "amount": [1200.] * 4, "region": ["A"] * 4})


def example_payments():
    rows = []
    for month in range(1, 13):
        date = pd.Timestamp("1996-01-15") + pd.DateOffset(months=month)
        rows.append((1, date, 100., 25.))
        if month <= 6:
            rows.append((2, date, 100., 25.))
    # Ignore disbursement-day credits. Both origin-month and month-end debits count.
    rows.extend([(3, pd.Timestamp("1996-01-15"), 8000., 0.),
                 (4, pd.Timestamp("1996-01-16"), 100., -10.),
                 (4, pd.Timestamp("1996-04-30"), 100., 10.)])
    return pd.DataFrame(rows, columns=["account_id", "paid_on", "paid", "balance"])


def test_repayment_dates_cross_the_instalment_boundaries():
    result = label_loans(example_loans(), example_payments()).set_index("account_id")
    assert list(result.e3) == [0, 0, 1, 1]
    assert list(result.short_by_month3) == [0, 0, 1, 0]
    assert list(result.e6) == [0, 0, 1, 1]
    assert list(result.y12) == [0, 1, 1, 1]
    assert result.loc[4, "early_tagged_debits"] == 2
    assert result.loc[4, "early_overdraft_debits"] == 1


def test_future_payments_cannot_change_closed_early_flags():
    loans, tx = example_loans(), example_payments()
    extra = pd.DataFrame([(3, pd.Timestamp("1996-08-01"), 10000., 500.)], columns=tx.columns)
    early = label_loans(loans, tx, as_of=pd.Period("1996-07", freq="M"))
    full = label_loans(loans, pd.concat([tx, extra], ignore_index=True))
    assert early.y12.isna().all()
    assert early.e6.notna().all() and np.array_equal(early.e6, full.e6)
    even_earlier = label_loans(loans, tx, as_of=pd.Period("1996-04", freq="M"))
    assert even_earlier.e6.isna().all() and even_earlier.e3.notna().all()


def test_forecast_uses_only_labels_available_at_issue():
    from paper11.early_czech import episode_counts, forecast

    def loan(offset, region, e3, e6, y12):
        return dict(month=pd.Period("1996-01", freq="M") + offset, region=region,
                    e3=e3, e6=e6, y12=y12, amount=100.)

    loans = pd.DataFrame([loan(-24,"A",1,1,1)] * 5 + [loan(-13,"A",0,0,0)] * 3
                         + [loan(-13,"B",1,0,1), loan(-12,"A",1,1,1),
                            loan(-7,"A",0,0,1), loan(-4,"A",0,1,1), loan(0,"A",1,1,1)])
    date = pd.period_range("1996-01", periods=1, freq="M")
    before = forecast(episode_counts(loans, date))
    assert tuple(before.loc[0, ["old_n", "old_e6", "young6_n", "young6_e", "young3_n", "young3_e"]]) == (8,5,2,1,2,0)
    # Younger annual flags, immature E6/E3 and current book principal cannot enter an issue forecast.
    loans.loc[loans.month >= date[0]-12, "y12"] = 0
    loans.loc[loans.month >= date[0]-6, "e6"] = 0
    loans.loc[loans.month >= date[0]-3, "e3"] = 0
    loans.loc[loans.month == date[0], "amount"] = 99999
    after = forecast(episode_counts(loans, date))
    assert np.array_equal(before[["local","other","six","three"]], after[["local","other","six","three"]])
    assert before.events.item() == 1 and after.events.item() == 0


def test_early_policy_counts_and_payoff_preserve_open_and_closed_books():
    from paper11.early_czech import summaries

    examples = pd.DataFrame([
        dict(month="1996-01", loans=3, events=1, principal=1000., event_principal=100.,
             local=.25, other=.04, six=.15, three=.25),
        dict(month="1996-02", loans=2, events=0, principal=1900., event_principal=0.,
             local=.02, other=.05, six=.21, three=.21)])
    _, direction, policy = summaries(examples)
    main = policy.query("method=='six' and reference=='local' and good==.10").iloc[0]
    assert (main.extra_books, main.dropped_books, main.extra_loans, main.dropped_loans) == (1,1,3,2)
    assert main.delta_margin_czk == 90.-45.-190.
    assert direction.query("method=='six'").true_flags.item() == 0
