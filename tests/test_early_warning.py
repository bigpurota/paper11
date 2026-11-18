import math

import pytest

from paper11.early_warning import curve_forecast, payment_forecast


def test_no_change_and_identifiable_below_both_boundary():
    fit = curve_forecast(.25, 10, 20, 10, 20, 10, 80)
    assert fit.source == "local" and fit.capture == .5
    assert fit.risk == pytest.approx(.25)
    # With L=.25, G=.15 there is strict evidence below both only under this early-event count.
    for events in range(81):
        forecast = curve_forecast(.25, 10, 20, 10, 20, events, 80)
        cutoff = .5 * ((80+10)*.15-10*.25)
        assert (forecast.risk < .15) == (events < cutoff)


def test_fallbacks_and_saturation():
    bank = curve_forecast(.2, 1, 2, 5, 10, 35, 40)
    assert bank.source == "bank" and bank.risk == 1
    assert curve_forecast(.2, 1, 2, 5, 10, 0, 0).risk == .2
    unsupported = curve_forecast(.2, 0, 6, 0, 12, 0, 150)
    assert unsupported.source == "none" and math.isnan(unsupported.capture)
    assert unsupported.risk == .2


def test_payment_marker_can_be_protective_or_adverse():
    # Reversing the marker definition gives exactly the same forecast.
    good = payment_forecast(.15, 100, 15, 60, 3, 90, 100)
    bad = payment_forecast(.15, 100, 15, 40, 12, 10, 100)
    assert good == pytest.approx(bad) and good < .15
    assert payment_forecast(.15, 20, 3, 0, 0, 4, 10) == .15
    with pytest.raises(ValueError):
        payment_forecast(.15, 20, 17, 12, 4, 4, 10)
    with pytest.raises(ValueError):
        curve_forecast(.15, 4, 3, 7, 20, 0, 10)
