import numpy as np
import pytest

from paper11.frequency_diagnosis import error_components


def test_error_decomposition_matches_individually_weighted_binary_labels():
    # Two portfolio forecasts; within-book defaults account for 25% and 60% of principal.
    forecast = np.array([.30, .45])
    actual = np.array([.25, .60])
    frequency = np.array([.15, .55])
    row = error_components(forecast, actual, frequency)
    individual = (.75 * .30**2 + .25 * .70**2 + .40 * .45**2 + .60 * .55**2) / 2
    assert row["brier"] == pytest.approx(individual)
    assert row["within_book_component"] + row["squared_mean_error"] + row["centered_error_variance"] == pytest.approx(individual)
    gap = row["brier_gap_vs_issue"]
    assert row["squared_mean_error_gap"] + row["centered_error_variance_gap"] == pytest.approx(gap)
    assert row["adjustment_squared"] - row["adjustment_alignment"] == pytest.approx(gap)


def test_an_uninformative_constant_markup_loses_its_squared_size():
    actual = np.array([.04, .18, .38])
    base = np.array([.09, .18, .33])
    row = error_components(base + .10, actual, base)
    assert row["brier_gap_vs_issue"] == pytest.approx(.01)
    assert row["squared_mean_error_gap"] == pytest.approx(.01)
    assert row["centered_error_variance_gap"] == pytest.approx(0.)
