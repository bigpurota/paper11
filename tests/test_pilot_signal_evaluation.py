import numpy as np
import pandas as pd
import pytest

from paper11.pilot_signal_evaluation import brier, estimates, policy_contrasts


def test_fractional_loss_equals_exposure_weighted_individual_loss():
    obs, amounts = np.array([1, 0, 1]), np.array([50, 200, 100])
    assert brier(np.average(obs, weights=amounts), .2) == pytest.approx(np.average((obs-.2)**2, weights=amounts))


def test_changed_action_zero_volume_and_missing_observation():
    data = pd.DataFrame(dict(structural_eligible=[True]*3, ml_selected=[True, True, False],
                             structural_selected=[False, True, False], blind_lend=[True]*3,
                             seen_lend=[False, np.nan, np.nan], pilot_default=[1, np.nan, np.nan],
                             future_count=[25, 0, 25], pilot_cash=[-15., -4., np.nan],
                             future_cash=[-100., np.nan, 20.], pilot_scenario=[-45., np.nan, np.nan],
                             future_scenario=[-80., 0., 40.]))
    p = policy_contrasts(data)
    assert p.new_cash.tolist() == [85., -4., 0.]
    assert p.new_minus_old_cash.tolist() == [85., 0., 0.]
    assert p.strict_new_cash.tolist() == [1., 0., 0.]
    assert pd.isna(p.forced_cash.iloc[2])


def test_calendar_blocks_cannot_make_an_interval_out_of_short_history():
    x = pd.DataFrame({"paired": [1., np.nan, 3.]})
    times = pd.Series(["2024-01", "2024-03", "2024-06"])
    value = next(estimates(x, times, ("2024-01", "2024-06"), True))
    assert value["mean"] == 2 and value["observed"] == 2 and value["estimable_draws"] == 0
    assert np.isnan(value["low"])


def test_unknown_model_choice_keeps_policy_value_missing():
    data = pd.DataFrame(dict(structural_eligible=[True], ml_selected=[np.nan],
                             structural_selected=[False], blind_lend=[np.nan], seen_lend=[np.nan],
                             pilot_default=[1], future_count=[25], pilot_cash=[-4.], future_cash=[80.],
                             pilot_scenario=[-9.], future_scenario=[30.]))
    p = policy_contrasts(data)
    assert p.old_cash.iloc[0] == 0. and p.old_scenario.iloc[0] == 0.
    assert p.loc[0, ["new_cash", "new_minus_old_cash", "new_scenario", "switch_new"]].isna().all()
