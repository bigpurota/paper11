import numpy as np
import pandas as pd
import pytest

from paper11.pilot_signal_ml import (
    DISCLOSURE_OUTPUTS, ISSUE_OUTPUTS, branch_value, issue_features, score_panel,
)


def training_data():
    rows = []
    months = pd.period_range("2010-01", periods=82, freq="M")
    rng = np.random.default_rng(1103)
    for month in months:
        for country in ["A", "B"]:
            event = rng.binomial(1, .32)
            rows.append(dict(country=country, origin_month=str(month), q_initial=.2, prior_n=60,
                             pilot_principal=90., pilot_rate=.15, pilot_term=36.,
                             mean_prior_exposure=2000., mean_prior_count=20., q_fresh=.16,
                             peer_n=100, peer_defaults=12, pilot_default=event,
                             future_count=20, future_principal=2000.,
                             future_default_principal=100. if event == 0 else 700.,
                             structural_eligible=True, pilot_cash=50., future_cash=500.))
    return pd.DataFrame(rows)


def test_one_observation_crossing_the_action_threshold():
    blind, gain, bits, switch = branch_value(.25, .1, .4)
    assert blind == pytest.approx(.175)
    assert gain == pytest.approx(.03)
    assert switch == pytest.approx(.25)
    assert bits > 0
    _, gain, bits, switch = branch_value(.25, .20, .50)
    assert gain == pytest.approx(0.) and switch == 0 and bits > 0
    for pi in (0., .3, 1.):
        _, gain, bits, switch = branch_value(pi, .5, .5)
        assert (gain, bits, switch) == pytest.approx((0., 0., 0.))


def test_unknown_country_is_all_zero_and_missing_contract_stays_missing():
    test = training_data().iloc[[0]].assign(country="unseen", pilot_rate=np.nan)
    x = issue_features(test, ["A", "B"])
    assert np.array_equal(x[0, :2], np.zeros(2))
    assert np.isnan(x).sum() == 1


def test_timing_noninterference_and_conditional_branches():
    train = training_data()
    test = train.iloc[:2].copy().assign(origin_month="2022-10", pilot_default=[0., 1.])
    ref = score_panel(train, test)
    actual = np.where(ref.pilot_default == 1, ref.m_default, ref.m_repay)
    assert np.allclose(ref.m_seen, actual)
    assert np.allclose(ref.m_blind, ref.pi_disclosure*ref.m_default + (1-ref.pi_disclosure)*ref.m_repay)
    assert ref.pred_info_money.gt(0).all() and ref.pred_information_bits.gt(0).all()
    assert ref.m_default.gt(ref.m_repay).all()

    changed = test.assign(pilot_cash=-500., future_cash=9.e6, future_default_principal=1500.,
                          pilot_default=1. - test.pilot_default, peer_defaults=70, q_fresh=.4)
    alternative = score_panel(train.assign(pilot_cash=-9.e6), changed)
    pd.testing.assert_frame_equal(ref[ISSUE_OUTPUTS], alternative[ISSUE_OUTPUTS])
    unknown = score_panel(train, test.assign(pilot_default=np.nan))
    assert unknown.m_seen.isna().all() and unknown.seen_lend.isna().all()
    assert np.allclose(ref.m_blind, unknown.m_blind)


def test_unique_mature_episodes_and_minimum_training_support():
    train = training_data()
    test = train.iloc[:1].assign(origin_month="2022-10")
    with pytest.raises(ValueError, match="not yet mature"):
        score_panel(train.assign(origin_month="2022-03"), test)
    with pytest.raises(ValueError, match="duplicate training"):
        score_panel(pd.concat([train, train.iloc[:1]]), test)
    with pytest.raises(ValueError, match="after the model freeze"):
        score_panel(train, test.assign(origin_month="2022-01"))
    short = score_panel(train.iloc[:10], test)
    assert not short.model_scorable.any()
    assert short.train_n.eq(10).all()
    assert short[DISCLOSURE_OUTPUTS + ISSUE_OUTPUTS].isna().all().all()
