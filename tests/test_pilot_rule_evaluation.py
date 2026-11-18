import numpy as np
import pandas as pd
import pytest
from scipy.integrate import quad
from scipy.stats import beta, binom

from paper11.pilot_rule import predict, public_risks
from paper11.pilot_rule_evaluation import forecast_inputs, ranking, summarize


def test_original_risk_below_eight_distinct_disclosed_dates_and_center_after_eight():
    old = np.full(8, .25)
    new = np.linspace(.1, .4, 8)
    np.testing.assert_allclose(public_risks(.2, old, new, [0,1,2,3,4,5,6,6]), [.2])
    forecasts = public_risks(.2, old, new, np.arange(8))
    assert forecasts.mean() == pytest.approx(.2)
    assert np.all(np.diff(forecasts) > 0)


def test_frozen_case_score_by_explicit_conditional_integration_and_currency_scale():
    q, amount = .18, 26.
    # With three equal 100-euro follow-ups the bank's switch pays for a failed
    # pilot when at least one of those three defaults. A default adds one to alpha.
    n = np.full(12, 3)
    volume = np.full(12, 300.)
    f = predict(q, amount, n, volume)
    posterior = beta(20*q+1, 20*(1-q))
    cond = quad(lambda theta: binom.sf(0, 3, theta)*posterior.pdf(theta), 0, 1)[0]
    assert f.strict_probability == pytest.approx(q*cond)
    expected_rate = ((1-q)*max(0., .1-.55*(20*q/21)) +
                     q*max(0., .1-.55*((20*q+1)/21)) - max(0., .1-.55*q))
    assert f.net_money == pytest.approx(amount*(.1-.55*q)+300*expected_rate)
    scaled = predict(q, 20*amount, n, 20*volume)
    assert scaled.strict_probability == pytest.approx(f.strict_probability)
    assert scaled.net_money == pytest.approx(20*f.net_money)
    assert scaled.selected == f.selected == False
    assert predict(q, amount, np.zeros(12), np.zeros(12)).strict_probability == 0


def test_origin_inputs_ignore_future_outcomes_and_amounts_and_fill_empty_months():
    origin = pd.Period("2024-02", "M")
    history = pd.DataFrame(dict(origin=[1,2], disclosure=[origin.ordinal, origin.ordinal+1],
                                initial=[.2,.9], fresh=[.17,.99]))
    samples = pd.DataFrame({"size":[3,5,25,25], "sum":[30,50,9e5,1e6]},
                           index=[origin-12, origin-1, origin, origin+1])
    counts, volumes, old, fresh, dates = forecast_inputs(history, samples, origin)
    assert list(counts) == [3]+[0]*10+[5]
    assert list(volumes) == [30]+[0]*10+[50]
    assert old.tolist()==[.2] and fresh.tolist()==[.17] and dates.tolist()==[1]


def test_ranking_counts_ties_and_reports_unidentified_single_class():
    weights = np.array([2.,1.,1.])
    scores = np.array([.3,.3,.1])
    events = np.array([False,True,False])
    auc, ap = ranking(scores,events,weights)
    assert auc == pytest.approx(2/3)
    assert ap == pytest.approx(1/3)
    assert np.isnan(ranking(scores, np.ones(3,dtype=bool),weights)).all()


def test_paired_policy_cash_and_strict_events_preserve_unknown_selected_positions():
    panel = pd.DataFrame(dict(origin_month=["2020-01","2020-04","2020-07","2020-10"],
                             eligible=True, selected=[1,1,0,0], baseline_selected=[1,0,1,0],
                             strict_probability=[.3,.2,.1,.05], action_changed=[True,True,False,pd.NA],
                             net_cash=[np.nan,30.,-10.,np.nan], pilot_cash=[-1.,-1.,-10.,3.],
                             net_scenario=[0.,0.,0.,0.], pilot_scenario=[1.,-1.,-1.,1.])).astype(
                                 {"selected":bool,"baseline_selected":bool})
    answer = summarize("test","known",panel)
    assert answer["eligible"]==4 and answer["new_cash_known"]==3
    assert answer["new_minus_baseline_cash_known"]==4  # same unknown pilot cancels
    assert answer["new_minus_baseline_cash"]==10
    assert answer["cash_event_known"]==3  # a positive pilot cannot be a strict recovery
    assert answer["new_cash_tp"]==1 and answer["new_cash_fp"]==0
    assert answer["new_cash_draws"]==0 and np.isnan(answer["new_cash_low"])
    assert not answer["cash_gain_supported"]


def test_empty_prespecified_calendar_has_denominator_zero_and_undefined_performance():
    columns = ["origin_month","eligible","selected","baseline_selected","action_changed","strict_probability",
               "net_cash","net_scenario","pilot_cash","pilot_scenario"]
    empty = pd.DataFrame(columns=columns).astype({c:bool for c in ["eligible","selected","baseline_selected"]})
    out = summarize("holdout","primary",empty, calendar=("2024-06","2024-09"))
    assert out["scheduled"]==0 and out["eligible"]==0 and out["quarters"]==2
    assert np.isnan(out["new_cash"]) and np.isnan(out["auc_cash"])
    assert out["new_cash_draws"]==0 and not out["cash_gain_supported"]


def test_within_segment_ranking_excludes_easy_cross_group_controls():
    from paper11.pilot_rule_evaluation import within_segment_auc
    groups = pd.DataFrame(dict(country=["EE","EE","FI","FI"], customer=["new"]*4))
    scores = np.array([.7,.9,0.,0.])
    events = np.array([1.,0.,0.,0.])
    assert ranking(scores, events.astype(bool), np.ones(4))[0] == pytest.approx(2/3)
    assert within_segment_auc(groups, scores, events) == (0., 1, 1)


def test_all_missing_selected_margins_do_not_become_zero_or_confirm_gain():
    panel = pd.DataFrame(dict(origin_month=["2000-01","2002-04"], eligible=True, selected=True,
                              baseline_selected=False, strict_probability=.1, action_changed=pd.NA,
                              net_cash=np.nan, pilot_cash=np.nan, net_scenario=np.nan, pilot_scenario=np.nan))
    result = summarize("prosper","prosper",panel,calendar=("1999-01","2002-12"))
    assert result["quarters"] == 16 and result["occupied_quarters"] == 2
    assert result["eligible"] == result["selected"] == 2
    assert result["new_cash_known"] == result["cash_event_known"] == result["new_cash_draws"] == 0
    assert np.isnan(result["new_cash"]) and np.isnan(result["auc_cash"])
    assert result["baseline_cash"] == 0 and result["currency"] == "USD"
    assert not result["cash_gain_supported"] and not result["cash_ranking_supported"]
