import numpy as np
import pandas as pd
import pytest

from paper11 import lender_pilot as lender


def test_one_signal_value_is_incremental_to_optimal_no_pilot():
    q = .186
    immediate, value = lender.forecast(q)
    assert immediate < 0 and immediate+value > 0
    chosen = [max(0., lender.margin(lender.after_signal(q,k))) for k in (0,1)]
    assert value == pytest.approx(25 * (np.dot([1-q,q], chosen) - max(0., immediate)))
    assert lender.forecast(.8)[1] == pytest.approx(0.)


def test_clock_excludes_immature_labels_and_never_uses_cash_to_choose():
    periods = pd.period_range("2010-01","2015-04",freq="M")
    frame = pd.DataFrame([dict(Country="EE", customer="new",month=m,event=(i < 2),
                          cash_unit=-.4+i*.1,cash=-40+i*10,past_original_maturity=True)
                          for m in periods for i in range(10)])
    base = lender.episodes(frame).query("pilot_month == '2013-01'").iloc[0]
    assert base.prior_n == 120 and base.fresh_n == 120
    assert base.q_initial == pytest.approx((24+.5)/(120+1))
    assert base.future_month == "2014-02" and base.future_n == 10
    frame.loc[frame.month >= pd.Period("2013-01","M"),"event"] = False
    frame[["cash_unit","cash"]] = 1000.
    changed = lender.episodes(frame).query("pilot_month == '2013-01'").iloc[0]
    for name in ("q_initial","q_fresh","selected","baseline_lend","predicted_gross","predicted_net"):
        assert base[name] == changed[name]
    assert changed.pilot_default_12m != base.pilot_default_12m


def test_cash_loss_must_be_covered_by_incremental_portfolio():
    pilot = pd.Series({"event":True, "cash":-400., "cash_unit":-.4, "past_original_maturity":True})
    portfolio = pd.DataFrame({"event":[True,False], "cash_unit":[-.8,-.1], "cash":[-800.,-100.],
                              "past_original_maturity":[True,True]})
    scored = lender.score(pilot,portfolio,.185,.16)
    assert scored["selected"] and scored["baseline_lend"] and not scored["pilot_lend"]
    assert scored["cash_covered"] and scored["cash_net"] == pytest.approx(.5)
    assert scored["euro_net"] == pytest.approx(500.)
    assert not scored["forced_covered"]
    zero = lender.score(pilot,portfolio.iloc[:0],.185,.16)
    assert zero["future_n"] == 0 and not zero["cash_covered"]


def test_later_ledger_preserves_identical_borrowers_and_missing_counterfactuals():
    field = pd.Period("2018-10","M")
    loans = pd.DataFrame([dict(Country="EE", customer="returning",month=m,Amount=100.,
                               later_cash=net,later_principal_balance=rem,later_status="Repaid",
                               later_principal_paid=paid,later_income_paid=0.,later_writeoffs=100-paid)
                          for m,net,rem,paid in [(field,-20.,0.,80.),(field+13,-50.,37.,50.)]])
    panel = pd.DataFrame([dict(country="EE",customer="returning",pilot_month=str(field),
                               future_month=str(field+13),primary=False,eligible=True,selected=True,
                               pilot_lend=False,baseline_lend=True,action_changed=True,future_n=1)])
    actual = lender.rescore_later(loans,panel).iloc[0]
    assert actual.cash_covered and actual.euro_net == pytest.approx(30.)
    assert actual.net_if_declined_portfolio_recovers_principal == pytest.approx(-.07)
    loans.loc[1, "later_cash"] = np.nan
    missing = lender.rescore_later(loans,panel).iloc[0]
    assert not missing.complete and not missing.scorable and np.isnan(missing.euro_net)
    panel["baseline_lend"] = False
    panel["action_changed"] = False
    same_action = lender.rescore_later(loans,panel).iloc[0]
    assert same_action.scorable and same_action.euro_net == pytest.approx(-20.)


def test_repackaged_archive_must_contain_exactly_the_pinned_csv(tmp_path):
    from hashlib import sha256
    from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

    contents = b"principal,payments\n100,95\n"
    expected = sha256(contents).hexdigest()
    for method in [ZIP_STORED, ZIP_DEFLATED]:
        archive = tmp_path / f"tape-{method}.zip"
        with ZipFile(archive, "w", compression=method) as file:
            file.writestr("loans.csv", contents)
        assert lender._same_csv(archive, "loans.csv", len(contents), expected)
        assert not lender._same_csv(archive, "loans.csv", len(contents), "wrong digest")
        with ZipFile(archive, "a") as file:
            file.writestr("extra.csv", b"")
        assert not lender._same_csv(archive, "loans.csv", len(contents), expected)


def test_failed_first_route_is_replaced_only_by_verified_second_download(tmp_path, monkeypatch):
    from hashlib import sha256
    from io import BytesIO

    from paper11 import data

    seen = []
    real = b"published data"
    expected = sha256(real).hexdigest()
    first, second = "https://one.example/file", "https://two.example/file"

    def open_route(request, timeout):
        seen.append(request.full_url)
        return BytesIO(real if request.full_url == second else b"<html>Service temporarily unavailable</html>")

    monkeypatch.setattr(data, "urlopen", open_route)
    destination = tmp_path / "tape"
    assert data.fetch_pinned(first, expected, destination, alternates=(second,)).read_bytes() == real
    assert seen == [first, second]
    with pytest.raises(ValueError, match="fingerprint"):
        data.fetch_pinned(first, "wrong", destination, alternates=(second,))
    assert destination.read_bytes() == real and list(tmp_path.iterdir()) == [destination]
