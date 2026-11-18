import pandas as pd
import pytest

from paper11.pilot_signal_sensitivity import signal_sensitivity


def test_private_pilot_stays_out_of_the_shared_feed():
    case = dict(country="EE", customer="returning", pilot_month="2018-10", future_month="2019-11",
                selected=True, pilot_default_12m=1, fresh_n=10008, q_fresh=.1576)
    episodes = pd.DataFrame([case, dict(case, pilot_month="2018-11", selected=False)])
    loans = pd.DataFrame(dict(Country=["EE"]*3, customer=["returning"]*3,
                              month=[pd.Period("2018-10", "M")]*3, date=pd.to_datetime(["2018-10-01"]*3),
                              LoanNumber=[3, 1, 2], event=[False, True, False]))
    replay = signal_sensitivity(episodes, loans).set_index(["prior_strength", "peer_feed"])
    assert len(replay) == 6
    assert replay.loc[(20, "none")].action_changed
    assert not replay.loc[(40, "none")].action_changed
    shared = replay.loc[(20, "all_peers")]
    assert (shared.peer_n, shared.peer_defaults) == (2, 0)
    assert shared.pd_without_pilot == pytest.approx(20 * .1576 / 22)
    assert shared.pd_with_pilot == pytest.approx((20 * .1576 + 1) / 23)
    assert not shared.action_changed
