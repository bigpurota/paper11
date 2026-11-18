import numpy as np
import pandas as pd
import pytest

from paper11.frequency_model import (
    CUTOFF, ISSUE_FIELDS, Slopes, bounded_branches, conditional_forecasts,
    fit_slopes, ridge_slope, score_anchored, score_experiment,
)


def example_data():
    rng = np.random.default_rng(1411)
    n = 140
    q = rng.uniform(.1, .45, n)
    u = rng.uniform(.05, .55, n)
    peers = rng.integers(0, 100, n)
    events = rng.binomial(peers, u)
    y = rng.binomial(1, u)
    target = np.clip(.4 * q + .6 * u + .2 * (y - u), 0., 1.)
    return pd.DataFrame(dict(
        sample="train", pilot_rank=1, country=np.where(np.arange(n) % 2, "B", "A"),
        origin_month=pd.period_range("2009-03", periods=n, freq="M").astype(str),
        q_initial=q, q_fresh=u, prior_n=100, peer_n=peers, peer_defaults=events,
        pilot_default=y, future_count=25, future_principal=10000.,
        future_default_principal=target * 10000., pilot_principal=200., mean_prior_exposure=20000.,
        mean_prior_count=23., pilot_rate=12., pilot_term=24., structural_eligible=True))


def test_ridge_minimizes_penalized_sum_and_no_update_returns_frequency():
    x = np.array([.2, -.1, .4])
    y = np.array([.08, .27, .10])
    w = ridge_slope(x, y)
    assert 2*x @ (w*x - y) + 2*w == pytest.approx(0.)
    q = np.array([.1, .25])
    p, c, pi, g, r, d = conditional_forecasts(q, q, 0., 0., Slopes(.38, .93, 0.))
    for component in (p, c, pi, r, d):
        assert component == pytest.approx(q)
    assert np.array_equal(g, [0., 0.])


def test_branch_bounds_and_tower_property_for_both_directions_and_boundary_risks():
    c, pi = np.meshgrid([0., .01, .45, .99, 1.], [0., .01, .38, .99, 1.])
    for slope in (-2., -.07, 0., .07, 2.):
        effective, repay, default = bounded_branches(c, pi, slope)
        assert ((repay >= 0) & (repay <= 1) & (default >= 0) & (default <= 1)).all()
        np.testing.assert_allclose((1-pi)*repay + pi*default, c, atol=1e-15)
        np.testing.assert_allclose(default - repay, effective, atol=1e-15)
        assert np.all(np.abs(effective) <= abs(slope) + 1e-15)


def test_peer_absence_and_unknown_pilot_are_distinct():
    train = example_data()
    test = train.iloc[:4].copy().assign(country="new", pilot_default=np.nan)
    test.iloc[0, test.columns.get_loc("peer_n")] = 0
    test.iloc[0, test.columns.get_loc("peer_defaults")] = 0
    parameters = Slopes(.3, .7, .22)
    scored = score_anchored(train, test, "peers", parameters)
    assert scored.m_seen.isna().all() and scored.seen_lend.isna().all()
    assert scored.m_blind.iloc[0] == scored.m_public.iloc[0]
    assert scored.analog_pooled.all() and scored.analog_n.eq(len(train)).all()
    hidden = score_anchored(train, test, "no_peers", parameters)
    np.testing.assert_array_equal(hidden.m_public, hidden.m_blind)
    changed = test.assign(peer_n=20, peer_defaults=20, pilot_default=1, q_fresh=.03,
                          future_default_principal=10000., future_cash=-1e9, pilot_cash=1e9)
    alt = score_anchored(train, changed, "peers", parameters)
    pd.testing.assert_frame_equal(scored[ISSUE_FIELDS], alt[ISSUE_FIELDS])


def test_expected_value_when_the_pilot_can_and_cannot_change_a_choice():
    train = example_data().assign(q_initial=.22, q_fresh=.22, peer_n=0, peer_defaults=0)
    test = train.iloc[:1].assign(pilot_default=1)
    exposed = score_anchored(train, test, "peers", Slopes(0., 0., .5))
    row = exposed.iloc[0]
    payoff_repaid = .10 - .55*(.22 - .5*.22)
    assert row.pred_info_money == pytest.approx(20000.*.78*payoff_repaid)
    assert row.pred_direct_money == pytest.approx(200.*(.10-.55*.22))
    assert row.ml_selected and row.pred_switch_probability == pytest.approx(.78)
    protected = score_anchored(train, test, "peers", Slopes(0., 0., .002)).iloc[0]
    assert protected.pred_information_bits > 0
    assert protected.pred_info_money == 0. and not protected.ml_selected


def test_only_rank_one_mature_outcomes_fit_and_hgb_controls_align_between_ranks():
    train = example_data()
    older = train.iloc[:100]
    test = pd.concat([train.iloc[:3].assign(sample="test", origin_month=str(CUTOFF+i))
                      for i in range(2)], ignore_index=True).drop_duplicates(["country", "origin_month"])
    second = test.assign(pilot_rank=26, pilot_default=1-test.pilot_default)
    panel = pd.concat([train, test, second], ignore_index=True)
    forecasts, coeff = score_experiment(panel, older)
    assert len(forecasts) == len(test)*4 and coeff.train_n.eq(len(train)).all()
    assert coeff.query("feed == 'no_peers'").peer_slope.iloc[0] == 0.
    assert coeff.refresh_slope.between(0., 1.).all() and coeff.peer_slope.between(0., 1.).all()
    assert forecasts[["hgb_seen", "hgb_2022_seen"]].notna().all().all()
    c = forecasts.pivot(index=["feed", "country", "origin_month"], columns="pilot_rank", values="m_blind")
    np.testing.assert_array_equal(c[1], c[26])
    for feed, rows in forecasts.groupby("feed"):
        assert rows.m_seen.to_numpy() == pytest.approx(np.where(rows.pilot_default, rows.m_default, rows.m_repay))
    with pytest.raises(ValueError, match="mature"):
        score_experiment(panel.assign(origin_month=str(CUTOFF)), older)
    with pytest.raises(ValueError, match="training unit"):
        score_experiment(pd.concat([panel, train.iloc[:1].assign(pilot_rank=26)]), older)
    no_moves = example_data().assign(q_initial=.2, q_fresh=.2, peer_n=5., peer_defaults=1.)
    small = fit_slopes(no_moves, "peers")
    assert small.refresh == small.peers == 0.
