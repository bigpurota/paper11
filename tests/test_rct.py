import numpy as np
import pandas as pd
import pytest

from paper11.rct import prepare, run_experiment, summarize_cells


def example():
    rows = []
    for window in [0, 1]:
        for arm, count in [(1, 3), (0, 2)]:
            for i in range(count):
                funded = (i < 2) if arm else i == 0
                principal = 1580 if funded and i == 1 else 1600
                interest = 25 if funded else 0
                paid = principal + interest if funded else np.nan
                net = paid / 16 - 100 if funded else 0
                rows.append(dict(lower_window=window, treat=arm, prop_score=.6,
                                 loan_size=100 if funded else 0,
                                 prinpaid=principal if funded else np.nan,
                                 intpaid=interest if funded else np.nan,
                                 penalty=0 if funded else np.nan, paid_total=paid,
                                 net_revenue=net, default_value=max(-net, 0)))
    return pd.DataFrame(rows)


def test_realized_cash_loss_differs_from_principal_shortfall():
    d = prepare(example())
    assert d.material_shortfall.sum() == 2
    assert d.cash_loss.sum() == 0
    assert not d.loc[~d.funded, "material_shortfall"].any()
    invalid = example()
    invalid.loc[0, "net_revenue"] += 1
    with pytest.raises(ValueError, match="cash flow"):
        prepare(invalid)


def test_offers_do_not_equal_drawdowns_and_unfunded_risk_is_unknown():
    cells, output = run_experiment(example(), draws=30, seed=8)
    value = output.set_index("estimand").estimate
    assert cells.funded.sum() == 6
    assert value["funding_if_offer"] == pytest.approx(2/3)
    assert value["funding_if_no_offer"] == pytest.approx(1/2)
    assert value["principal_shortfall_gt1php_among_funded_if_offer"] == pytest.approx(1/2)
    assert value["all_funded_hypothetical_risk_lower"] == pytest.approx(1/3)
    assert value["all_funded_hypothetical_risk_upper"] == pytest.approx(2/3)
    assert value["negative_cash_margin_among_funded_if_offer"] == 0


def test_stratified_policy_and_wald_known_answers():
    # Entries give funding, net cash, principal and three adverse event indicators.
    m = np.zeros((2, 2, 6))
    m[0, 1] = [.8, 50, 200, .03, .01, .01]
    m[1, 1] = [.4, 20, 200, .05, .04, 0]
    m[1, 0] = [.1, 1, 30, .01, 0, 0]
    v = summarize_cells(m, .25)
    assert v["offer_all_minus_high_only_cash_revenue"] == pytest.approx(.25*(20-1))
    assert v["offer_minus_no_offer_cash_revenue"] == pytest.approx(.75*50+.25*19)
    assert v["offer_minus_no_offer_funding"] == pytest.approx(.75*.8+.25*.3)
    assert v["cash_revenue_per_induced_disbursement_wald"] == pytest.approx(42.25/.675)
    assert v["principal_shortfall_gt1php_among_funded_if_offer"] == pytest.approx(.0175/.7)


def test_prior_transfer_uses_only_source_window_for_fit():
    from paper11.rct import transfer_audit

    cells, _ = run_experiment(example(), draws=10)
    offered_low = (cells.window == "low") & (cells.assigned_offer == 1)
    cells.loc[(cells.window == "high") & (cells.assigned_offer == 1),
              ["residual_gt1php", "funded"]] = [6, 600]
    cells.loc[offered_low, ["residual_gt1php", "funded"]] = [2, 50]
    first = transfer_audit(cells)
    assert first["expected_low_events"] == .5
    assert first["low_ci_low"] < .01 < first["low_ci_high"]
    assert first["fisher_two_sided_p"] > .05
    cells.loc[offered_low, "residual_gt1php"] = 4
    second = transfer_audit(cells)
    assert first["expected_low_events"] == second["expected_low_events"]
    assert second["observed_low_rate"] == .08
