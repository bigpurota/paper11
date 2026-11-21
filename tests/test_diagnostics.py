import numpy as np
import pytest

from paper11.diagnostics import psi, recovery


def test_recovery_is_zero_for_the_baseline_and_one_for_full_information():
    assert recovery(.08, .08, .07) == 0
    assert recovery(.08, .07, .07) == pytest.approx(1)
    assert recovery(.08, .09, .07) == pytest.approx(-1)  # a method can widen the gap


def test_psi_is_zero_for_identical_samples_and_grows_with_a_shift():
    rng = np.random.default_rng(0)
    base = rng.random(20_000)
    assert psi(base, base) == 0
    assert psi(base, rng.random(20_000)) < .01
    assert psi(base, base * .5) > psi(base, base * .9) > 0


def test_psi_matches_the_lecture_formula_on_two_bins():
    development = np.r_[np.zeros(50), np.ones(50)]  # median edge splits the two bins 50/50
    current = np.r_[np.zeros(20), np.ones(80)]
    expected = (.2 - .5) * np.log(.2 / .5) + (.8 - .5) * np.log(.8 / .5)
    assert psi(development, current, bins=2) == pytest.approx(expected)


def test_psi_stays_finite_when_a_bin_empties():
    development = np.linspace(0, 1, 1000)
    assert np.isfinite(psi(development, np.full(100, .99)))
