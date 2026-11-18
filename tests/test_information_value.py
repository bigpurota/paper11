"""Closed-form pilot economics against independent state mixtures and Bellman."""
from fractions import Fraction as F

import numpy as np
import pytest

from paper11.exploration import Model, solve
from paper11.information_value import Pilot, break_even, geometric_sum, pilot_value, terminal_evsi


def direct_table(p, pd, repay, default, m, delay, beta, reset, *, committed=False):
    """Enumerate pilot branch by latent state; forecast via its actual Markov matrix."""
    p = np.asarray(p)
    losses = np.asarray(pd)
    transition = (1-reset) * np.eye(len(p)) + reset*np.tile(p,(len(p),1))
    margin = (1-losses)*repay + losses*default
    likelihoods = np.array([losses, 1-losses])
    total = 0.
    full_batch_margin = np.zeros(len(p))
    for t in range(delay,m+1):
        conditional = np.linalg.matrix_power(transition,t) @ margin
        branch_value = sum(max(0., sum(p*likelihood*conditional)) for likelihood in likelihoods)
        total += beta**t * (branch_value - max(0.,p @ conditional))
        full_batch_margin += beta**t * conditional
    if committed:
        mixed = sum(max(0., sum(p*likelihood*full_batch_margin)) for likelihood in likelihoods)
        return mixed - max(0., p @ full_batch_margin)
    return total


def test_general_terminal_value_requires_a_change_of_optimal_decision_with_positive_probability():
    prior = [.2,.5,.3]
    # Perfect signal, an impossible report and three genuinely competing actions.
    signal = np.vstack([np.eye(3),np.zeros(3)])
    payoff = np.array([[2,0,-1], [0,1,0], [-2,0,4]])
    value = terminal_evsi(prior,signal,payoff)
    assert value == pytest.approx(.4+.5+1.2-.8)
    dominant = np.vstack([payoff,[5,5,5]])
    assert terminal_evsi(prior,signal,dominant) == pytest.approx(0.)
    assert terminal_evsi(prior,[[.5,.5,.5],[.5,.5,.5]],payoff) == pytest.approx(0.)
    with pytest.raises(ValueError,match="probabilities"):
        terminal_evsi(prior,[[.9,1,1]],payoff)


@pytest.mark.parametrize("reset", [0.,.13,.5,1.])
@pytest.mark.parametrize("lag,discount", [(1,1.),(2,.91),(4,.3)])
def test_formulas_agree_with_direct_multi_state_markov_and_decision_enumeration(reset,lag,discount):
    states = [.01,.22,.74,.99]
    weights = np.array([.15,.6,.2,.05])
    d = np.average(states,weights=weights)
    var = np.average((states-d)**2, weights=weights)
    for good,bad in [(.12,-.5),(.22,-.27),(.32,-.18)]:
        pilot = Pilot(d,var,good,bad)
        for m in [0,2,5,13]:
            predicted = pilot_value(pilot,m,reset=reset,delay=lag,discount=discount)
            direct = direct_table(weights,states,good,bad,m,lag,discount,reset)
            assert predicted == pytest.approx(direct,abs=1e-13)
            committed = pilot_value(pilot,m,reset=reset,delay=lag,discount=discount,fixed_rule=True)
            frozen = direct_table(weights,states,good,bad,m,lag,discount,reset,committed=True)
            assert committed == pytest.approx(frozen,abs=1e-13)
            assert committed <= direct+1e-13


def test_distinct_distributions_of_pd_with_same_mean_and_variance_agree_after_one_label():
    # Three-point uniform-with-center and two-point symmetric priors share moments.
    priors = [(np.array([.125,.75,.125]),np.array([0.,.5,1.])),
              (np.array([.5,.5]),np.array([.25,.75]))]
    values = [direct_table(w,pd,.55,-.45,7,1,.94,.11) for w,pd in priors]
    assert values[0] > 0 and values[0] == pytest.approx(values[1],abs=1e-13)
    assert values[0] == pytest.approx(pilot_value(Pilot(.5,.0625,.55,-.45),7,discount=.94,reset=.11))


def test_break_even_strict_at_tie_and_correct_for_delays_and_infinite_ceiling():
    # Mean margin 0, c=1 and variance 1/16. One subsequent signal-directed loan is worth 1/16.
    pilot = Pilot(.5,1/16,.5,-.5)
    assert break_even(pilot,fee=1/8,delay=1) == 3
    assert break_even(pilot,fee=1/8,delay=3) == 5
    assert break_even(pilot,fee=1/16,discount=.5) is None  # discounted infinite sum exactly equals fee
    assert break_even(pilot,fee=1/20,discount=.5) == 3
    assert geometric_sum(.5,1,None) == 1 and geometric_sum(1.,1,None) == np.inf
    assert pilot_value(pilot,None,reset=0.,discount=0.) == 0
    assert break_even(pilot,reset=1.) is None
    assert break_even(Pilot(.1,0.,.2,-.1),fee=.01) == 0


def test_canonical_pilot_ceiling_and_opposite_funding_decision_from_fully_adaptive_model():
    loan = Model()
    pilot = Pilot.from_model(loan)
    assert pilot_value(pilot,1) == pytest.approx(float(F(877,160000)))
    assert break_even(pilot) == 3
    assert pilot_value(pilot,None,reset=.10) == pytest.approx(.0070888996875)
    assert break_even(pilot,reset=.10) is None
    assert solve(Model(reset=.10),3)[3].value(.55) > .0025
    assert pilot_value(pilot,10,reset=.10,fixed_rule=True) == 0
    assert pilot_value(pilot,10,reset=.10) > 0


def test_degenerate_state_and_invalid_timing_or_coupling_parameters():
    assert pilot_value(Pilot(0.,0.),None) == 0.
    assert pilot_value(Pilot(1.,0.),None) == 0.
    with pytest.raises(ValueError,match="variance"):
        Pilot(.2,.5)
    with pytest.raises(ValueError,match="delay|signal"):
        pilot_value(Pilot(.2,.1),2,delay=0)
    with pytest.raises(ValueError,match="contractual"):
        pilot_value(Pilot(.2,.1),None,fixed_rule=True)


def test_public_update_removes_value_of_a_duplicate_pilot_and_can_complement_an_uninformative_one():
    from paper11.information_value import conditional_terminal_evsi

    prior = [.5,.5]
    payoff = np.eye(2)  # choose the correct binary state
    duplicate = np.zeros((2,2,2))
    duplicate[0,0,0] = duplicate[1,1,1] = 1.  # W=Y=state
    assert terminal_evsi(prior,duplicate.sum(axis=0),payoff) == pytest.approx(.5)
    assert conditional_terminal_evsi(prior,duplicate,payoff) == pytest.approx(0.)
    xor = np.zeros_like(duplicate)
    for state in (0,1):
        for public in (0,1):
            xor[public,public ^ state,state] = .5
    assert terminal_evsi(prior,xor.sum(axis=0),payoff) == pytest.approx(0.)
    assert terminal_evsi(prior,xor.sum(axis=1),payoff) == pytest.approx(0.)
    assert conditional_terminal_evsi(prior,xor,payoff) == pytest.approx(.5)
