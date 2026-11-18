import numpy as np
import pandas as pd
import pytest

from paper11.pilot_targeting import score_panel, weighted_auc


def test_weighted_auc_matches_explicit_ties_and_repeated_episodes():
    score = np.array([.1, .1, .2, .3])
    flag = np.array([0, 1, 0, 1], dtype=bool)
    weights = np.array([3, 2, 1, 3])
    pos, neg = np.repeat(score[flag], weights[flag]), np.repeat(score[~flag], weights[~flag])
    pairs = [float(a > b) + .5 * (a == b) for a in pos for b in neg]
    assert weighted_auc(score, flag, weights) == pytest.approx(np.mean(pairs))
    assert np.isnan(weighted_auc(score, np.ones(4, dtype=bool), weights))


def test_targeting_uses_every_eligible_opportunity_and_preserves_empty_quarters():
    panel = pd.DataFrame(dict(quarter=["2001Q1","2001Q1","2001Q3","2001Q4"],
                              eligible=[1,1,0,1], score=[1.,-3.,7.,1.],
                              selected=[1,0,0,1], net=[2.,4.,100.,-1.], strict=[1,0,0,0]))
    table = pd.DataFrame(score_panel(panel, draws=30)).set_index("metric")
    assert table.loc["rule_gain","estimate"] == pytest.approx(1/3)
    assert table.loc["pilot_all_gain","estimate"] == pytest.approx(5/3)
    assert table.loc["targeting_difference","estimate"] == pytest.approx(.5-4)
    assert table.loc["auc_positive","estimate"] == pytest.approx(.25)
    assert table.quarters.eq(4).all() and table.strict_selected.eq(1).all()
    panel["eligible"] = panel["selected"] = False
    assert pd.DataFrame(score_panel(panel, draws=3)).estimate.isna().all()


def test_analog_public_forecast_uses_only_mature_updates_and_ignores_payoffs():
    from paper11.pilot_targeting import public_risk_forecast
    frame = pd.DataFrame(dict(origin=np.arange(14), disclosure=np.arange(14)+3,
                              initial=.19, fresh=np.tile([.12, .27], 7), strength=20.,
                              repay=.10, default=-.45, capacity=25, score=.123, net=17.))
    forecast, ages = public_risk_forecast(frame)
    assert np.all(ages[:10] < 8) and np.all(forecast[:10] == .123)
    assert ages[10] == 8 and forecast[10] != .123
    frame.loc[frame.disclosure > 10, "fresh"] = .9
    frame["net"] *= -1
    other, _ = public_risk_forecast(frame)
    np.testing.assert_allclose(forecast[:11], other[:11])
