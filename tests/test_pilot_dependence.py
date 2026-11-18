import numpy as np
import pytest

from paper11.pilot_dependence import joint_default_limits, maximum_signal_value, signal_value


def test_formula_matches_direct_enumeration_of_all_four_contingent_decisions():
    for p in np.linspace(0, 1, 9):
        for q in np.linspace(0, 1, 11):
            bounds = joint_default_limits(p, q)
            upper = maximum_signal_value(p, q, .1, -.45)
            for t in np.linspace(*bounds, 7):
                # Rows: pilot repays or defaults. Columns: next repays or defaults.
                joint = np.array([[1-p-q+t, q-t], [p-t, t]])
                by_signal = joint @ [.1, -.45]
                informed = max(a*by_signal[0] + b*by_signal[1] for a in [0, 1] for b in [0, 1])
                expected = informed - max(0., by_signal.sum())
                assert signal_value(p, q, t, .1, -.45) == pytest.approx(expected, abs=1e-14)
                assert expected <= upper + 1e-14
            assert signal_value(p, q, p*q, .1, -.45) == pytest.approx(0., abs=1e-14)


def test_even_reversed_dependence_cannot_pay_for_an_expensive_pilot():
    assert signal_value(.02, .30, 0., .1, -.45) == pytest.approx(.002)
    assert signal_value(.02, .30, .02, .1, -.45) == pytest.approx(0.)
    assert 4 * maximum_signal_value(.02, .30, .1, -.45) < .01


def test_two_regime_example_from_a_joint_probability_without_a_fitted_state_model():
    p = .55*.05 + .45*.40
    joint = .55*.05**2 + .45*.40**2
    assert signal_value(p, p, joint, .1, -.45) == pytest.approx(.00548125)
    assert 2*.00548125 < .014125 < 3*.00548125
    with pytest.raises(ValueError):
        signal_value(.2, .3, .25, .1, -.45)
