from itertools import product
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from paper11.frequency_evaluation import action_rows, brier_bounds, policy_summary


def test_unknown_principal_and_pilot_brier_envelope_matches_individual_completions():
    # 20 known performing, 30 known defaulted, and two unknown loans of 10 and 40.
    row = SimpleNamespace(future_count=4, future_principal=100., future_known_default_principal=30.,
                          future_unknown_principal=50., pilot_default=np.nan, m_blind=.18,
                          m_repay=.1, m_default=.35, m_seen=np.nan)
    exact = []
    for p, y_a, y_b in product([.1, .35], [0, 1], [0, 1]):
        y = np.array([0, 1, y_a, y_b])
        exact.append(np.average((y-.18)**2 - (y-p)**2, weights=[20, 30, 10, 40]))
    assert brier_bounds(row, "common", "revealed") == pytest.approx([min(exact), max(exact)])


def test_action_euros_couple_unknown_pilot_with_its_decision_branch():
    frame = pd.DataFrame([dict(pilot_rank=1, feed="peers", country="A", origin_month="2024-06",
                          future_count=4, future_principal=100., future_known_default_principal=30.,
                          future_unknown_principal=50., pilot_default=np.nan, q_initial=.23,
                          pi_disclosure=.18, m_public=.22, m_blind=.17, m_repay=.1, m_default=.35,
                          m_seen=np.nan, hgb_seen=np.nan, hgb_common=.25, pilot_principal=20.,
                          pilot_cash=-4., future_cash=-23., ml_selected=True,
                          structural_eligible=True, structural_selected=False)])
    ledger = pd.DataFrame(action_rows(frame))
    free = ledger.query("comparison == 'frequency_to_common'").iloc[0]
    assert free.direction == 1 and free.cash == -23.
    assert (free.scenario_lower, free.scenario_upper) == pytest.approx([-34., -6.5])
    reveal = ledger.query("comparison == 'common_to_revealed'")
    result = pd.DataFrame(policy_summary(frame, reveal)).set_index("policy")
    # Repay: +2 pilot, same action. Default: -9 pilot, decline a loss of 6.5 to 34.
    assert result.loc["anchor", ["scenario_lower", "scenario_upper"]].tolist() == pytest.approx([-2.5, 25.])
    assert np.isnan(result.loc["anchor","net_cash"])
    assert result.loc["skip", "net_cash"] == 0
