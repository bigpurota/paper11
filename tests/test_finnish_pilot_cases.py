import numpy as np
import pandas as pd
import pytest

from paper11.finnish_pilot_cases import historical_inputs, information_at_issue
from paper11.pilot_rule import value_per_unit


def test_private_value_splits_into_default_and_repayment_benefits():
    # One public state permits a default-induced refusal, one a repayment-induced
    # approval, and two leave the bank's action fixed whatever the pilot does.
    risks = np.array([.10, .16, .185, .25])
    q = risks.mean()
    a = information_at_issue(q, principal=1000., exposure=40000., nonempty_share=.5, risks=risks)
    # Payoffs per unit: +0.10 on repayment and -0.45 on default.
    avoided = .16 * (.55 * (20*.16+1)/21 - .10) / 4
    enabled = (1-.185) * (.10 - .55 * (20*.185)/21) / 4
    assert a["expected_info_after_default"] == pytest.approx(40000 * avoided)
    assert a["expected_info_after_repayment"] == pytest.approx(40000 * enabled)
    assert a["expected_information"] == pytest.approx(40000 * value_per_unit(risks).mean())
    assert a["share_public_risk_in_default_pivot_band"] == .25
    assert a["share_public_risk_in_repayment_pivot_band"] == .25
    assert a["probability_any_flip_with_nonempty"] == pytest.approx(.5 * (.16 + 1-.185) / 4)


def test_public_history_excludes_labels_too_recent_to_mature():
    origin = pd.Period("2021-03", freq="M")
    dates = pd.period_range(origin-48, origin+1, freq="M").repeat(12)
    frame = pd.DataFrame({"country": "Finland", "grade": "(unrated)", "origin": dates,
                          "event": np.arange(len(dates)) % 4 == 0})
    before, counts = historical_inputs(frame, origin)
    frame.loc[frame.origin > origin-13, "event"] = True
    frame = pd.concat([frame, frame.loc[frame.origin >= origin]], ignore_index=True)
    after, changed_counts = historical_inputs(frame, origin)
    assert before == after and before
    pd.testing.assert_series_equal(counts, changed_counts)
    assert max(before) <= origin


def test_break_even_exposure_matches_the_frozen_money_objective():
    risks = np.array([.17, .26])
    q = risks.mean()
    a = information_at_issue(q, 100., 2000., 1., risks)
    b = information_at_issue(q, 100., a["break_even_followup_principal"], 1., risks)
    c = information_at_issue(q, a["break_even_pilot_principal"], 2000., 1., risks)
    assert b["expected_total"] == pytest.approx(0.)
    assert c["expected_total"] == pytest.approx(0.)
    no_pivot = information_at_issue(.25, 100., 2000., 1., np.array([.25]))
    assert no_pivot["expected_information"] == 0
    assert np.isnan(no_pivot["break_even_followup_principal"])


def test_no_pilot_leakage_and_common_peer_outcomes_at_disclosure():
    from paper11.finnish_pilot_cases import peer_feed_at_disclosure

    peers = pd.Series([0] * 17 + [1] * 3 + [np.nan])
    a = peer_feed_at_disclosure(.16, peers, 1, -500.)
    b = peer_feed_at_disclosure(.16, peers, 0, -500.)
    assert a["peer_flags_known"] == 20 and a["peer_flags_unknown"] == 1
    assert a["later_peer_pd_without_pilot"] == b["later_peer_pd_without_pilot"] == pytest.approx(6.2/40)
    assert a["later_peer_pd_with_pilot"] == pytest.approx(7.2/41)
    assert not a["changed_with_shared_peers"] and a["incremental_future_cash_with_shared_peers"] == 0
    no_feed = peer_feed_at_disclosure(.16, pd.Series([], dtype=float), 1, -500.)
    assert no_feed["changed_with_shared_peers"] and no_feed["incremental_future_cash_with_shared_peers"] == 500
