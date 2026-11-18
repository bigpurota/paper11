import numpy as np
import pandas as pd
import pytest

from paper11.local_trust import trust_forecast
from paper11.local_trust_bank import SOURCES, score_books, summarize


def test_local_variance_and_growth_discount_against_closed_form():
    # Three equally sized donor samples, with well separated realized default rates.
    a = trust_forecast(4, 50, 200, [1, 15, 35], [50, 50, 50])
    rates = np.array([1.5, 15.5, 35.5]) / 51
    tau = np.var(rates, ddof=1) - np.mean(rates*(1-rates) / 51)
    local, broader = 4.5 / 51, 51.5 / 151
    w = tau / (tau + local * (1-local) / 13.5)
    assert a.tau2 == pytest.approx(tau)
    assert a.effective_n == 12.5
    assert a.weight == pytest.approx(w)
    assert a.hybrid == pytest.approx(w*local + (1-w)*broader)
    assert a.support_weight > w
    b = trust_forecast(0, 0, 200, [1, 15, 35], [50, 50, 50])
    assert b.weight == 0 and b.local == b.hybrid == broader


def test_variance_donors_and_pooled_support_are_distinct():
    a = trust_forecast(2, 10, 20, [10, 0, 18], [20, 5, 50])
    assert a.pooled == pytest.approx(28.5/76)
    assert a.tau2 == a.weight == 0
    assert a.hard == a.pooled
    with pytest.raises(ValueError):
        trust_forecast(0, 1, 0, [0], [0])


def row(quarter, state, count, defaults, source=SOURCES[-1]):
    return dict(quarter=pd.Period(quarter, freq="Q"), state=state, issued=count, n=count,
                defaults=defaults, principal=count*100., known_principal=count*100.,
                default_principal=defaults*100., source=source)


def test_forecasts_share_only_mature_history_and_skip_old_archive_test_positions():
    history = [row("2011Q4", "CA", 40, 10), row("2011Q4", "OR", 50, 1),
               row("2011Q4", "NY", 60, 20), row("2011Q4", "MI", 70, 30),
               row("2012Q1", "CA", 15, 10), row("2014Q4", "CA", 90, 70)]
    test = [row("2015Q1", "CA", 10, 3), row("2015Q1", "CA", 98, 77, SOURCES[0]),
            row("2015Q1", "NJ", 10, 2)]
    panel = pd.DataFrame(history + test)
    q = pd.period_range("2015Q1", periods=1, freq="Q")
    before = score_books(panel, q).set_index("state")
    assert before.loc["CA","recent_n"] == 105
    assert before.loc["CA","local_n"] == 40 and before.loc["CA", "other_n"] == 180
    assert before.loc["CA", "issued"] == 10
    assert before.loc["NJ", "local_n"] == 0 and before.loc["NJ", "weight"] == 0
    panel.loc[panel.quarter.ge(pd.Period("2012Q1", freq="Q")), "defaults"] = 0
    after = score_books(panel, q).set_index("state")
    assert np.allclose(before.hybrid, after.hybrid)
    assert not np.allclose(before.defaults, after.defaults)


def test_scenario_difference_matches_individual_loan_outcomes():
    rows = pd.DataFrame([dict(quarter="2015Q1", state="CA", local_n=20, other_n=40,
                              recent_n=30, weight=.75, local=.23, hybrid=.12, pooled=.06,
                              support_hybrid=.2, hard=.23, issued=4, n=3, defaults=1,
                              principal=1000., known_principal=900., default_principal=200.)])
    _, _, policies = summarize(rows)
    k = policies.query("sample=='matched' and good==.10 and method=='hybrid' and reference=='local'").iloc[0]
    assert k.new_lending == 1
    assert k.known_delta == pytest.approx(.10*700 - .45*200)
    assert (k.delta_lower, k.delta_upper) == pytest.approx((-65., -10.))


def test_raw_source_observes_anniversary_and_preserves_missing_event_exposure(tmp_path):
    from paper11.local_trust_bank import load_cohorts

    paths = []
    for source, year in zip(SOURCES, [1998, 2008, 2015], strict=True):
        issued = f"{year}-03-01"
        base = dict(AsOfDate="2026-09-30", ApprovalFY=year, BankFDICNumber="3511", ProjectState="CA",
                    ApprovalDate=issued, FirstDisbursementDate=issued, ChargeOffDate="",
                    LoanStatus="P I F", GrossApproval="100")
        loans = [dict(base, LoanStatus="CHGOFF", ChargeOffDate=f"{year+3}-03-01"),
                 dict(base, LoanStatus="CHGOFF", ChargeOffDate=f"{year+3}-03-02"),
                 dict(base, LoanStatus="CHGOFF", GrossApproval="300"),
                 dict(base, BankFDICNumber="100"), dict(base, GrossApproval="-1"),
                 dict(base, LoanStatus="CHGOFF", ChargeOffDate=f"{year}-02-28")]
        path = tmp_path / (source + ".csv")
        pd.DataFrame(loans).to_csv(path, index=False)
        paths.append(path)
    cells, audit = load_cohorts(paths)
    assert len(cells) == 3 and audit.unknown_flags.eq(1).all()
    assert cells.issued.eq(3).all() and cells.n.eq(2).all() and cells.defaults.eq(1).all()
    assert cells.default_principal.eq(100).all() and cells.known_principal.eq(200).all()
    assert audit.premature_chargeoff.eq(1).all() and audit.invalid_principal.eq(1).all()
