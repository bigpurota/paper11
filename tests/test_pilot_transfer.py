from itertools import combinations

import numpy as np
import pandas as pd
import pytest

from paper11 import pilot_transfer as t


def test_prefixed_calibration_price_and_read_filter(tmp_path):
    assert t.base.mean_margin(27 / 9398, t.REFERENCE_INTEREST) == pytest.approx(0.)
    cols = ["AsOfDate", "ProjectState", "ApprovalDate", "FirstDisbursementDate", "ChargeOffDate"]
    test = [["2026-09-30", "FL", "1998-01-01", "1999-01-01", charge] for charge in
            (None, "1998-02-01", "2002-01-01", "2002-01-02")]
    p = tmp_path/"ledger.csv"
    pd.DataFrame(test, columns=cols).assign(GrossApproval=100, GrossChargeOffAmount=55).to_csv(p, index=False)
    loans, counts = t.read_loans([p])
    assert len(loans) == 3
    assert counts["chargeoff_before_disbursement"] == 1
    assert loans.event.tolist() == [False, True, False]
    assert loans.chargeoff_fraction.tolist() == [0., .55, 0.]


def test_exact_boundary_draw_and_actual_loss_recovery(monkeypatch):
    monkeypatch.setattr(t.base, "HORIZON", 3)
    days = pd.DataFrame({"day": pd.to_datetime(["2000-05-01", "2000-05-02"]),
                         "n": [1, 4], "events": [1, 2]})
    ks, weights = t.future_counts(days)
    choices = [1 + sum(x) for x in combinations([0, 0, 1, 1], 2)]
    np.testing.assert_allclose(weights, [choices.count(k)/len(choices) for k in ks])
    plan = {"fresh_lend": True, "lend_after_no_event": True, "lend_after_event": False}
    row = t.evaluate_paths(plan, .1, .5, .25, (ks, weights), 1, 2)
    assert row["prob_changed"] == pytest.approx(.5 * .25)
    assert row["prob_loss_recovered"] == pytest.approx(.5 * .25 * (5 / 6))
    assert row["seed_flip"] and row["seed_loss_recovered"]
    assert row["seed_pilot_cash"] == pytest.approx(-.5)
    assert row["seed_gross"] == pytest.approx(.9)
    assert row["seed_net"] == pytest.approx(.4)
    assert not t.evaluate_paths(plan, .1, .5, .25, (ks, weights), None, 2)["seed_loss_recovered"]


def test_fixed_draw_indices_independent_of_outcomes(monkeypatch):
    monkeypatch.setattr(t.base, "HORIZON", 3)
    panel = pd.DataFrame({"day": pd.to_datetime(["2000-01-05"] * 4 + ["2000-02-02"] * 3 + ["2000-03-01"] * 8),
                          "event": [0, 1, 1, 0, 0] * 3})
    flipped = panel.assign(event=1-panel.event)
    for ri in range(len(t.REGIONS)):
        orig, future = t.draw_panel(panel, panel, 8000, ri)
        other, later = t.draw_panel(flipped, flipped, 8000, ri)
        assert orig.event + other.event == 1 and future.event.sum() + later.event.sum() == 3


def test_mutating_both_holdouts_leaves_predicted_and_conditional_actions_fixed(monkeypatch):
    monkeypatch.setattr(t.base, "LAST", t.base.FIRST)
    q0 = t.base.FIRST
    rows = []
    for q in range(1992 * 4, q0 + t.base.MATURITY + 1):
        for region in t.REGIONS:
            month = 1 + (q % 4) * 3
            for i in range(30):
                rows.append((pd.Timestamp(q // 4, month + i%3, 8), region, q, i % 10 == 0))
    loans = pd.DataFrame(rows, columns=["day", "region", "quarter", "event"])
    loans["chargeoff_fraction"] = .55
    baseline, cal = t.replay(loans)
    target = loans.quarter.isin([q0, q0 + t.base.MATURITY])
    loans.loc[target, "event"] = ~loans.loc[target, "event"]
    perturbed, later_cal = t.replay(loans)
    cols = ["q_initial", "q_fresh", "interest", "predicted_net", "eligible", "model_pilots",
            "fresh_lend", "lend_after_event", "lend_after_no_event"]
    pd.testing.assert_frame_equal(baseline[cols], perturbed[cols])
    assert cal == later_cal and not baseline.seed_next_events.equals(perturbed.seed_next_events)


def test_reported_severity_keeps_realized_losses_and_missingness():
    plan = {"fresh_lend": True, "lend_after_no_event": True, "lend_after_event": False}
    pilot = pd.Series({"event": True, "chargeoff_fraction": .6})
    future = pd.DataFrame({"event": [True, True, False], "chargeoff_fraction": [.4, .5, 0.]})
    result = t.recorded_margin(.1, plan, pilot, future)
    assert result["seed_recorded_pilot_cash"] == pytest.approx(-.6)
    assert result["seed_recorded_gross"] == pytest.approx(.8)
    assert result["seed_recorded_net"] == pytest.approx(.2)
    future.loc[0, "chargeoff_fraction"] = np.nan
    assert np.isnan(t.recorded_margin(.1, plan, pilot, future)["seed_recorded_net"])
    assert t.recorded_margin(.1, plan, None, future)["seed_recorded_net"] == 0


def test_witness_respects_first_batches_and_fixed_future():
    pilots = pd.DataFrame({"day": pd.to_datetime(["2002-04-30", "2002-04-30", "2002-04-30",
                                                   "2002-05-17", "2002-06-07"]),
                           "event": [True, False, True, False, False],
                           "chargeoff_fraction": [.85, 0, .2, 0, 0]})
    future = pd.DataFrame({"event": [True, True, False], "chargeoff_fraction": [.4, .5, 0.]})
    plan = {"fresh_lend": True, "lend_after_no_event": True, "lend_after_event": False}
    w = t.chargeoff_witness(pilots, future, 4*2002+1, plan, .1)
    assert w["fixed_future_first_failed_pilot_cash"] == -.85
    assert w["fixed_future_prob_strict"] == pytest.approx(2/9)
    assert w["fixed_future_prob_recorded_strict"] == pytest.approx(1/9)
    assert w["fixed_future_recorded_gross_on_failure"] == pytest.approx(.8)
