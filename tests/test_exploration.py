"""Independent checks of sequential funding with selective repayment outcomes."""
from fractions import Fraction as F
from functools import cache

import numpy as np
import pytest

from paper11.exploration import Model, choices, posterior, solve, upper_envelope


def rational_tree(horizon, belief, reset, *, p_good=F(1,20), p_bad=F(2,5)):
    """Direct public-history tree using *joint masses*, no posterior or envelope."""
    prior = F(11,20)
    def transition(good, bad):
        redraw = reset * (good + bad)
        return (1-reset)*good + redraw*prior, (1-reset)*bad + redraw*(1-prior)

    @cache
    def node(h, good, bad):
        if h == 0:
            return F()
        defaults = good*p_good, bad*p_bad
        repayments = good-defaults[0], bad-defaults[1]
        present = F(1,10)*sum(repayments) - F(9,20)*sum(defaults)
        fund = present + node(h-1,*transition(*defaults)) + node(h-1,*transition(*repayments))
        wait = node(h-1,*transition(good,bad))
        return max(F(), fund, wait)
    return node(horizon, belief, 1-belief)


@pytest.mark.parametrize("hazard", [F(0), F(1,10), F(1,4), F(1,2), F(1)])
def test_piecewise_exact_bellman_matches_independent_rational_tree(hazard):
    model = Model(reset=float(hazard))
    values = solve(model, 5)
    for h, value in enumerate(values):
        for b in [F(0), F(2,13), F(11,20), F(7,11), F(37,41), F(1)]:
            expected = rational_tree(h, b, hazard)
            assert value.value(float(b)) == pytest.approx(float(expected), abs=2e-13)
            if h:
                by_action = choices(model, values[h-1], float(b))["adaptive_value"]
                assert by_action == pytest.approx(float(expected), abs=2e-13)


def test_first_loss_pays_only_with_three_applicants_and_repayments_are_seen_in_order():
    m = Model()
    v = solve(m, 3)
    cases = [choices(m, env, m.prior_good) for env in v[:-1]]
    assert [c["first_action"] for c in cases] == ["stop", "stop", "fund"]
    assert cases[0]["immediate_margin"] == pytest.approx(float(F(-113,8000)))
    assert cases[1]["fund_value"] == pytest.approx(float(F(-1383,160000)))
    assert cases[2]["fund_value"] == pytest.approx(float(F(25291,3200000)))
    assert cases[2]["first_signal_value"] + cases[2]["immediate_margin"] == pytest.approx(cases[2]["fund_value"])
    pd, after_default = posterior(m.prior_good, m.default)
    pr, after_repay = posterior(m.prior_good, 1-m.default)
    assert pd + pr == pytest.approx(1.)
    assert [after_default, after_repay] == pytest.approx([float(F(11,83)),float(F(209,317))])
    assert choices(m, v[1], after_default)["first_action"] == "stop"
    assert choices(m, v[1], after_repay)["first_action"] == "fund"


def test_complete_redraw_removes_feedback_value_and_identical_regimes_remove_it_too():
    for model in [Model(reset=1), Model(default_good=.22, default_bad=.22),
                  Model(prior_good=.8, reset=1), Model(default_good=.1, default_bad=.1)]:
        values = solve(model, 10)
        b = model.prior_good
        per_period = np.dot([b,1-b], model.margin)
        for h in (1,2,6,10):
            c = choices(model, values[h-1], b)
            assert c["first_signal_value"] == pytest.approx(0, abs=1e-13)
            assert c["adaptive_value"] == pytest.approx(h*max(0.,per_period), abs=1e-13)


def test_hull_honors_dominated_parallel_lines_and_endpoint_ties():
    payoffs = np.array([[1,0], [0,.5], [-1,-2], [0,0], [0,.5], [.5,.5], [-4,1.0]])
    envelope = upper_envelope(payoffs)
    for b in np.linspace(0,1,51):
        assert envelope.value(b) == pytest.approx(np.max(payoffs @ [b,1-b]))


def test_perfect_signal_and_impossible_events_are_handled_without_division_errors():
    m = Model(default_good=0.,default_bad=1., reset=.25)
    values = solve(m, 5)
    for b in [F(0), F(1,2), F(1)]:
        expected = rational_tree(5,b,F(1,4),p_good=F(0),p_bad=F(1))
        assert values[-1].value(float(b)) == pytest.approx(float(expected))
    for pd in (0.,1.):
        model = Model(default_good=pd,default_bad=pd)
        assert solve(model,3)[3].value(.6) == pytest.approx(.3 if pd == 0 else 0.)


def test_wait_after_a_default_can_have_positive_value_without_seeing_a_repayment():
    m = Model(reset=.25)
    v = solve(m, 16)
    _, post = posterior(m.prior_good, m.default)
    c = choices(m, v[14], m.predict(post))
    assert c["first_action"] == "wait"
    assert c["wait_value"] > c["fund_value"] and c["wait_value"] > 0.


def test_input_validation_and_zero_horizon():
    assert solve(Model(),0)[0].value(.5) == 0.
    with pytest.raises(ValueError, match="horizon"):
        solve(Model(),-1)
    with pytest.raises(ValueError, match="default"):
        Model(default_good=.7,default_bad=.5)
    with pytest.raises(ValueError, match="probability"):
        Model(reset=1.1)
