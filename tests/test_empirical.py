from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from paper11.audit_design import randomized_audit
from paper11.data import PERIODS, Population, checksum
from paper11.empirical import cashflow, odds_shift, risk_lift, run_fold, select_policy


def test_profit_denominators_and_optimal_policy():
    realized = cashflow(np.array([0, 1, 1]), np.array([True, True, False]), .5)
    np.testing.assert_allclose(realized, [.1, -.45, 0])
    assert realized.mean() == pytest.approx((2/3) * realized[:2].mean())
    p = np.linspace(.01, .99, 100)
    obs = np.where(np.arange(100) % 2 == 1, np.nan, 0)
    chosen = select_policy(p, obs, np.zeros(100), np.full(100, .5), .5)
    assert all(rate == .5 and cutoff == p[49] for name, cutoff, rate in chosen)


def test_odds_and_lift_have_documented_direction_and_tie_rule():
    assert odds_shift(.2, 2) == pytest.approx(1/3)
    y = np.array([0,0,0,0,0,0,0,0,1,1])
    assert risk_lift(y,np.arange(10)) == pytest.approx(5)
    assert risk_lift(y,np.zeros(10)) == pytest.approx(1)


def test_census_audit_recovers_portfolio_truth():
    score = np.arange(100) / 100
    y = (np.arange(100) % 4 == 0).astype(float)
    obs = y.copy()
    obs[:12] = np.nan
    rows = list(randomized_audit(y, obs, score, np.full(100, .8), seed=8, budgets=(12,), draws=5))
    for row in rows:
        assert row["audit_rmse"] < 1e-14
        assert abs(row["prior_only_error"]) > .1


def test_flipping_every_hidden_development_label_keeps_decisions_fixed():
    rng = np.random.default_rng(33)
    X = rng.normal(size=(620, 4))
    y = (rng.random(620) < 1/(1+np.exp(-X[:,0]))).astype(int)
    p = .3 + .4 / (1 + np.exp(X[:,1]))
    a = rng.random(620) < p
    split = np.split(np.arange(620), [320, 400, 500])
    pop = Population(X, y, p, a, [split], [], {})
    corrupted = y.copy()
    dev = np.concatenate(split[:3])
    ids = dev[~a[dev]]
    corrupted[ids] = 1 - corrupted[ids]
    res, before, _ = run_fold(pop, split, 7)
    alt, after, _ = run_fold(replace(pop,y=corrupted), split, 7)
    for x, z in zip(before,after):
        np.testing.assert_array_equal(x,z)
    for name in ["training","policy","basl","calibration"]:
        pd.testing.assert_frame_equal(pd.DataFrame(res[name]),pd.DataFrame(alt[name]))
    np.testing.assert_array_equal([r["estimate"] for r in res["evaluation"]],
                                  [r["estimate"] for r in alt["evaluation"]])


def test_prosper_decision_calendar_leaves_a_full_outcome_window():
    dates = [(pd.Timestamp(a),pd.Timestamp(b)) for a,b in PERIODS]
    for (_,end), (start,_) in zip(dates,dates[1:]):
        assert end + pd.DateOffset(years=1) <= start
    assert dates[-1][1] + pd.DateOffset(years=1) <= pd.Timestamp("2014-03-11")
