"""Verify deliverable consistency, without imposing a preferred empirical finding."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from numpy.testing import assert_allclose


def verify_extensions(out):
    history = pd.read_csv(out / "vintage_forecasts.csv")
    summary = pd.read_csv(out / "vintage_summary.csv").set_index("method")
    assert history.quarter.nunique() == 12 and len(history) == 48
    assert history.groupby("quarter").method.nunique().eq(4).all()
    assert_allclose(history.forecast_error, history.masking_error + history.historical_minus_future_abr,
                    atol=1e-10)
    assert_allclose(summary.forecast_rmse**2, summary.masking_rmse**2 + summary.drift_rmse**2
                    + summary.mean_cross_term, atol=1e-10)
    expected = history.assign(squared=history.forecast_error**2).groupby("method").squared.mean()
    assert_allclose(summary.forecast_rmse.sort_index()**2, expected, atol=1e-10)

    policy = pd.read_csv(out / "bounds_policy.csv")
    assert len(policy) == 5 * 8 * 2
    assert (policy.validation_worst_gain >= -policy.budget - 1e-9).all()
    assert (policy.realized_test_gain >= policy.test_binary_gain_lower - 1e-9).all()
    assert (policy.realized_test_gain <= policy.test_binary_gain_upper + 1e-9).all()
    frontier = pd.read_csv(out / "bounds_frontier.csv").sort_values("gamma")
    for _, path in frontier.groupby(["dataset","fold","target"]):
        assert (np.diff(path.delta_lower) <= 1e-9).all()
        assert (np.diff(path.delta_upper) >= -1e-9).all()
    agg = policy.groupby(["dataset","gamma","budget"]).realized_test_gain.mean()
    output = pd.read_csv(out / "bounds_summary.csv").set_index(["dataset","gamma","budget"])
    assert_allclose(agg, output.mean_realized_test_gain.sort_index(), atol=1e-9)

    rct = pd.read_csv(out / "rct_cells.csv")
    arms = rct.groupby("assigned_offer")[["n","funded"]].sum()
    assert arms.loc[1].tolist() == [891,650] and arms.loc[0].tolist() == [222,4]
    values = pd.read_csv(out / "rct_contrasts.csv").set_index("estimand").estimate
    # Only the low-score window changes when the bank expands the offer policy.
    low = rct[rct.window == "low"].set_index("assigned_offer")
    w = low.n.sum() / rct.n.sum()
    delta_cash = w * (low.loc[1,"mean_cash_revenue"] - low.loc[0,"mean_cash_revenue"])
    assert_allclose(delta_cash,values["offer_all_minus_high_only_cash_revenue"],atol=1e-8)
    bound_width = values["all_funded_hypothetical_risk_upper"]-values["all_funded_hypothetical_risk_lower"]
    assert_allclose(bound_width,1-values["funding_if_offer"],atol=1e-9)
    transfer = pd.read_csv(out / "rct_prior_transfer.csv").iloc[0]
    assert_allclose(transfer.expected_low_events,transfer.high_events/transfer.high_funded*transfer.low_funded)
    for figure in ("vintage_forecasts.png","bounds_frontier.png","rct_policy.png"):
        assert (out / figure).read_bytes().startswith(bytes.fromhex("89504e470d0a1a0a"))


def verify(out):
    def read(name):
        return pd.read_csv(out / (name + ".csv"))
    t, e, b = read("training"), read("evaluation"), read("policy")
    assert set(t.dataset) == {"prosper","taiwan"}
    assert t.groupby(["dataset","fold"]).ngroups == 5
    assert t.groupby(["dataset","fold"]).size().eq(6).all()
    assert t[["auc","pauc","abr","brier"]].apply(lambda c:c.between(0,1).all()).all()
    assert ((b.cutoff >= 0) & (b.cutoff <= 1)).all()
    assert_allclose(b.profit_per_issued, .10-1.10*b.lgd*b.test_abr, atol=1e-9)
    assert_allclose(b.profit_per_applicant, b.profit_per_issued*b.test_approval, atol=1e-9)
    rms = read("evaluation_rmse").set_index(["dataset","method","metric"]).sort_index()
    expected = e.assign(sq=e.error**2).groupby(["dataset","method","metric"]).sq.mean().pow(.5)
    assert_allclose(rms.rmse, expected, atol=1e-9)
    assert_allclose(e.error, e.estimate-e.truth, atol=1e-9)
    assert_allclose(e.within_cohort_error, e.estimate-e.validation_oracle_audit, atol=1e-9)
    tr = read("simulation_trajectory")
    assert tr.seed.nunique() == 20 and len(tr) == 100
    assert len(read("simulation_fig2_digitized")) > 0
    for name in ("simulation_fig2.png","calibration.png"):
        assert (out/name).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    cal = read("calibration").groupby(["dataset","fold","method"]).n.sum()
    parts = read("partitions")
    n_test = parts[parts.role=="test"].set_index(["dataset","fold"]).n
    for (ds,fold,_),n in cal.items():
        assert n == n_test.loc[(ds,fold)]
    ref = read("paper_comparison").set_index(["table","method","metric"])
    assert len(ref)==28
    by_model = t.groupby(["dataset","method"]).mean(numeric_only=True)
    for (table,method,metric),row in ref.iterrows():
        for ds in ("prosper","taiwan"):
            target = rms.loc[(ds,method,metric),"rmse"] if table==2 else by_model.loc[(ds,method),metric]
            assert_allclose(row[ds],target,atol=1e-9)
    audit = read("audit_budget")
    assert (audit.n_audited <= audit.n_pool).all() and audit.draws.eq(500).all()
    summary = read("audit_summary").set_index(["dataset","n_audited","design"]).sort_index()
    expected = audit.assign(square=audit.audit_rmse**2).groupby(["dataset","n_audited","design"]).square.mean()
    assert_allclose(summary.audit_rmse, np.sqrt(expected), atol=1e-9)
    diff = read("uncertainty").set_index(["dataset","contrast"])
    for ds in ("taiwan","prosper"):
        delta = by_model.loc[(ds,"basl"),"abr"]-by_model.loc[(ds,"accepts"),"abr"]
        assert_allclose(diff.loc[(ds,"basl_minus_accepts_abr"),"estimate"],delta,atol=1e-9)
    verify_extensions(out)
    print("PASS: rolling decompositions, policy bounds, randomized offers, cohort counts, score ranges, calibration counts, RMSE, financial identities, paper comparisons, paired contrasts and randomized audit.")


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,default=Path("results"))
    verify(parser.parse_args().out)
