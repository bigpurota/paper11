from itertools import combinations

import numpy as np
import pandas as pd
import pytest

from paper11 import pilot_replay as replay


def test_ledger_counts_recorded_three_year_events_and_removes_unusable_dates(tmp_path):
    def row(disb, charge, state="NY", approval="2000-01-01"):
        return ["2026-09-30", state, approval, disb, charge]
    supplies = [
        row("2000-02-29", "2003-02-28"), row("2000-02-29", "2003-03-01"),
        row("2000-02-29", None), row(None, None), row("1999-09-01", None),
        row("2000-02-29", None, "PR"), row("2026-02-01", None),
    ]
    cols = ["AsOfDate", "ProjectState", "ApprovalDate", "FirstDisbursementDate", "ChargeOffDate"]
    ledger = pd.DataFrame(supplies, columns=cols)
    path = tmp_path / "data.csv"
    ledger.to_csv(path, index=False)
    data, counts = replay.cohort(path)
    assert data.n.sum() == 3 and data.events.sum() == 1
    assert counts["immature"] == counts["outside_census_regions"] == 1
    assert counts["missing_disbursement"] == counts["disbursement_precedes_approval"] == 1
    ledger.loc[0, "ChargeOffDate"] = "1999-01-01"
    ledger.to_csv(path, index=False)
    with pytest.raises(ValueError, match="precedes"):
        replay.cohort(path)


def test_first_available_day_and_capacity_ties_match_enumerated_draws(monkeypatch):
    monkeypatch.setattr(replay, "HORIZON", 3)
    batches = pd.DataFrame({"day": pd.to_datetime(["2000-01-20", "2000-01-21", "2000-02-10"]),
                            "n": [1, 3, 4], "events": [0, 2, 1]})
    a, q, f = replay.chronological_panels(batches.iloc[::-1], batches)
    # January starts on day 20, skipping the following batch; February starts
    # on day 10. In this example a March assignment never yields a pilot.
    assert (a, q) == pytest.approx((2 / 3, (0 + 1 / 4) / 2))
    draws = [(0 + sum(t)) / 3 for t in combinations([1, 1, 0], 2)]
    assert f == pytest.approx(np.mean(draws))
    with pytest.raises(ValueError, match="fixed portfolio"):
        replay.chronological_panels(batches, batches.iloc[:1])


def test_positive_model_value_and_replay_cash_agree_with_enumeration():
    q, r = .101, .50 / 9  # break-even 10 percent
    immediate, value, lend = replay.pilot_plan(q, r)
    assert immediate < 0 < immediate + value and lend
    events = [0, 0, 0, 1]
    future = [1, 0, 0, 0, 0]
    result = replay.episode(q, .101, np.mean(events), np.mean(future), r)
    cash = lambda y: r if y == 0 else -.50
    holdout = replay.HORIZON * np.mean([cash(y) for y in future])
    expected = np.mean([cash(y) + (holdout if y == 0 else 0) for y in events])
    assert result["model_net"] == pytest.approx(expected)
    assert result["model_pilot_margin"] == np.mean([cash(y) for y in events])
    assert result["model_gross"] == pytest.approx(holdout * .75)
    assert result["model_total"] == pytest.approx(result["no_pilot_fresh"] + result["model_net"])
    # A higher mature risk by follow-up eliminates both signal-contingent actions.
    updated = replay.episode(q, .20, np.mean(events), np.mean(future), r)
    assert updated["model_pilots"] and updated["model_gross"] == 0
    no_arrival = replay.episode(q, .101, .25, .20, r, arrival=0.)
    assert no_arrival["model_net"] == 0


def test_future_outcome_flips_cannot_change_either_decision_before_observation(monkeypatch):
    monkeypatch.setattr(replay, "LAST", replay.FIRST)
    q0 = replay.FIRST
    rows = []
    for q in range(1992 * 4, q0 + replay.MATURITY + 1):
        for region in replay.REGIONS:
            day = pd.Timestamp(q // 4, (q % 4) * 3 + 1, 10)
            rows.append(dict(region=region, quarter=q, day=day, n=100, events=4))
    daily = pd.DataFrame(rows)
    initial, _ = replay.replay(daily)
    daily.loc[daily.quarter >= q0, "events"] = 65
    changed, _ = replay.replay(daily)
    known = ["q_initial", "q_fresh", "break_even", "eligible", "model_pilots", "fresh_lend",
             "lend_after_no_event", "lend_after_event", "predicted_gross"]
    pd.testing.assert_frame_equal(initial[known], changed[known])
    assert not initial.future_pool_events.equals(changed.future_pool_events)
    daily.loc[daily.quarter == q0 - 1, "events"] = 80
    fresh, _ = replay.replay(daily)
    assert initial.q_initial.equals(fresh.q_initial)
    assert np.all(fresh.q_fresh > initial.q_fresh)


def test_calendar_block_sampling_respects_ratio_and_zero_eligibility():
    weights = np.array([0, 2, 0, 1, 3, 2, 0, 1] * 4)
    interval = replay.clustered_interval(1.25 * weights, weights, block=4)
    assert interval == pytest.approx((1.25, 1.25))
    assert all(np.isnan(replay.clustered_interval(weights, np.zeros_like(weights), block=4)))
    assert 0 < replay.sample_rate(pd.DataFrame({"n": [10] * 12, "events": [0] * 12})) < 1
    with pytest.raises(ValueError, match="incomplete"):
        replay.sample_rate(pd.DataFrame({"n": [10], "events": [0]}))
